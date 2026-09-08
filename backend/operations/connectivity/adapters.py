

from .models import BandwidthClass, ExternalProviderStatus


class ExternalDataProvider:
    source_id = "UNSPECIFIED"
    classification = "UNAVAILABLE"

    def get_status(self) -> ExternalProviderStatus:
        raise NotImplementedError

    def fetch_metadata(self):
        return None

    def fetch_latest(self):
        raise RuntimeError("SOURCE_NOT_CONFIGURED")

    def get_provenance(self):
        return {"classification": self.classification}

    def supports_offline_cache(self):
        return True

    def estimate_payload_size(self):
        return BandwidthClass.UNKNOWN


class SeaIceAdapter(ExternalDataProvider):
    source_id = "SEA_ICE_OBSERVATION"
    classification = "OBSERVATION"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=True,
            available=True,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.HIGH,
            provenance={"provider": "Copernicus Marine / OSI-SAF"},
            limitations=[
                "Uses existing local ingestion and cached artifacts; no credentials added."
            ],
        )


class ERA5ReanalysisProvider(ExternalDataProvider):
    source_id = "ERA5_REANALYSIS"
    classification = "REANALYSIS"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=True,
            available=True,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.HIGH,
            provenance={"provider": "ECMWF / Copernicus Climate"},
            limitations=["Historical reanalysis; not an operational future weather forecast."],
        )


class WeatherForecastProvider(ExternalDataProvider):
    source_id = "WEATHER_FORECAST"
    classification = "MODEL_PREDICTION"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=False,
            available=False,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.UNKNOWN,
            provenance={"provider": "NOT_CONFIGURED"},
            limitations=["No weather forecast credentials or network adapter configured."],
        )


class IcebergAdapter(ExternalDataProvider):
    source_id = "ICEBERG_REGISTRY"
    classification = "OBSERVATION"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=True,
            available=True,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.MEDIUM,
            provenance={"provider": "U.S. National Ice Center"},
            limitations=["Named/qualifying iceberg registry coverage only."],
        )


class HistoricalTransitAdapter(ExternalDataProvider):
    source_id = "HISTORICAL_TRANSIT"
    classification = "HISTORICAL_REFERENCE"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=True,
            available=True,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.LOW,
            provenance={"provider": "POLARIS verified local store"},
            limitations=[
                "Zero verified voyages remains an honest NO_VERIFIED_DATA state when applicable."
            ],
        )


class AISProvider(ExternalDataProvider):
    source_id = "AIS_FUTURE"
    classification = "OBSERVATION"

    def get_status(self):
        return ExternalProviderStatus(
            source_id=self.source_id,
            configured=False,
            available=False,
            classification=self.classification,
            refresh_supported=False,
            estimated_size_class=BandwidthClass.UNKNOWN,
            provenance={"provider": "FUTURE_HOOK"},
            limitations=["No external AIS API connection."],
        )


class OnboardGPSProvider(AISProvider):
    source_id = "GPS_FUTURE"
