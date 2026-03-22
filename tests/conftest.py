"""Shared pytest fixtures for the Veritas-RPM test suite."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from veritas_rpm import RPMPipeline, PipelineConfig
from veritas_rpm.models import (
    AgentClaim,
    AlertFeatures,
    AlertProvenanceSummary,
    CandidateAlert,
    SystemDecision,
    DecisionMeta,
    VeritasRecord,
)


# ---------------------------------------------------------------------------
# Raw data samples
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ehr_raw() -> dict:
    return {
        "diagnoses": ["COPD", "Hypertension"],
        "medications": ["Salbutamol inhaler", "Lisinopril 10mg"],
        "baseline_spo2": 93.0,
        "baseline_hr": 72.0,
        "recent_admissions": [],
    }


@pytest.fixture
def sample_vitals_raw() -> dict:
    return {
        "hr": 108.0,
        "spo2": 91.0,
        "resp_rate": 22.0,
        "signal_quality": "good",
        "activity_level": "moderate",
    }


@pytest.fixture
def sample_conversation_raw() -> dict:
    return {
        "symptoms": ["mild breathlessness on exertion"],
        "activities": ["walked 20 minutes this afternoon"],
        "adherence_notes": "took all medications this morning",
    }


@pytest.fixture
def sample_patient_input_raw() -> dict:
    return {
        "free_text": "The probe slipped off my finger again.",
        "symptom_severity": None,
    }


# ---------------------------------------------------------------------------
# Model instances
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_veritas_record() -> VeritasRecord:
    return VeritasRecord(
        record_id=str(uuid.uuid4()),
        patient_id="patient-test",
        timestamp=datetime.now(timezone.utc),
        provenance={
            "ehr_data": "EHR_verified",
            "vital_signs": "device_stream",
        },
    )


@pytest.fixture
def sample_candidate_alert() -> CandidateAlert:
    return CandidateAlert(
        alert_id=str(uuid.uuid4()),
        patient_id="patient-test",
        alert_type="tachycardia",
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        features=AlertFeatures(max_hr=120.0, avg_hr=115.0),
        provenance_summary=AlertProvenanceSummary(
            vitals_source="device_stream",
            context_sources=["EHR_verified"],
        ),
    )


@pytest.fixture
def sample_agent_claim(sample_candidate_alert: CandidateAlert) -> AgentClaim:
    return AgentClaim(
        alert_id=sample_candidate_alert.alert_id,
        agent_name="TachycardiaAgent",
        classification="undetermined_tachycardia",
        risk_level="moderate",
        recommended_action="queue_for_nurse",
        justification="Test claim",
        used_fields=["vital_signs.hr"],
    )


# ---------------------------------------------------------------------------
# Pipeline fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def pipeline() -> RPMPipeline:
    return RPMPipeline()


@pytest.fixture
def ingested_pipeline(
    pipeline: RPMPipeline,
    sample_ehr_raw: dict,
    sample_vitals_raw: dict,
    sample_conversation_raw: dict,
) -> RPMPipeline:
    pid = "patient-test"
    pipeline.ingest_ehr(pid, sample_ehr_raw)
    pipeline.ingest_vitals(pid, sample_vitals_raw)
    pipeline.ingest_conversation(pid, sample_conversation_raw)
    return pipeline
