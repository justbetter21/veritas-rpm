"""Tests for custom exception hierarchy."""

from veritas_rpm.exceptions import (
    AgentEvaluationError,
    InvalidRoleError,
    NoDataIngestedError,
    ValidationError,
    VeritasRPMError,
)


def test_hierarchy():
    assert issubclass(NoDataIngestedError, VeritasRPMError)
    assert issubclass(InvalidRoleError, VeritasRPMError)
    assert issubclass(ValidationError, VeritasRPMError)
    assert issubclass(AgentEvaluationError, VeritasRPMError)
    assert issubclass(VeritasRPMError, Exception)


def test_catchable_as_base():
    try:
        raise NoDataIngestedError("test")
    except VeritasRPMError as e:
        assert str(e) == "test"
