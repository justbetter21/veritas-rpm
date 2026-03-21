"""Tests for DirectorAgent."""

from __future__ import annotations

from unittest.mock import MagicMock

from veritas_rpm.agents.director_agent import DirectorAgent
from veritas_rpm.config import RoutingConfig
from veritas_rpm.models import CandidateAlert, VeritasRecord


class TestAgentSelection:
    def test_selects_correct_agents_for_tachycardia(
        self, sample_candidate_alert, sample_veritas_record
    ):
        director = DirectorAgent()
        director.update_context(sample_veritas_record)
        selected = director._select_agents(sample_candidate_alert, sample_veritas_record)
        agent_names = [a.name for a in selected]
        assert "TachycardiaAgent" in agent_names
        assert "ActivityIntegrityAgent" in agent_names
        assert "ProbeIntegrityAgent" in agent_names

    def test_unknown_alert_type_returns_empty(self, sample_veritas_record):
        config = RoutingConfig(routing_table={"tachycardia": ["TachycardiaAgent"]})
        director = DirectorAgent(routing_config=config)
        # Create alert with 'other' type not in our minimal config
        from datetime import datetime, timezone
        import uuid
        alert = CandidateAlert(
            alert_id=str(uuid.uuid4()),
            patient_id="patient-test",
            alert_type="other",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        selected = director._select_agents(alert, sample_veritas_record)
        assert selected == []

    def test_custom_routing_config(self, sample_candidate_alert, sample_veritas_record):
        config = RoutingConfig(routing_table={
            "tachycardia": ["BradycardiaAgent"],
        })
        director = DirectorAgent(routing_config=config)
        selected = director._select_agents(sample_candidate_alert, sample_veritas_record)
        assert len(selected) == 1
        assert selected[0].name == "BradycardiaAgent"


class TestHandleAlert:
    def test_handle_alert_without_context(self, sample_candidate_alert):
        """Should log warning but still produce claims."""
        meta = MagicMock()
        director = DirectorAgent(meta_sentinel=meta)
        claims = director.handle_alert(sample_candidate_alert)
        # Claims are produced (stubs return default claims)
        assert isinstance(claims, list)
        meta.aggregate_claims.assert_called_once()

    def test_handle_alert_with_context(
        self, sample_candidate_alert, sample_veritas_record
    ):
        meta = MagicMock()
        director = DirectorAgent(meta_sentinel=meta)
        director.update_context(sample_veritas_record)
        claims = director.handle_alert(sample_candidate_alert)
        assert len(claims) > 0
        assert all(c.alert_id == sample_candidate_alert.alert_id for c in claims)


class TestContextCache:
    def test_update_context(self, sample_veritas_record):
        director = DirectorAgent()
        director.update_context(sample_veritas_record)
        assert sample_veritas_record.patient_id in director._context_cache


class TestAgentExceptionHandling:
    def test_faulty_agent_does_not_crash_pipeline(
        self, sample_candidate_alert, sample_veritas_record
    ):
        director = DirectorAgent()
        director.update_context(sample_veritas_record)

        # Monkey-patch one agent to raise
        director._tachycardia_agent.evaluate = MagicMock(
            side_effect=RuntimeError("boom")
        )
        claims = director.handle_alert(sample_candidate_alert)
        # Other agents still produce claims
        assert isinstance(claims, list)
