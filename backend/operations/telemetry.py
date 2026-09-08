import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from .models import Position


class VesselTelemetryProvider(Protocol):
    def get_latest_position(self, vessel_id: str) -> Position | None: ...

    def get_status(self, vessel_id: str) -> dict: ...

    def get_provenance(self) -> dict: ...


class ManualTelemetryProvider:
    def __init__(self):
        self._positions: dict[str, Position] = {}

    def set_position(self, vessel_id: str, position: Position) -> None:
        self._positions[vessel_id] = position.model_copy(
            update={"source_type": "MANUAL", "source_id": vessel_id, "is_simulated": False}
        )

    def get_latest_position(self, vessel_id: str) -> Position | None:
        return self._positions.get(vessel_id)

    def get_status(self, vessel_id: str) -> dict:
        return {"available": vessel_id in self._positions, "classification": "MANUAL_INPUT"}

    def get_provenance(self) -> dict:
        return {"provider": "manual operator input", "classification": "MANUAL_INPUT"}


class FileTelemetryProvider:
    """Local test/demo provider; never represents production AIS."""

    def __init__(self, path: Path):
        self.path = path

    def get_latest_position(self, vessel_id: str) -> Position | None:
        if not self.path.is_file():
            return None
        rows = (
            json.loads(self.path.read_text())
            if self.path.suffix == ".json"
            else list(csv.DictReader(self.path.open()))
        )
        if not rows:
            return None
        row = rows[-1]
        return Position(
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            timestamp=datetime.fromisoformat(
                str(row["timestamp"]).replace("Z", "+00:00")
            ).astimezone(UTC),
            source_type="SIMULATED",
            source_id=str(self.path),
            accuracy_m=None,
            is_simulated=True,
            provenance={
                "classification": "SIMULATED",
                "provider": "local test telemetry file",
                "vessel_id": vessel_id,
            },
        )

    def get_status(self, vessel_id: str) -> dict:
        return {"available": self.path.is_file(), "classification": "SIMULATED"}

    def get_provenance(self) -> dict:
        return {"provider": "local test telemetry file", "classification": "SIMULATED"}
