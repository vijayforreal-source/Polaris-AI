from collections.abc import Callable
from datetime import datetime

VectorSampler = Callable[[float, float, datetime], tuple[float | None, float | None]]


def blend_components(
    surface_u: float,
    surface_v: float,
    depth_u: float,
    depth_v: float,
    blend_lambda: float,
) -> tuple[float, float]:
    if not 0.0 <= blend_lambda <= 1.0:
        raise ValueError("Effective-current lambda must be within [0, 1]")
    return (
        (1.0 - blend_lambda) * surface_u + blend_lambda * depth_u,
        (1.0 - blend_lambda) * surface_v + blend_lambda * depth_v,
    )


def effective_current_sampler(
    surface_sampler: VectorSampler,
    depth_sampler: VectorSampler,
    blend_lambda: float,
) -> VectorSampler:
    if not 0.0 <= blend_lambda <= 1.0:
        raise ValueError("Effective-current lambda must be within [0, 1]")

    def sample(latitude: float, longitude: float, valid_at: datetime):
        surface_u, surface_v = surface_sampler(latitude, longitude, valid_at)
        depth_u, depth_v = depth_sampler(latitude, longitude, valid_at)
        if None in (surface_u, surface_v, depth_u, depth_v):
            return None, None
        return blend_components(
            surface_u, surface_v, depth_u, depth_v, blend_lambda  # type: ignore[arg-type]
        )

    return sample

