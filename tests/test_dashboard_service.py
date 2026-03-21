"""Tests for DashboardService."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from veritas_rpm.exceptions import InvalidRoleError
from veritas_rpm.models import SystemDecision
from veritas_rpm.services.dashboard_service import DashboardService


def _make_decision(action: str, role: str = "nurse") -> SystemDecision:
    return SystemDecision(
        alert_id="alert-test-1",
        final_action=action,
        target_role=role,
        priority="normal",
    )


class TestRouting:
    def test_suppress_does_not_queue(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("suppress", "patient"))
        assert ds.get_patient_queue() == []
        assert ds.get_nurse_queue() == []
        assert ds.get_doctor_queue() == []

    def test_notify_patient_adds_to_patient_queue(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("notify_patient", "patient"))
        assert len(ds.get_patient_queue()) == 1

    def test_queue_for_nurse(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("queue_for_nurse", "nurse"))
        assert len(ds.get_nurse_queue()) == 1

    def test_escalate_to_doctor(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("escalate_to_doctor", "doctor"))
        assert len(ds.get_doctor_queue()) == 1


class TestAcknowledge:
    def test_removes_from_queue(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("queue_for_nurse"))
        ds.acknowledge("alert-test-1", role="nurse")
        assert ds.get_nurse_queue() == []

    def test_unknown_role_raises(self):
        ds = DashboardService()
        with pytest.raises(InvalidRoleError):
            ds.acknowledge("alert-1", role="admin")

    def test_acknowledge_nonexistent_alert(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("queue_for_nurse"))
        ds.acknowledge("nonexistent", role="nurse")  # Should not raise
        assert len(ds.get_nurse_queue()) == 1  # Original still there


class TestFeedback:
    def test_forwards_outcome_to_meta_sentinel(self):
        meta = MagicMock()
        ds = DashboardService(meta_sentinel=meta)
        ds.report_feedback("alert-1", "false_positive")
        meta.record_outcome.assert_called_once_with("alert-1", "false_positive")

    def test_forwards_corrections_to_veritas(self):
        veritas = MagicMock()
        ds = DashboardService(veritas_agent=veritas)
        ds.report_feedback(
            "alert-1",
            "false_positive",
            data_corrections={"ehr_data.diagnoses": "human_confirmed"},
            patient_id="p1",
        )
        veritas.update_provenance_override.assert_called_once()


class TestDeliveryLog:
    def test_log_populated(self):
        ds = DashboardService()
        ds.route_decision(_make_decision("queue_for_nurse"))
        log = ds.get_delivery_log()
        assert len(log) >= 1
        assert log[0]["alert_id"] == "alert-test-1"
