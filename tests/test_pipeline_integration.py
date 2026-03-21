"""Integration tests for the full RPMPipeline."""

from __future__ import annotations

from veritas_rpm import RPMPipeline, PipelineConfig
from veritas_rpm.config import CooldownConfig, RoutingConfig


class TestEndToEnd:
    def test_process_produces_record(self, ingested_pipeline):
        record = ingested_pipeline.process("patient-test")
        assert record.patient_id == "patient-test"
        assert record.vital_signs.hr == 108.0

    def test_get_all_decisions(self, ingested_pipeline):
        ingested_pipeline.process("patient-test")
        # With stubs, no alerts are detected → no decisions
        decisions = ingested_pipeline.get_all_decisions()
        assert isinstance(decisions, list)

    def test_multiple_patients(self, pipeline, sample_ehr_raw, sample_vitals_raw):
        pipeline.ingest_ehr("p1", sample_ehr_raw)
        pipeline.ingest_vitals("p1", sample_vitals_raw)
        pipeline.ingest_ehr("p2", sample_ehr_raw)
        pipeline.ingest_vitals("p2", sample_vitals_raw)

        r1 = pipeline.process("p1")
        r2 = pipeline.process("p2")
        assert r1.patient_id == "p1"
        assert r2.patient_id == "p2"


class TestConfiguration:
    def test_custom_cooldown_config(self):
        config = PipelineConfig(
            cooldown=CooldownConfig(doctor_minutes=60, nurse_minutes=30),
        )
        pipeline = RPMPipeline(config=config)
        assert pipeline.meta._cooldown_minutes["doctor"] == 60
        assert pipeline.meta._cooldown_minutes["nurse"] == 30

    def test_custom_routing_config(self):
        config = PipelineConfig(
            routing=RoutingConfig(routing_table={
                "tachycardia": ["TachycardiaAgent"],
            }),
        )
        pipeline = RPMPipeline(config=config)
        assert "tachycardia" in pipeline.director._routing_config.routing_table

    def test_legacy_cooldown_minutes(self):
        pipeline = RPMPipeline(cooldown_minutes={"doctor": 45})
        assert pipeline.meta._cooldown_minutes["doctor"] == 45


class TestMetrics:
    def test_metrics_initialized(self, pipeline):
        summary = pipeline.get_metrics_summary()
        assert summary["alerts_generated"] == 0
        assert summary["alerts_suppressed"] == 0

    def test_metrics_after_processing(self, ingested_pipeline):
        ingested_pipeline.process("patient-test")
        summary = ingested_pipeline.get_metrics_summary()
        # With stubs, no alerts generated
        assert summary["alerts_generated"] == 0
