from pydantic import BaseModel, Field, model_validator


class StudyRegion(BaseModel):
    """Geographic bounds for source subsetting; no CRS conversion is implied."""

    minimum_longitude: float = Field(ge=-180, le=180)
    maximum_longitude: float = Field(ge=-180, le=180)
    minimum_latitude: float = Field(ge=-90, le=90)
    maximum_latitude: float = Field(ge=-90, le=90)
    bharati_latitude: float = Field(ge=-90, le=90)
    bharati_longitude: float = Field(ge=-180, le=180)

    @model_validator(mode="after")
    def validate_bounds_and_anchor(self) -> "StudyRegion":
        if self.minimum_longitude >= self.maximum_longitude:
            raise ValueError("minimum_longitude must be less than maximum_longitude")
        if self.minimum_latitude >= self.maximum_latitude:
            raise ValueError("minimum_latitude must be less than maximum_latitude")
        if not self.minimum_longitude <= self.bharati_longitude <= self.maximum_longitude:
            raise ValueError("Bharati longitude must lie within the study region")
        if not self.minimum_latitude <= self.bharati_latitude <= self.maximum_latitude:
            raise ValueError("Bharati latitude must lie within the study region")
        return self


BHARATI_PRYDZ_BAY = StudyRegion(
    minimum_longitude=70.0,
    maximum_longitude=84.0,
    minimum_latitude=-70.5,
    maximum_latitude=-66.0,
    bharati_latitude=-69.4068,
    bharati_longitude=76.1953,
)

