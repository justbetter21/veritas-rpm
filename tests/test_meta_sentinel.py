"""Tests for MetaSentinelAgent."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from veritas_rpm.agents.meta_sentinel_agent import MetaSentinelAgent
from veritas_rpm.config import CooldownConfig
from veritas_rpm.models import AgentClaim, CandidateAlert


class TestClaimSynthesis:
    def test_empty_claims_defaults_to_nurse(self, sample_candidate_alert):
        meta = MetaSentinelAgent()
        decision = meta.aggregate_claims(sample_candidate_alert, [])
        assert decision.final_action == "queue_for_nurse"
        assert decision.priority == "low"

    def test_loudest_claim_wins(self, sample_candidate_alert):
        claims = [
            AgentClaim(
                alert_id=sample_candidate_alert.alert_id,
                agent_name="AgentA",
                classification="low_risk",
                risk_level="low",
                recommended_action="suppress",
            ),
            AgentClaim(
                alert_id=sample_candidate_alert.alert_id,
                agent_name="AgentB",
                classification="high_risk",
                risk_level="high",
                recommended_action="escalate_to_doctor",
            ),
        ]
        meta = MetaSentinelAgent()
        decision = meta.aggregate_claims(sample_candidate_alert, claims)
        assert decision.final_action == "escalate_to_doctor"
        assert decision.priority == "high"


class TestCooldown:
    def test_first_call_sets_cooldown(self, sample_candidate_alert, sample_agent_claim):
        meta = MetaSentinelAgent()
        decision = meta.aggregate_claims(
            sample_candidate_alert, [sample_agent_claim]
        )
        assert decision.cooldown_until is not None

    def test_second_call_within_window_suppresses(
        self, sample_candidate_alert, sample_agent_claim
    ):
        meta = MetaSentinelAgent(cooldown_config=CooldownConfig(nurse_minutes=60))
        # First call
        meta.aggregate_claims(sample_candidate_alert, [sample_agent_claim])
        # Second call for same patient — should be suppressed by cooldown
        decision2 = meta.aggregate_claims(sample_candidate_alert, [sample_agent_claim])
        assert decision2.final_action == "suppress"

    def test_critical_bypasses_cooldown(self, sample_candidate_alert):
        meta = MetaSentinelAgent(cooldown_config=CooldownConfig(nurse_minutes=60))
        low_claim = AgentClaim(
            alert_id=sample_candidate_alert.alert_id,
            agent_name="AgentA",
            classification="test",
            risk_level="moderate",
            recommended_action="queue_for_nurse",
        )
        # First call sets cooldown
        meta.aggregate_claims(sample_candidate_alert, [low_claim])
        # Second call with critical claim
        critical_claim = AgentClaim(
            alert_id=sample_candidate_alert.alert_id,
            agent_name="AgentB",
            classification="critical_event",
            risk_level="critical",
            recommended_action="escalate_to_doctor",
        )
        decision = meta.aggregate_claims(sample_candidate_alert, [critical_claim])
        assert decision.final_action != "suppress"


class TestOutcomeLog:
    def test_record_and_retrieve(self):
        meta = MetaSentinelAgent()
        meta.record_outcome("alert-1", "false_positive")
        log = meta.get_outcome_log()
        assert log == {"alert-1": "false_positive"}


class TestDecisionCallback:
    def test_on_decision_invoked(self, sample_candidate_alert, sample_agent_claim):
        meta = MetaSentinelAgent()
        received = []
        meta.on_decision(lambda d: received.append(d))
        meta.aggregate_claims(sample_candidate_alert, [sample_agent_claim])
        assert len(received) == 1
