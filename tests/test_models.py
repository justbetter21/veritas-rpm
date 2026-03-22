"""Tests for Pydantic data models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from veritas_rpm.models import (
    AgentClaim,
    AlertFeatures,
    AlertProvenanceSummary,
    CandidateAlert,
    DecisionMeta,
    EHRData,
    SystemDecision,
    VeritasRecord,
    VitalSigns,
)


class TestVeritasRecord:
    def test_valid_construction(self):
        record = VeritasRecord(
            record_id="r1",
            patient_id="p1",
            timestamp=datetime.now(timezone.utc),
            provenance={"ehr_data": "EHR_verified"},
        )
        assert record.patient_id == "p1"

    def test_rejects_extra_fields(self):
        with pytest.raises(PydanticValidationError):
            VeritasRecord(
                record_id="r1",
                patient_id="p1",
                timestamp=datetime.now(timezone.utc),
                provenance={},
                unknown_field="bad",
            )

    def test_default_sub_objects(self):
        record = VeritasRecord(
            record_id="r1",
            patient_id="p1",
            timestamp=datetime.now(timezone.utc),
            provenance={},
        )
        assert record.ehr_data.diagnoses == []
        assert record.vital_signs.hr is None


class TestCandidateAlert:
    def test_valid_construction(self, sample_candidate_alert):
        assert sample_candidate_alert.alert_type == "tachycardia"

    def test_serialization_roundtrip(self, sample_candidate_alert):
        data = sample_candidate_alert.model_dump()
        restored = CandidateAlert(**data)
        assert restored.alert_id == sample_candidate_alert.alert_id

    def test_rejects_invalid_alert_type(self):
        with pytest.raises(PydanticValidationError):
            CandidateAlert(
                alert_id="a1",
                patient_id="p1",
                alert_type="invalid_type",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc),
            )


class TestAgentClaim:
    def test_valid_construction(self, sample_agent_claim):
        assert sample_agent_claim.agent_name == "TachycardiaAgent"

    def test_rejects_invalid_risk_level(self):
        with pytest.raises(PydanticValidationError):
            AgentClaim(
                alert_id="a1",
                agent_name="Test",
                classification="test",
                risk_level="invalid",
                recommended_action="suppress",
            )


class TestSystemDecision:
    def test_valid_construction(self):
        decision = SystemDecision(
            alert_id="a1",
            final_action="suppress",
            target_role="patient",
            priority="low",
        )
        assert decision.final_action == "suppress"

    def test_rejects_invalid_action(self):
        with pytest.raises(PydanticValidationError):
            SystemDecision(
                alert_id="a1",
                final_action="invalid",
                target_role="patient",
                priority="low",
            )
