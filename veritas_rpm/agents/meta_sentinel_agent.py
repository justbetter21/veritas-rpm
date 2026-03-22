"""
meta_sentinel_agent.py — MetaSentinelAgent: the aggregator and decision maker.

Responsibility
--------------
MetaSentinelAgent is the final decision-making layer before any output reaches
a human being.  It receives a CandidateAlert and the list of AgentClaims
produced by the specialist agents, synthesises them, and returns a single
SystemDecision.

Key responsibilities
--------------------
1. Aggregating multiple AgentClaims that may disagree with each other.
2. Applying cooldown / debouncing to avoid over-alerting human staff.
3. Determining the target role (patient, nurse, or doctor) and priority level.
4. Logging outcome labels supplied by clinicians for performance monitoring.

Cooldown policy
---------------
For each patient, MetaSentinelAgent tracks the last time a SystemDecision was
sent to each target role.  If a new decision is generated within the cooldown
window, it is withheld unless the risk is 'critical'.  This protects clinicians
from continuous interruption while ensuring that genuinely critical events
are never suppressed.

The cooldown duration is configurable via ``CooldownConfig`` (default: 30
minutes for doctor-level alerts, 15 minutes for nurse-level).  These defaults
are placeholders — the exact values used in production are considered
proprietary configuration.

Proprietary boundary
--------------------
The ``_synthesise_claims()`` method contains only a TODO placeholder.  In
production this would encode the weighting, voting, or ensemble logic used to
derive the final action and priority from a set of potentially conflicting
claims.  Only the input/output contract is defined here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from veritas_rpm.config import CooldownConfig
from veritas_rpm.models import (
    AgentClaim,
    CandidateAlert,
    DecisionMeta,
    FinalAction,
    Priority,
    SystemDecision,
    TargetRole,
)

logger = logging.getLogger(__name__)


class MetaSentinelAgent:
    """
    Aggregates AgentClaims and produces a single SystemDecision per alert.

    Usage
    -----
    meta = MetaSentinelAgent()
    director = DirectorAgent(meta_sentinel=meta)

    # Decisions are routed automatically when DirectorAgent calls:
    #   meta.aggregate_claims(alert, claims)

    # To receive the resulting SystemDecision, register a callback:
    meta.on_decision(lambda d: logger.info(d))

    # Or use in standalone mode:
    decision = meta.aggregate_claims(alert, claims)

    Performance monitoring
    ----------------------
    Clinicians can report outcomes (false positives, label corrections) via:
    meta.record_outcome(alert_id, label)
    These are stored in self._outcome_log for offline analysis.
    """

    def __init__(
        self,
        cooldown_config: Optional[CooldownConfig] = None,
        dashboard_service: Optional[object] = None,
        metrics: Optional[object] = None,
        # Legacy parameter — prefer cooldown_config
        cooldown_minutes: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Parameters
        ----------
        cooldown_config:
            Optional CooldownConfig dataclass.  Takes precedence over
            ``cooldown_minutes`` if both are provided.
        dashboard_service:
            A DashboardService instance.  If provided, each SystemDecision is
            automatically routed via ``dashboard_service.route_decision()``.
            Pass None to use MetaSentinelAgent in standalone mode.
        metrics:
            A PipelineMetrics instance for recording decision counts.
        cooldown_minutes:
            Legacy dict mapping target role to cooldown duration in minutes.
            Deprecated in favour of ``cooldown_config``.
        """
        if cooldown_config is not None:
            self._cooldown_minutes = cooldown_config.as_dict()
        elif cooldown_minutes is not None:
            self._cooldown_minutes = cooldown_minutes
        else:
            self._cooldown_minutes = CooldownConfig().as_dict()

        self._dashboard_service = dashboard_service
        self._metrics = metrics

        # Cooldown state: {patient_id: {target_role: cooldown_until_datetime}}
        self._cooldown_state: Dict[str, Dict[str, datetime]] = {}

        # Outcome log: {alert_id: label}  — populated by clinician feedback
        self._outcome_log: Dict[str, str] = {}

        # Optional decision callback (e.g. for testing or monitoring)
        self._decision_callbacks: List = []

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def on_decision(self, callback) -> None:
        """
        Register a callback to be called whenever a SystemDecision is produced.

        Parameters
        ----------
        callback:
            Callable that accepts a single SystemDecision argument.
        """
        self._decision_callbacks.append(callback)

    def _emit_decision(self, decision: SystemDecision) -> None:
        for cb in self._decision_callbacks:
            cb(decision)

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def aggregate_claims(
        self,
        alert: CandidateAlert,
        claims: List[AgentClaim],
    ) -> SystemDecision:
        """
        Synthesise AgentClaims into a single SystemDecision.

        This is the main entry point called by DirectorAgent.  It:
        1. Synthesises the claims into a proposed final_action and priority.
        2. Determines the target role (patient, nurse, doctor).
        3. Applies cooldown logic: suppresses or delays the decision if the
           patient has been recently alerted, unless risk is 'critical'.
        4. Constructs and returns a SystemDecision.
        5. Routes the decision to DashboardService (if configured).

        Parameters
        ----------
        alert:
            The CandidateAlert that triggered this decision.
        claims:
            List of AgentClaims from the specialist agents.  May be empty
            if no agents were selected or all raised exceptions.

        Returns
        -------
        SystemDecision
            The final, actionable decision for this alert.
        """
        # Step 1: Synthesise claims into proposed action and priority
        proposed_action, proposed_priority, participating = self._synthesise_claims(
            alert, claims
        )

        # Step 2: Determine target role from proposed action
        target_role = self._action_to_role(proposed_action)

        # Step 3: Apply cooldown logic
        final_action, final_priority, cooldown_until = self._apply_cooldown(
            patient_id=alert.patient_id,
            proposed_action=proposed_action,
            proposed_priority=proposed_priority,
            target_role=target_role,
            claims=claims,
        )

        # Step 4: Build decision
        decision = SystemDecision(
            alert_id=alert.alert_id,
            final_action=final_action,
            target_role=target_role,
            priority=final_priority,
            cooldown_until=cooldown_until,
            meta=DecisionMeta(
                timestamp=datetime.now(timezone.utc),
                participating_agents=participating,
            ),
        )

        # Step 5: Record metrics
        if self._metrics is not None:
            self._metrics.record_decision(decision)

        # Step 6: Route to dashboard and notify callbacks
        if self._dashboard_service is not None:
            self._dashboard_service.route_decision(decision)
        self._emit_decision(decision)

        logger.info(
            "Decision produced: alert=%s action=%s priority=%s",
            alert.alert_id[:16],
            decision.final_action,
            decision.priority,
        )

        return decision

    # ------------------------------------------------------------------
    # Claim synthesis (proprietary logic placeholder)
    # ------------------------------------------------------------------

    def _synthesise_claims(
        self,
        alert: CandidateAlert,
        claims: List[AgentClaim],
    ) -> Tuple[FinalAction, Priority, List[str]]:
        """
        Derive the proposed final_action and priority from the set of claims.

        This is the heart of MetaSentinelAgent's decision logic.  In a
        production implementation this method would encode the ensemble or
        voting strategy used to reconcile potentially conflicting claims from
        different specialist agents.

        TODO
        ----
        Replace the placeholder logic below with the proprietary synthesis
        algorithm:

        - Define how conflicting recommended_actions are resolved (e.g. majority
          vote, maximum risk wins, weighted ensemble).
        - Define how risk_level values across agents are combined into a priority.
        - Handle the edge case where all claims recommend 'suppress' but one
          critical claim recommends escalation.
        - Consider provenance quality: low-trust context should widen the
          confidence interval of the decision.
        - Handle the empty-claims case gracefully.

        Returns
        -------
        Tuple of (final_action, priority, participating_agent_names)
        """
        participating = [c.agent_name for c in claims]

        if not claims:
            # No claims: default to conservative queuing for nurse review
            # TODO: Decide whether 'no claims' should suppress or queue.
            return "queue_for_nurse", "low", participating

        # TODO: Replace the following placeholder logic with the actual
        # claim-synthesis algorithm.
        #
        # Placeholder: use the claim with the highest risk_level as the
        # 'loudest voice'.  This is NOT a clinically validated strategy.
        risk_order = {"low": 0, "moderate": 1, "high": 2, "critical": 3}
        loudest = max(claims, key=lambda c: risk_order.get(c.risk_level, 0))

        proposed_action: FinalAction = loudest.recommended_action  # type: ignore[assignment]

        # TODO: Replace the following placeholder priority mapping.
        priority_map: Dict[str, Priority] = {
            "low": "low",
            "moderate": "normal",
            "high": "high",
            "critical": "urgent",
        }
        proposed_priority: Priority = priority_map.get(loudest.risk_level, "normal")  # type: ignore[assignment]

        return proposed_action, proposed_priority, participating

    # ------------------------------------------------------------------
    # Cooldown enforcement
    # ------------------------------------------------------------------

    def _apply_cooldown(
        self,
        patient_id: str,
        proposed_action: FinalAction,
        proposed_priority: Priority,
        target_role: TargetRole,
        claims: List[AgentClaim],
    ) -> Tuple[FinalAction, Priority, Optional[datetime]]:
        """
        Apply the cooldown policy to the proposed action.

        If the patient was recently alerted at the same or higher level, the
        action is downgraded to 'suppress' unless the risk is 'critical'.

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        proposed_action:
            The action proposed by ``_synthesise_claims``.
        proposed_priority:
            The priority proposed by ``_synthesise_claims``.
        target_role:
            The human role that would receive this decision.
        claims:
            The full list of AgentClaims (used to check for 'critical' risk).

        Returns
        -------
        Tuple of (final_action, final_priority, cooldown_until)
            If suppressed by cooldown, final_action is 'suppress'.
            cooldown_until is the new cooldown expiry set for this role,
            or None if no cooldown applies.
        """
        now = datetime.now(timezone.utc)

        # Check if patient is currently under cooldown for this role
        patient_cooldowns = self._cooldown_state.get(patient_id, {})
        cooldown_expiry = patient_cooldowns.get(str(target_role))

        is_critical = any(c.risk_level == "critical" for c in claims)

        if cooldown_expiry is not None and now < cooldown_expiry and not is_critical:
            # Within cooldown window and not critical: suppress
            logger.info(
                "Alert suppressed by cooldown for patient=%s role=%s "
                "(expires %s)",
                patient_id,
                target_role,
                cooldown_expiry.isoformat(),
            )
            return "suppress", "low", None

        # Outside cooldown (or critical): proceed and set a new cooldown
        cooldown_duration = self._cooldown_minutes.get(str(target_role), 15)
        new_cooldown_until = now + timedelta(minutes=cooldown_duration)

        if patient_id not in self._cooldown_state:
            self._cooldown_state[patient_id] = {}
        self._cooldown_state[patient_id][str(target_role)] = new_cooldown_until

        return proposed_action, proposed_priority, new_cooldown_until

    # ------------------------------------------------------------------
    # Role mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _action_to_role(action: FinalAction) -> TargetRole:
        """
        Map a FinalAction to the appropriate TargetRole.

        This is a deterministic mapping that defines who receives the alert.

        TODO
        ----
        Verify that this mapping matches the organisational escalation policy
        in your deployment context.
        """
        mapping: Dict[FinalAction, TargetRole] = {
            "suppress": "patient",          # No delivery; target_role unused
            "notify_patient": "patient",
            "queue_for_nurse": "nurse",
            "escalate_to_doctor": "doctor",
        }
        return mapping.get(action, "nurse")  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Performance monitoring
    # ------------------------------------------------------------------

    def record_outcome(self, alert_id: str, label: str) -> None:
        """
        Record a clinician-supplied outcome label for an alert.

        This is called by DashboardService when a clinician reviews a decision
        and provides feedback (e.g. 'false_positive_exertion', 'true_positive',
        'false_positive_probe').

        The outcome log can be exported for offline model evaluation and
        feedback loop training.

        Parameters
        ----------
        alert_id:
            The alert_id of the SystemDecision being labelled.
        label:
            A free-text or structured label describing the clinical outcome.
        """
        self._outcome_log[alert_id] = label

    def get_outcome_log(self) -> Dict[str, str]:
        """
        Return the current outcome log.

        Returns
        -------
        Dict[str, str]
            Mapping of alert_id → outcome label for all labelled alerts.
        """
        return dict(self._outcome_log)
