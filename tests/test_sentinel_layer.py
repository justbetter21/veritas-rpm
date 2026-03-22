"""Tests for SentinelLayer."""

from __future__ import annotations

from unittest.mock import MagicMock

from veritas_rpm.agents.sentinel_layer import SentinelLayer
from veritas_rpm.metrics import PipelineMetrics
from veritas_rpm.models import AlertProvenanceSummary, VeritasRecord


class TestOnRecord:
    def test_returns_empty_list_for_stubs(self, sample_veritas_record):
        """All detectors are stubs returning False → no alerts."""
        sentinel = SentinelLayer()
        alerts = sentinel.on_record(sample_veritas_record)
        assert alerts == []

    def test_forwards_to_director(self, sample_veritas_record):
        director = MagicMock()
        sentinel = SentinelLayer(director=director)
        sentinel.on_record(sample_veritas_record)
        # No alerts generated (stubs), so director.handle_alert not called
        director.handle_alert.assert_not_called()


class TestBatchProcessing:
    def test_generate_candidate_alerts(self, sample_veritas_record):
        sentinel = SentinelLayer()
        alerts = sentinel.generate_candidate_alerts([sample_veritas_record] * 3)
        assert alerts == []  # Stubs produce no alerts


class TestProvenanceSummary:
    def test_extracts_trusted_sources(self, sample_veritas_record):
        sentinel = SentinelLayer()
        summary = sentinel._build_provenance_summary(sample_veritas_record)
        assert isinstance(summary, AlertProvenanceSummary)
        assert summary.vitals_source == "device_stream"
        assert "EHR_verified" in summary.context_sources


class TestMetricsIntegration:
    def test_metrics_not_incremented_for_stubs(self, sample_veritas_record):
        metrics = PipelineMetrics()
        sentinel = SentinelLayer(metrics=metrics)
        sentinel.on_record(sample_veritas_record)
        assert metrics.alerts_generated == 0  # No alerts from stubs
