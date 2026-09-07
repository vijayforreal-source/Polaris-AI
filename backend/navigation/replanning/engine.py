from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime

import numpy as np

from backend.navigation.risk.models import RiskField
from backend.navigation.risk.vessel import VesselProfile
from backend.navigation.routing.engine import RoutePlanner, RoutePlanningError
from backend.navigation.routing.models import Objective, RouteResult

from .config import CONFIG, ReplanningConfig
from .models import ActiveVoyage, ReplanDecision


class ReplanningEngine:
    """Pure decision engine; no polling, telemetry, or autonomous route application."""

    def __init__(
        self,
        field_provider: Callable[[float, VesselProfile], RiskField],
        planner_factory: Callable[
            [datetime, tuple[float, float], tuple[float, float], Objective], RoutePlanner
        ],
        vessel: VesselProfile,
        *,
        config: ReplanningConfig = CONFIG,
        environment_version_provider: Callable[[], str] | None = None,
    ):
        self.field_provider = field_provider
        self.planner_factory = planner_factory
        self.vessel = vessel
        self.config = config
        self.environment_version_provider = environment_version_provider or (lambda: "UNKNOWN")

    def environment_version(self) -> str:
        return self.environment_version_provider()

    def evaluate_route(self, voyage: ActiveVoyage) -> dict:
        route = voyage.current_route
        now = voyage.current_time
        remaining = [point for point in route.waypoints if point.arrival_time >= now]
        if not remaining:
            remaining = [route.waypoints[-1]]
        risks = []
        uncertainty = []
        blocked = []
        critical = []
        distance = 0.0
        eta = 0.0
        cumulative = 0.0
        for point in remaining:
            elapsed = max(0.0, (point.arrival_time - voyage.departure_time).total_seconds() / 3600)
            if elapsed > 72:
                return {
                    "status": "FORECAST_HORIZON_EXCEEDED",
                    "blocked_segments": [],
                    "remaining_waypoints": len(remaining),
                }
            try:
                field = self.field_provider(elapsed, self.vessel)
            except Exception as error:
                return {
                    "status": "REPLAN_UNAVAILABLE",
                    "reason": str(error),
                    "blocked_segments": [],
                }
            row = int(np.argmin(abs(field.latitude - point.latitude)))
            col = int(np.argmin(abs(field.longitude - point.longitude)))
            risk = float(field.risk_grid[row, col])
            risks.append(risk)
            uncertainty.append(float(field.component_grids["uncertainty_hazard"][row, col]))
            if not field.navigable_mask[row, col]:
                blocked.append(point.sequence)
            if risk >= 0.8:
                critical.append(point.sequence)
            distance += point.segment_distance_km
            eta += point.segment_time_hours
            cumulative += risk * point.segment_distance_km
        return {
            "status": "AVAILABLE" if not blocked else "BLOCKED",
            "mean_remaining_risk": float(np.mean(risks)) if risks else 0,
            "max_remaining_risk": float(np.max(risks)) if risks else 0,
            "cumulative_remaining_risk": cumulative,
            "max_uncertainty": float(np.max(uncertainty)) if uncertainty else 0,
            "blocked_segments": blocked,
            "critical_segments": critical,
            "high_risk_duration_hours": sum(
                p.segment_time_hours for p in remaining if p.risk_score >= 0.6
            ),
            "forecast_horizon_usage_hours": max(
                (p.arrival_time - voyage.departure_time).total_seconds() / 3600 for p in remaining
            ),
            "eta_remaining_hours": eta,
            "distance_remaining_km": distance,
        }

    @staticmethod
    def _metrics(route: RouteResult) -> dict:
        return {
            "eta_hours": route.eta_hours,
            "distance_km": route.distance_km,
            "mean_risk": route.mean_risk,
            "max_risk": route.max_risk,
            "cumulative_risk": route.cumulative_risk_exposure,
            "eco_proxy": route.eco_cost_proxy,
            "uncertainty": route.maximum_uncertainty,
        }

    def _decision(self, voyage, current, candidate, *, now, environment_version, hard):
        before = dict(current)
        after = self._metrics(candidate) if candidate else None
        if candidate:
            after.update(
                {
                    "eta_remaining_hours": candidate.eta_hours,
                    "distance_remaining_km": candidate.distance_km,
                }
            )
        delta = {}
        if after:
            for key in (
                "eta_hours",
                "distance_km",
                "mean_risk",
                "max_risk",
                "cumulative_risk",
                "eco_proxy",
                "uncertainty",
            ):
                old = before.get(key)
                new = after.get(key)
                if old is not None and new is not None:
                    delta[key] = new - old
        if hard:
            decision = "REROUTE_REQUIRED" if candidate else "NO_SAFE_ALTERNATIVE"
            reason = ["CURRENT_ROUTE_HARD_INVALID"] + ([] if candidate else ["NO_SAFE_ALTERNATIVE"])
            text = "A hard environmental constraint intersects the remaining route."
        elif not candidate:
            decision, reason, text = (
                "KEEP_CURRENT",
                ["NO_MEANINGFUL_ALTERNATIVE"],
                "No candidate provides a meaningful improvement.",
            )
        else:
            risk_improvement = before.get("mean_remaining_risk", before.get("mean_risk", 1)) - (
                candidate.mean_risk or 1
            )
            cumulative_old = before.get(
                "cumulative_remaining_risk", before.get("cumulative_risk", 0)
            )
            cumulative_improvement_pct = (
                (
                    (cumulative_old - (candidate.cumulative_risk_exposure or 0))
                    / cumulative_old
                    * 100
                )
                if cumulative_old
                else 0
            )
            eta_improvement_pct = (
                (
                    before.get("eta_remaining_hours", before.get("eta_hours", 0))
                    - (candidate.eta_hours or 0)
                )
                / before.get("eta_remaining_hours", before.get("eta_hours", 1))
                * 100
            )
            meaningful = (
                risk_improvement >= self.config.minimum_risk_improvement
                or cumulative_improvement_pct >= self.config.minimum_cumulative_risk_improvement_pct
                or eta_improvement_pct >= self.config.minimum_eta_improvement_pct
            )
            cooldown = (
                voyage.last_replan_at
                and (now - voyage.last_replan_at).total_seconds()
                < self.config.cooldown_minutes * 60
            )
            if cooldown:
                decision, reason, text = (
                    "KEEP_CURRENT",
                    ["REPLAN_COOLDOWN_ACTIVE"],
                    "Cooldown is active after the previous replanning recommendation.",
                )
            elif meaningful:
                decision, reason, text = (
                    "REROUTE_RECOMMENDED",
                    ["MEANINGFUL_ROUTE_IMPROVEMENT"],
                    "The candidate route provides a meaningful configured improvement.",
                )
            else:
                decision, reason, text = (
                    "KEEP_CURRENT",
                    ["IMPROVEMENT_BELOW_THRESHOLD"],
                    "Candidate improvement is below the configured reroute threshold; "
                    "current route is retained.",
                )
        return ReplanDecision(
            decision=decision,
            reason_codes=reason,
            explanation=text,
            environment_version=environment_version,
            voyage=voyage,
            current_metrics=before,
            candidate_metrics=after,
            delta=delta,
            candidate_route=candidate,
            evaluated_at=now,
        )

    def replan(self, voyage: ActiveVoyage) -> ReplanDecision:
        environment_version = self.environment_version()
        current = self.evaluate_route(voyage)
        hard = current.get("status") in {
            "BLOCKED",
            "FORECAST_HORIZON_EXCEEDED",
            "REPLAN_UNAVAILABLE",
        }
        destination = (
            float(voyage.destination["mapped"]["latitude"]),
            float(voyage.destination["mapped"]["longitude"]),
        )
        origin = (voyage.current_position_lat, voyage.current_position_lon)
        candidate = None
        try:
            planner = self.planner_factory(
                voyage.current_time, origin, destination, voyage.objective
            )
            candidate = (
                planner.plan(origin, destination, voyage.objective)
                if hasattr(planner, "plan")
                else planner
            )
        except RoutePlanningError:
            candidate = None
        if current.get("status") == "FORECAST_HORIZON_EXCEEDED":
            return self._decision(
                voyage,
                current,
                candidate,
                now=voyage.current_time,
                environment_version=environment_version,
                hard=True,
            )
        return self._decision(
            voyage,
            current,
            candidate,
            now=voyage.current_time,
            environment_version=environment_version,
            hard=hard,
        )

    @staticmethod
    def voyage_id(route: RouteResult, value: str) -> str:
        return value or hashlib.sha1(route.route_id.encode()).hexdigest()[:12]
