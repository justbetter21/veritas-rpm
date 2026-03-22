"""
exceptions.py — Custom exception hierarchy for Veritas-RPM.

All public exceptions inherit from VeritasRPMError, allowing callers
to catch the full family with a single ``except VeritasRPMError`` clause
or to handle specific cases individually.
"""


class VeritasRPMError(Exception):
    """Base exception for all veritas_rpm errors."""


class NoDataIngestedError(VeritasRPMError):
    """Raised when build_record is called with no ingested data for a patient."""


class InvalidRoleError(VeritasRPMError):
    """Raised when an unknown role string is used."""


class ValidationError(VeritasRPMError):
    """Raised when input data fails validation."""


class AgentEvaluationError(VeritasRPMError):
    """Wraps an exception raised by a specialist agent during evaluation."""
