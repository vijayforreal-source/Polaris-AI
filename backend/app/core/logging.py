import logging
import sys

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a small, centralized standard-library logging setup."""
    logging.basicConfig(level=level, format=LOG_FORMAT, force=not getattr(sys, "frozen", False))

