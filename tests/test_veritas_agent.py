"""Tests for VeritasAgent."""

from __future__ import annotations

import pytest

from veritas_rpm.agents.veritas_agent import VeritasAgent
from veritas_rpm.exceptions import NoDataIngestedError, ValidationError
from veritas_rpm.models import VeritasRecord


class TestIngestValidation:
    def test_empty_patient_id_raises(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="non-empty string"):
            agent.ingest_ehr("", {"diagnoses": []})

    def test_non_string_patient_id_raises(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError):
            agent.ingest_ehr(123, {})  # type: ignore[arg-type]

    def test_non_dict_raw_raises(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="must be a dict"):
            agent.ingest_ehr("p1", "not a dict")  # type: ignore[arg-type]

    def test_diagnoses_must_be_list(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="diagnoses must be a list"):
            agent.ingest_ehr("p1", {"diagnoses": "COPD"})

    def test_medications_must_be_list(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="medications must be a list"):
            agent.ingest_ehr("p1", {"medications": "Metoprolol"})

    def test_negative_hr_raises(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="non-negative"):
            agent.ingest_vitals("p1", {"hr": -10})

    def test_negative_spo2_raises(self):
        agent = VeritasAgent()
        with pytest.raises(ValidationError, match="non-negative"):
            agent.ingest_vitals("p1", {"spo2": -5})

    def test_valid_vitals_accepted(self, sample_vitals_raw):
        agent = VeritasAgent()
        agent.ingest_vitals("p1", sample_vitals_raw)  # Should not raise

    def test_none_vitals_accepted(self):
        agent = VeritasAgent()
        agent.ingest_vitals("p1", {"hr": None, "spo2": None})


class TestBuildRecord:
    def test_no_data_raises(self):
        agent = VeritasAgent()
        with pytest.raises(NoDataIngestedError):
            agent.build_record("p1")

    def test_ehr_only_succeeds(self, sample_ehr_raw):
        agent = VeritasAgent()
        agent.ingest_ehr("p1", sample_ehr_raw)
        record = agent.build_record("p1")
        assert isinstance(record, VeritasRecord)
        assert record.patient_id == "p1"

    def test_provenance_defaults(self, sample_ehr_raw):
        agent = VeritasAgent()
        agent.ingest_ehr("p1", sample_ehr_raw)
        record = agent.build_record("p1")
        assert record.provenance["ehr_data"] == "EHR_verified"
        assert record.provenance["vital_signs"] == "device_stream"

    def test_provenance_override(self, sample_ehr_raw):
        agent = VeritasAgent()
        agent.ingest_ehr("p1", sample_ehr_raw)
        agent.tag_provenance("p1", "ehr_data", "human_confirmed")
        record = agent.build_record("p1")
        assert record.provenance["ehr_data"] == "human_confirmed"

    def test_subscriber_called(self, sample_ehr_raw):
        agent = VeritasAgent()
        agent.ingest_ehr("p1", sample_ehr_raw)
        received = []
        agent.subscribe(lambda r: received.append(r))
        agent.build_record("p1")
        assert len(received) == 1
        assert received[0].patient_id == "p1"


class TestBuildAndStream:
    def test_yields_per_vitals(self, sample_ehr_raw):
        agent = VeritasAgent()
        agent.ingest_ehr("p1", sample_ehr_raw)
        vitals_seq = [
            {"hr": 80.0, "spo2": 95.0},
            {"hr": 85.0, "spo2": 94.0},
            {"hr": 90.0, "spo2": 93.0},
        ]
        records = list(agent.build_and_stream("p1", vitals_seq))
        assert len(records) == 3
        assert records[2].vital_signs.hr == 90.0
