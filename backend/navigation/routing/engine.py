"""Deterministic time-dependent routing over a Checkpoint 4 risk field."""

from __future__ import annotations

import hashlib
import heapq
import math
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import numpy as np
from pyproj import Geod

from backend.navigation.risk.models import RiskField
from backend.navigation.risk.vessel import VesselProfile

from .models import Objective, RouteResult, RouteWaypoint

GEOD = Geod(ellps="WGS84")
OBJECTIVES: tuple[Objective, ...] = ("SAFE", "FAST", "ECO", "BALANCED")
CATEGORY_NAMES = ("LOW", "GUARDED", "ELEVATED", "HIGH", "CRITICAL")


class RoutePlanningError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    _, _, metres = GEOD.inv(a_lon, a_lat, b_lon, b_lat)
    return float(abs(metres) / 1000)


class RoutePlanner:
    """A bounded Dijkstra search whose state is (row, col, time bucket).

    `field_provider` receives an arrival horizon in hours and returns the risk field
    valid at that horizon. The provider is memoized per bucket by the planner.
    """

    def __init__(
        self,
        field_provider: Callable[[float], RiskField],
        vessel: VesselProfile,
        departure_time: datetime,
        *,
        bucket_hours: float = 1,
        max_horizon_hours: float = 72,
        max_expansions: int = 100_000,
        max_mapping_km: float = 100,
    ):
        self.provider = field_provider
        self.vessel = vessel
        self.departure_time = departure_time.astimezone(UTC)
        self.bucket_hours = bucket_hours
        self.max_horizon = max_horizon_hours
        self.max_expansions = max_expansions
        self.max_mapping_km = max_mapping_km
        self._fields: dict[int, RiskField] = {}

    def _field(self, horizon: float) -> RiskField:
        bucket = max(0, int(round(horizon / self.bucket_hours)))
        if bucket not in self._fields:
            self._fields[bucket] = self.provider(bucket * self.bucket_hours)
        return self._fields[bucket]

    @staticmethod
    def _map(field: RiskField, latitude: float, longitude: float) -> tuple[int, int, float]:
        if not np.isfinite(latitude) or not np.isfinite(longitude):
            raise RoutePlanningError("INVALID_START", "Coordinates must be finite")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise RoutePlanningError("INVALID_START", "Coordinates are outside WGS84 bounds")
        row = int(np.argmin(abs(field.latitude - latitude)))
        col = int(np.argmin(abs(field.longitude - longitude)))
        distance = _distance_km(
            latitude, longitude, float(field.latitude[row]), float(field.longitude[col])
        )
        if distance > 100:
            raise RoutePlanningError(
                "INVALID_START", "Coordinate is too far from the regional grid"
            )
        return row, col, distance

    def _edge(self, field: RiskField, r: int, c: int, nr: int, nc: int, horizon: float):
        if not (0 <= nr < len(field.latitude) and 0 <= nc < len(field.longitude)):
            return None
        if not field.navigable_mask[nr, nc]:
            return None
        # Geodesic cell-center distance and a transparent fixed-speed profile.
        distance = _distance_km(
            float(field.latitude[r]),
            float(field.longitude[c]),
            float(field.latitude[nr]),
            float(field.longitude[nc]),
        )
        speed = float(self.vessel.nominal_speed_knots or 1)
        travel = distance / (speed * 1.852)
        arrival = horizon + travel
        if arrival > self.max_horizon + 1e-9:
            return None
        target = self._field(arrival)
        risk = float(target.risk_grid[nr, nc])
        cost = (
            float(target.navigation_cost_grid[nr, nc])
            if np.isfinite(target.navigation_cost_grid[nr, nc])
            else math.inf
        )
        if not target.navigable_mask[nr, nc] or not np.isfinite(risk):
            return None
        components = target.component_grids
        uncertainty = float(
            components.get("uncertainty_hazard", np.zeros_like(target.risk_grid))[nr, nc]
        )
        eco = distance * (1 + 0.25 * risk + 0.15 * uncertainty)
        return distance, travel, arrival, target, risk, cost, eco

    def _objective_cost(self, objective: Objective, edge) -> float:
        distance, travel, _arrival, _field, risk, cost, eco = edge
        if objective == "FAST":
            return travel + 0.001 * risk
        if objective == "ECO":
            return eco
        if objective == "SAFE":
            return (
                0.05 * distance
                + 5.0 * risk
                + 1.5 * float(_field.component_grids["uncertainty_hazard"].mean())
            )
        # Normalized engineering defaults documented in Checkpoint 5.
        return (
            0.30 * (travel / 24)
            + 0.45 * risk
            + 0.15 * (eco / 100)
            + 0.10 * float(_field.component_grids["uncertainty_hazard"].mean())
        )

    def plan(
        self, origin: tuple[float, float], destination: tuple[float, float], objective: Objective
    ) -> RouteResult:
        if objective not in OBJECTIVES:
            raise RoutePlanningError("UNSUPPORTED_OBJECTIVE", f"Unsupported objective: {objective}")
        base = self._field(0)
        try:
            sr, sc, smap = self._map(base, *origin)
        except RoutePlanningError as error:
            error.code = "INVALID_START"
            raise
        try:
            dr, dc, dmap = self._map(base, *destination)
        except RoutePlanningError as error:
            error.code = "INVALID_DESTINATION"
            raise
        if not base.navigable_mask[sr, sc]:
            raise RoutePlanningError("ORIGIN_BLOCKED", "Origin maps to a hard no-go cell")
        if not base.navigable_mask[dr, dc]:
            raise RoutePlanningError("DESTINATION_BLOCKED", "Destination maps to a hard no-go cell")
        if (sr, sc) == (dr, dc):
            raise RoutePlanningError(
                "INVALID_DESTINATION", "Origin and destination map to the same cell"
            )
        direct_km = _distance_km(
            float(base.latitude[sr]),
            float(base.longitude[sc]),
            float(base.latitude[dr]),
            float(base.longitude[dc]),
        )
        direct_eta = direct_km / (float(self.vessel.nominal_speed_knots or 1) * 1.852)
        if direct_eta > self.max_horizon:
            raise RoutePlanningError(
                "ROUTE_HORIZON_EXCEEDED",
                "The direct minimum travel time exceeds the validated forecast horizon",
            )
        heap = [(0.0, 0.0, sr, sc, 0)]
        best: dict[tuple[int, int, int], float] = {(sr, sc, 0): 0.0}
        previous: dict[tuple[int, int, int], tuple[tuple[int, int, int], tuple]] = {}
        arrivals: dict[tuple[int, int, int], float] = {(sr, sc, 0): 0.0}
        goal = None
        expanded = 0
        directions = [(dr_, dc_) for dr_ in (-1, 0, 1) for dc_ in (-1, 0, 1) if dr_ or dc_]
        while heap and expanded < self.max_expansions:
            score, horizon, r, c, bucket = heapq.heappop(heap)
            state = (r, c, bucket)
            if score > best.get(state, math.inf) + 1e-9:
                continue
            expanded += 1
            if (r, c) == (dr, dc):
                goal = state
                break
            current = self._field(horizon)
            for rr, cc in directions:
                # Prevent diagonal corner cutting through hard no-go cells.
                if rr and cc:
                    if not (
                        0 <= r + rr < len(current.latitude) and 0 <= c + cc < len(current.longitude)
                    ):
                        continue
                    if (
                        not current.navigable_mask[r, c + cc]
                        or not current.navigable_mask[r + rr, c]
                    ):
                        continue
                edge = self._edge(current, r, c, r + rr, c + cc, horizon)
                if edge is None:
                    continue
                _, travel, arrival, *_ = edge
                next_bucket = int(math.floor(arrival / self.bucket_hours + 1e-9))
                nstate = (r + rr, c + cc, next_bucket)
                value = score + self._objective_cost(objective, edge)
                if value < best.get(nstate, math.inf):
                    best[nstate] = value
                    arrivals[nstate] = arrival
                    previous[nstate] = (state, edge)
                    heapq.heappush(heap, (value, arrival, r + rr, c + cc, next_bucket))
        if goal is None:
            if expanded >= self.max_expansions:
                raise RoutePlanningError("NO_ROUTE_FOUND", "Search expansion limit reached")
            if any(k[2] >= int(self.max_horizon / self.bucket_hours) for k in best):
                raise RoutePlanningError(
                    "ROUTE_HORIZON_EXCEEDED", "No route fits the validated 72-hour horizon"
                )
            raise RoutePlanningError("NO_ROUTE_FOUND", "No contiguous navigable corridor exists")
        states = [goal]
        edges = []
        while states[-1] != (sr, sc, 0):
            prev, edge = previous[states[-1]]
            states.append(prev)
            edges.append(edge)
        states.reverse()
        edges.reverse()
        return self._result(
            objective, origin, destination, sr, sc, dr, dc, states, edges, expanded, smap, dmap
        )

    def _result(
        self, objective, origin, destination, sr, sc, dr, dc, states, edges, expanded, smap, dmap
    ):
        rows = [states[0][0]] + [s[0] for s in states[1:]]
        cols = [states[0][1]] + [s[1] for s in states[1:]]
        horizon = 0.0
        waypoints: list[RouteWaypoint] = []
        risk_values = []
        categories = defaultdict(float)
        eco = 0.0
        cumulative = 0.0
        max_uncertainty = 0.0
        total_distance = 0.0
        for i, (r, c) in enumerate(zip(rows, cols, strict=True)):
            field = self._field(horizon)
            risk = float(field.risk_grid[r, c])
            components = field.component_grids
            category = CATEGORY_NAMES[min(4, int(field.risk_category_grid[r, c]))]
            segment_distance = edges[i - 1][0] if i else 0.0
            segment_time = edges[i - 1][1] if i else 0.0
            if i:
                horizon += segment_time
                field = self._field(horizon)
                risk = float(field.risk_grid[r, c])
                category = CATEGORY_NAMES[min(4, int(field.risk_category_grid[r, c]))]
            categories[category] += segment_time
            risk_values.append(risk)
            cumulative += risk * segment_distance
            total_distance += segment_distance
            eco += edges[i - 1][6] if i else 0
            max_uncertainty = max(max_uncertainty, float(components["uncertainty_hazard"][r, c]))
            labels = field.metadata.get("dominant_factor_labels", ())
            dominant_index = int(field.dominant_factor_grid[r, c])
            dominant_label = (
                labels[dominant_index] if dominant_index < len(labels) else str(dominant_index)
            )
            waypoints.append(
                RouteWaypoint(
                    sequence=i,
                    latitude=float(field.latitude[r]),
                    longitude=float(field.longitude[c]),
                    arrival_time=self.departure_time + timedelta(hours=horizon),
                    elapsed_hours=horizon,
                    segment_distance_km=segment_distance,
                    segment_time_hours=segment_time,
                    risk_score=risk,
                    risk_category=category,
                    navigable=bool(field.navigable_mask[r, c]),
                    navigation_cost=float(field.navigation_cost_grid[r, c])
                    if np.isfinite(field.navigation_cost_grid[r, c])
                    else None,
                    dominant_risk_factor=dominant_label,
                    sea_ice_hazard=float(components["sea_ice_hazard"][r, c]),
                    iceberg_hazard=float(components["iceberg_hazard"][r, c]),
                    uncertainty_hazard=float(components["uncertainty_hazard"][r, c]),
                    vessel_constraint_hazard=float(components["vessel_constraint_hazard"][r, c]),
                    historical_transit_confidence=float(
                        components["historical_transit_confidence"][r, c]
                    ),
                )
            )
        route_id = (
            "route-"
            + hashlib.sha1(
                f"{origin}-{destination}-{self.departure_time.isoformat()}-{objective}".encode()
            ).hexdigest()[:12]
        )
        support = (
            "AVAILABLE"
            if any(w.historical_transit_confidence > 0 for w in waypoints)
            else "NO_VERIFIED_DATA"
        )
        explanation = {
            "SAFE": (
                "SAFE route minimizes cumulative safety exposure while respecting every "
                "hard no-go cell."
            ),
            "FAST": "FAST route minimizes ETA while remaining outside all hard no-go cells.",
            "ECO": (
                "ECO route minimizes the relative distance-weighted energy proxy; it is not "
                "fuel consumption."
            ),
            "BALANCED": (
                "BALANCED route combines normalized time, risk, eco proxy and uncertainty "
                "using engineering defaults (0.30/0.45/0.15/0.10)."
            ),
        }[objective]
        return RouteResult(
            route_id=route_id,
            objective=objective,
            status="AVAILABLE",
            origin={
                "requested": {"latitude": origin[0], "longitude": origin[1]},
                "mapped": {"latitude": waypoints[0].latitude, "longitude": waypoints[0].longitude},
                "mapping_distance_km": smap,
            },
            destination={
                "requested": {"latitude": destination[0], "longitude": destination[1]},
                "mapped": {
                    "latitude": waypoints[-1].latitude,
                    "longitude": waypoints[-1].longitude,
                },
                "mapping_distance_km": dmap,
            },
            departure_time=self.departure_time,
            arrival_time=waypoints[-1].arrival_time,
            eta_hours=horizon,
            distance_km=total_distance,
            distance_nm=total_distance / 1.852,
            mean_risk=float(np.mean(risk_values)),
            max_risk=float(np.max(risk_values)),
            cumulative_risk_exposure=cumulative,
            time_in_LOW=categories["LOW"],
            time_in_GUARDED=categories["GUARDED"],
            time_in_ELEVATED=categories["ELEVATED"],
            time_in_HIGH=categories["HIGH"],
            time_in_CRITICAL=categories["CRITICAL"],
            eco_cost_proxy=eco,
            maximum_uncertainty=max_uncertainty,
            historical_transit_support=support,
            waypoints=waypoints,
            display_waypoints=waypoints,
            explanation=explanation,
            provenance={
                "routing_algorithm": "time-dependent Dijkstra",
                "time_bucket_hours": self.bucket_hours,
                "risk_engine": "Checkpoint 4 RiskField",
                "vessel_profile": self.vessel.vessel_id,
                "forecast_horizon_hours": self.max_horizon,
                "origin_mapping_distance_km": smap,
                "destination_mapping_distance_km": dmap,
            },
            expanded_states=expanded,
        )
