"""
dashboard_service.py — DashboardService: the human-facing delivery layer.

Responsibility
--------------
DashboardService is the boundary between the automated pipeline and the
humans who act on its outputs.  It:

1. Receives SystemDecision objects from MetaSentinelAgent.
2. Routes each decision to the correct human role (patient, nurse, doctor).
3. Maintains queues so that nurses can review alerts intermittently rather
   than being interrupted continuously.
4. Accepts feedback from clinicians (false positive labels, data corrections)
   and propagates corrections back to VeritasAgent.

Human workflow model
--------------------
- Patients receive lightweight notifications (e.g. 'check your probe').
- Nurses see a queue of pending decisions and review them on their schedule.
- Doctors see only high/urgent decisions that require immediate attention.

None of the queue logic below is connected to real infrastructure.  In a
production system the queues would be backed by a database and the delivery
methods would call push-notification APIs, EHR-integrated dashboards, etc.

Design note
-----------
DashboardService deliberately knows nothing about clinical thresholds or
decision logic.  It acts purely on the final_action and priority fields of
the SystemDecision it receives.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, List, Optional

from veritas_rpm.models import SystemDecision


class DashboardService:
    """
    Routes SystemDecisions to human roles and handles clinician feedback.

    Usage
    -----
    dashboard = DashboardService(veritas_agent=agent, meta_sentinel=meta)

    # Automatic routing when MetaSentinelAgent passes decisions:
    #   meta = MetaSentinelAgent(dashboard_service=dashboard)

    # Manual routing:
    dashboard.route_decision(system_decision)

    # Nurse reviews their queue:
    pending = dashboard.get_nurse_queue()

    # Doctor acknowledges an alert:
    dashboard.acknowledge(alert_id, role='doctor')

    # Clinician labels a false positive:
    dashboard.report_feedback(alert_id, label='false_positive_exertion',
                              data_corrections={'vital_signs.spo2': 'human_confirmed'})
    """

    def __init__(
        self,
        veritas_agent: Optional[object] = None,
        meta_sentinel: Optional[object] = None,
    ) -> None:
        """
        Parameters
        ----------
        veritas_agent:
            A VeritasAgent instance.  Used to propagate provenance corrections
            when a clinician confirms or corrects data.  Optional.
        meta_sentinel:
            A MetaSentinelAgent instance.  Used to record outcome labels for
            performance monitoring.  Optional.
        """
        self._veritas_agent = veritas_agent
        self._meta_sentinel = meta_sentinel

        # In-memory queues per role
        self._patient_queue: Deque[SystemDecision] = deque()
        self._nurse_queue: Deque[SystemDecision] = deque()
        self._doctor_queue: Deque[SystemDecision] = deque()

        # Acknowledged alert IDs
        self._acknowledged: Dict[str, Dict] = {}

        # Delivery log for auditability
        self._delivery_log: List[Dict] = []

    # ------------------------------------------------------------------
    # Primary routing interface
    # ------------------------------------------------------------------

    def route_decision(self, decision: SystemDecision) -> None:
        """
        Route a SystemDecision to the appropriate human role.

        Called automatically by MetaSentinelAgent (if dashboard_service is
        configured) or manually by test code.

        Routing rules (based on final_action):
        - 'suppress'          → Decision is logged but not delivered.
        - 'notify_patient'    → Delivered to the patient queue.
        - 'queue_for_nurse'   → Added to the nurse review queue.
        - 'escalate_to_doctor' → Added to the doctor queue immediately.

        Parameters
        ----------
        decision:
            The SystemDecision to route.
        """
        self._log_delivery(decision, "received")

        if decision.final_action == "suppress":
            self._log_delivery(decision, "suppressed")
            return

        if decision.final_action == "notify_patient":
            self.notify_patient(decision)

        elif decision.final_action == "queue_for_nurse":
            self.queue_for_nurse(decision)

        elif decision.final_action == "escalate_to_doctor":
            self.escalate_to_doctor(decision)

    def notify_patient(self, decision: SystemDecision) -> None:
        """
        Deliver a SystemDecision as a patient-facing notification.

        In production this would trigger a push notification or in-app message.
        Here it simply adds the decision to the patient queue.

        Parameters
        ----------
        decision:
            The SystemDecision to deliver.
        """
        self._patient_queue.append(decision)
        self._log_delivery(decision, "delivered_to_patient")
        print(
            f"[DashboardService] PATIENT NOTIFICATION — "
            f"alert_id={decision.alert_id}  "
            f"priority={decision.priority}"
        )

    def queue_for_nurse(self, decision: SystemDecision) -> None:
        """
        Add a SystemDecision to the nurse review queue.

        Nurses review this queue intermittently.  Decisions are not pushed
        to individual nurses in real time; instead, the queue is surfaced on
        the nursing dashboard at the nurse's next review interval.

        Parameters
        ----------
        decision:
            The SystemDecision to queue.
        """
        self._nurse_queue.append(decision)
        self._log_delivery(decision, "queued_for_nurse")
        print(
            f"[DashboardService] NURSE QUEUE — "
            f"alert_id={decision.alert_id}  "
            f"priority={decision.priority}  "
            f"queue_depth={len(self._nurse_queue)}"
        )

    def escalate_to_doctor(self, decision: SystemDecision) -> None:
        """
        Escalate a high-priority SystemDecision directly to the doctor.

        This is reserved for 'high' or 'urgent' priority decisions.  In
        production this would trigger an immediate push notification or
        bleep/pager alert.

        Parameters
        ----------
        decision:
            The SystemDecision to escalate.
        """
        self._doctor_queue.append(decision)
        self._log_delivery(decision, "escalated_to_doctor")
        print(
            f"[DashboardService] DOCTOR ESCALATION — "
            f"alert_id={decision.alert_id}  "
            f"priority={decision.priority}  "
            f"cooldown_until={decision.cooldown_until}"
        )

    # ------------------------------------------------------------------
    # Queue inspection
    # ------------------------------------------------------------------

    def get_patient_queue(self) -> List[SystemDecision]:
        """Return all pending patient notifications (non-destructive)."""
        return list(self._patient_queue)

    def get_nurse_queue(self) -> List[SystemDecision]:
        """Return all pending nurse-review decisions (non-destructive)."""
        return list(self._nurse_queue)

    def get_doctor_queue(self) -> List[SystemDecision]:
        """Return all pending doctor escalations (non-destructive)."""
        return list(self._doctor_queue)

    def acknowledge(self, alert_id: str, role: str) -> None:
        """
        Mark a decision as acknowledged by a human reviewer.

        Removes the decision from the relevant queue and logs the
        acknowledgement with a timestamp.

        Parameters
        ----------
        alert_id:
            The alert_id of the SystemDecision being acknowledged.
        role:
            The role of the acknowledging clinician ('patient', 'nurse',
            or 'doctor').
        """
        queue_map = {
            "patient": self._patient_queue,
            "nurse": self._nurse_queue,
            "doctor": self._doctor_queue,
        }
        queue = queue_map.get(role)
        if queue is None:
            raise ValueError(f"Unknown role: '{role}'.  Must be patient, nurse, or doctor.")

        # Find and remove from queue
        for i, decision in enumerate(queue):
            if decision.alert_id == alert_id:
                # deque doesn't support index-based removal; convert temporarily
                items = list(queue)
                items.pop(i)
                queue.clear()
                queue.extend(items)
                self._acknowledged[alert_id] = {
                    "role": role,
                    "acknowledged_at": datetime.now(timezone.utc).isoformat(),
                }
                print(
                    f"[DashboardService] ACKNOWLEDGED by {role} — "
                    f"alert_id={alert_id}"
                )
                return

        print(
            f"[DashboardService] WARNING: alert_id={alert_id} not found in "
            f"{role} queue (may already be acknowledged)."
        )

    # ------------------------------------------------------------------
    # Clinician feedback interface
    # ------------------------------------------------------------------

    def report_feedback(
        self,
        alert_id: str,
        label: str,
        data_corrections: Optional[Dict[str, str]] = None,
        patient_id: Optional[str] = None,
    ) -> None:
        """
        Record clinician feedback for a delivered SystemDecision.

        This serves two purposes:
        1. Performance monitoring: the label is forwarded to MetaSentinelAgent
           so that false-positive rates and other metrics can be tracked.
        2. Provenance correction: if the clinician supplies data_corrections,
           these are forwarded to VeritasAgent so that future VeritasRecords
           for this patient carry the updated provenance.

        Parameters
        ----------
        alert_id:
            The alert_id of the decision being labelled.
        label:
            Clinician-supplied outcome label.  Examples:
            'true_positive', 'false_positive_exertion',
            'false_positive_probe', 'false_positive_medication_effect'.
        data_corrections:
            Optional dict of {field_path: ProvenanceTag} corrections to apply
            to future VeritasRecords for this patient.  Example:
            {'ehr_data.diagnoses': 'human_confirmed'} when a clinician
            confirms a COPD diagnosis that was previously LLM_extracted.
        patient_id:
            The patient_id associated with the alert.  Required when
            data_corrections are supplied, so VeritasAgent can apply the
            right patient's overrides.
        """
        print(
            f"[DashboardService] FEEDBACK — alert_id={alert_id}  label={label}"
        )

        # Forward outcome label to MetaSentinelAgent for monitoring
        if self._meta_sentinel is not None:
            self._meta_sentinel.record_outcome(alert_id, label)

        # Forward provenance corrections to VeritasAgent
        if data_corrections and self._veritas_agent is not None:
            if patient_id is None:
                import warnings
                warnings.warn(
                    "data_corrections supplied without patient_id — "
                    "provenance corrections cannot be applied without a patient_id.",
                    stacklevel=2,
                )
            else:
                self._veritas_agent.update_provenance_override(
                    patient_id, data_corrections  # type: ignore[arg-type]
                )
                print(
                    f"[DashboardService] Provenance updated for patient "
                    f"'{patient_id}': {data_corrections}"
                )

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    def _log_delivery(self, decision: SystemDecision, status: str) -> None:
        """Append an entry to the internal delivery log."""
        self._delivery_log.append(
            {
                "alert_id": decision.alert_id,
                "final_action": decision.final_action,
                "priority": decision.priority,
                "target_role": decision.target_role,
                "status": status,
                "logged_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def get_delivery_log(self) -> List[Dict]:
        """Return a copy of the full delivery log for auditability."""
        return list(self._delivery_log)
