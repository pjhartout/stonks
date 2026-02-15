"""Custom exceptions for stonks."""


class StonksError(Exception):
    """Base exception for all stonks errors."""


class DatabaseError(StonksError):
    """Error interacting with the SQLite database."""


class RunError(StonksError):
    """Error related to run lifecycle."""


class InvalidMetricError(StonksError):
    """Error when a metric value is invalid (e.g. Inf)."""
