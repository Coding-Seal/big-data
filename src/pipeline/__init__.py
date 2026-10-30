"""The pipeline, one module per medallion stage: bronze, silver, gold."""
from . import bronze, gold, silver, storage

__all__ = ["bronze", "silver", "gold", "storage"]
