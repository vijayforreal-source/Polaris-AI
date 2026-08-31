from dataclasses import dataclass


@dataclass(frozen=True)
class ChronologicalSplit:
    fit: range
    uncertainty_calibration: range
    final_test: range

    def validate(self, interval_count: int) -> None:
        partitions = [list(self.fit), list(self.uncertainty_calibration), list(self.final_test)]
        flattened = [index for partition in partitions for index in partition]
        if flattened != list(range(interval_count)):
            raise ValueError("Chronological split must cover each interval once, in order")


def a76c_split(interval_count: int = 34) -> ChronologicalSplit:
    if interval_count != 34:
        raise ValueError("The verified A76C checkpoint contract contains 34 intervals")
    split = ChronologicalSplit(range(0, 20), range(20, 27), range(27, 34))
    split.validate(interval_count)
    return split


def lambda_grid() -> tuple[float, ...]:
    return tuple(index / 20 for index in range(21))


def select_lambda(search: list[dict[str, float]]) -> float:
    if not search:
        raise ValueError("Lambda search results cannot be empty")
    # Grid precision is deliberately retained; ties prefer the simpler surface limit.
    return min(search, key=lambda row: (row["mean_error_km"], row["lambda"]))["lambda"]

