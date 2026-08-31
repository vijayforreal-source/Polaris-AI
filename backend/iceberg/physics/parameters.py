from dataclasses import dataclass

WDE17_DOI = "10.1175/JPO-D-16-0262.1"
NM_TO_METRES = 1852.0


@dataclass(frozen=True)
class ScientificParameter:
    name: str
    value: float
    units: str
    source: str
    citation: str
    description: str


@dataclass(frozen=True)
class WDE17Parameters:
    water_density: ScientificParameter
    air_density: ScientificParameter
    ice_density: ScientificParameter
    water_drag_coefficient: ScientificParameter
    air_drag_coefficient: ScientificParameter
    earth_rotation_rate: ScientificParameter


def paper_parameters() -> WDE17Parameters:
    """Peer-reviewed WDE17 values used by the canonical POLARIS-AI P3 run."""
    paper = f"Wagner, Dell & Eisenman (2017), DOI {WDE17_DOI}"
    bigg = "Bigg et al. (1997), as cited by WDE17 section 4a"
    return WDE17Parameters(
        water_density=ScientificParameter(
            "water_density", 1027.0, "kg m-3", paper, paper, "Seawater density."
        ),
        air_density=ScientificParameter(
            "air_density", 1.2, "kg m-3", paper, paper, "Air density."
        ),
        ice_density=ScientificParameter(
            "ice_density",
            850.0,
            "kg m-3",
            "Silva et al. (2006), as cited by WDE17",
            paper,
            "Shelf-ice density.",
        ),
        water_drag_coefficient=ScientificParameter(
            "water_drag_coefficient", 0.9, "dimensionless", bigg, paper, "Water drag."
        ),
        air_drag_coefficient=ScientificParameter(
            "air_drag_coefficient", 1.3, "dimensionless", bigg, paper, "Air drag."
        ),
        earth_rotation_rate=ScientificParameter(
            "earth_rotation_rate",
            7.2921e-5,
            "rad s-1",
            "WDE17 reference implementation",
            paper,
            "Earth angular rotation rate.",
        ),
    )


def reference_code_parameters() -> WDE17Parameters:
    """Values literally assigned by the authors' posted MATLAB implementation."""
    return paper_parameters()
