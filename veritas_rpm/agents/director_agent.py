"""
director_agent.py — DirectorAgent: the alert router.

Responsibility
--------------
DirectorAgent sits between SentinelLayer and the specialist agents.  When it
receives a CandidateAlert it decides which subset of specialist agents are
relevant, calls each one, collects the resulting AgentClaims, and forwards
them to MetaSentinelAgent.

Design principles
-----------------
- DirectorAgent owns references to all specialist agents.
- It selects agents based on alert_type and available context — not all agents
  are relevant to every alert type.
- It enforces a consistent interface: every selected agent is called with the
  same signature (evaluate(alert, context)) and returns an AgentClaim.
- It never makes clinical decisions itself; it only routes and collects.

Routing logic (proprietary boundary)
--------------------------------------
The method ``_select_agents()`` contains a placeholder routing table.  In
production this would encode the exact rules for which specialist agents should
be activated for each alert type and what contextual factors (e.g. COPD
diagnosis) trigger additional agents.  Only the structure is shown here.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from veritas_rpm.agents.specialist_agents import (
    ActivityIntegrityAgent,
    BradycardiaAgent,
    COPDAgent,
    NocturnalAgent,
    ProbeIntegrityAgent,
    SpecialistAgent,
    TachycardiaAgent,
)
from veritas_rpm.models import (
    AgentClaim,
    AlertType,
    CandidateAlert,
    VeritasRecord,
)


class DirectorAgent:
    """
    Routes CandidateAlerts to the appropriate specialist agents and
    collects their AgentClaims for MetaSentinelAgent.

    Usage
    -----
    director = DirectorAgent(meta_sentinel)

    # DirectorAgent is passed to SentinelLayer so it can receive alerts:
    sentinel = SentinelLayer(director=director)

    # Or call directly:
    claims = director.handle_alert(candidate_alert)
    """

    def __init__(self, meta_sentinel: Optional[object] = None) -> None:
        """
        Parameters
        ----------
        meta_sentinel:
            A MetaSentinelAgent instance.  If provided, collected AgentClaims
            are automatically forwarded via ``meta_sentinel.aggregate_claims()``.
            Pass None to use DirectorAgent in standalone mode.
        """
        self._meta_sentinel = meta_sentinel

        # Instantiate all specialist agents
        self._tachycardia_agent = TachycardiaAgent()
        self._bradycardia_agent = BradycardiaAgent()
        self._copd_agent = COPDAgent()
        self._nocturnal_agent = NocturnalAgent()
        self._activity_integrity_agent = ActivityIntegrityAgent()
        self._probe_integrity_agent = ProbeIntegrityAgent()

        # Maintain a context cache: patient_id → most recent VeritasRecord.
        # DirectorAgent needs the VeritasRecord to pass as context to specialists.
        # This is populated via update_context().
        self._context_cache: Dict[str, VeritasRecord] = {}

    # ------------------------------------------------------------------
    # Context management
    # ------------------------------------------------------------------

    def update_context(self, record: VeritasRecord) -> None:
        """
        Store the most recent VeritasRecord for a patient.

        SentinelLayer (or the pipeline orchestrator) should call this whenever
        a new VeritasRecord is available so that DirectorAgent can pass up-to-
        date context to specialist agents.

        Parameters
        ----------
        record:
            The latest VeritasRecord for the patient.
        """
        self._context_cache[record.patient_id] = record

    # ------------------------------------------------------------------
    # Primary interface
    # ------------------------------------------------------------------

    def handle_alert(self, alert: CandidateAlert) -> List[AgentClaim]:
        """
        Process a CandidateAlert received from SentinelLayer.

        Steps:
        1. Look up the most recent VeritasRecord for the alert's patient.
        2. Select the relevant specialist agents for this alert type.
        3. Call each selected agent's evaluate() method.
        4. Collect the resulting AgentClaims.
        5. Forward claims to MetaSentinelAgent (if configured).

        Parameters
        ----------
        alert:
            The CandidateAlert to process.

        Returns
        -------
        List[AgentClaim]
            Claims produced by all selected specialist agents.

        Notes
        -----
        If no VeritasRecord is available for the patient (update_context has
        not been called), a minimal empty record is constructed as a fallback
        so the pipeline does not crash.  In production, this situation should
        be logged and investigated.
        """
        context = self._context_cache.get(alert.patient_id)
        if context is None:
            import warnings
            warnings.warn(
                f"No VeritasRecord context available for patient '{alert.patient_id}'.  "
                "Specialist agents will have no EHR/conversation context.  "
                "Call update_context() before handle_alert() in production.",
                stacklevel=2,
            )
            # Construct a minimal context so agents can still run
            from datetime import datetime, timezone
            from veritas_rpm.models import VeritasRecord
            import uuid
            context = VeritasRecord(
                record_id=str(uuid.uuid4()),
                patient_id=alert.patient_id,
                timestamp=datetime.now(timezone.utc),
                provenance={},
            )

        selected = self._select_agents(alert, context)
        claims = self._invoke_agents(selected, alert, context)

        if self._meta_sentinel is not None:
            self._meta_sentinel.aggregate_claims(alert, claims)

        return claims

    # ------------------------------------------------------------------
    # Agent selection (proprietary routing logic)
    # ------------------------------------------------------------------

    def _select_agents(
        self,
        alert: CandidateAlert,
        context: VeritasRecord,
    ) -> List[SpecialistAgent]:
        """
        Choose which specialist agents should evaluate this alert.

        The routing table maps alert_type to a base set of agents.
        Additional agents are added when contextual factors (such as a COPD
        diagnosis) make them relevant.

        TODO
        ----
        Replace the placeholder routing rules below with the production
        routing policy:

        - Define exactly which agents handle each alert_type.
        - Add conditional logic: e.g. if 'COPD' in ehr_data.diagnoses, always
          include COPDAgent for desaturation and flatline alerts.
        - Add confidence-based routing: e.g. if signal quality is poor, always
          include ProbeIntegrityAgent regardless of alert_type.
        - Consider alert provenance: if only device_stream is available (no
          EHR or conversation context), adjust which agents are useful.

        Parameters
        ----------
        alert:
            The incoming CandidateAlert.
        context:
            The current VeritasRecord for contextual routing decisions.

        Returns
        -------
        List[SpecialistAgent]
            The subset of agents to invoke.
        """
        # Default routing table (placeholder — not clinically tuned)
        routing: Dict[str, List[SpecialistAgent]] = {
            "tachycardia": [
                self._tachycardia_agent,
                self._activity_integrity_agent,
                self._probe_integrity_agent,
            ],
            "bradycardia": [
                self._bradycardia_agent,
                self._nocturnal_agent,
            ],
            "desaturation": [
                self._probe_integrity_agent,
                self._copd_agent,
                self._nocturnal_agent,
            ],
            "flatline": [
                self._probe_integrity_agent,
            ],
            "nocturnal_event": [
                self._nocturnal_agent,
                self._copd_agent,
                self._probe_integrity_agent,
            ],
            "probe_issue": [
                self._probe_integrity_agent,
                self._activity_integrity_agent,
            ],
            "activity_spike": [
                self._activity_integrity_agent,
                self._tachycardia_agent,
            ],
            "other": [
                self._tachycardia_agent,
                self._bradycardia_agent,
                self._probe_integrity_agent,
            ],
        }

        base_agents = routing.get(alert.alert_type, [])

        # TODO: Add context-based conditional routing.
        # Example (placeholder — exact conditions are proprietary):
        #
        # diagnoses = [d.lower() for d in context.ehr_data.diagnoses]
        # if any("copd" in d for d in diagnoses):
        #     if self._copd_agent not in base_agents:
        #         base_agents = base_agents + [self._copd_agent]

        return base_agents

    # ------------------------------------------------------------------
    # Agent invocation
    # ------------------------------------------------------------------

    def _invoke_agents(
        self,
        agents: List[SpecialistAgent],
        alert: CandidateAlert,
        context: VeritasRecord,
    ) -> List[AgentClaim]:
        """
        Call evaluate() on each selected agent and collect the results.

        Errors from individual agents are caught and logged rather than allowed
        to propagate — a single faulty agent should not prevent others from
        contributing their claims.

        Parameters
        ----------
        agents:
            The specialist agents to invoke.
        alert:
            The CandidateAlert being evaluated.
        context:
            The current VeritasRecord to pass as context.

        Returns
        -------
        List[AgentClaim]
            All successfully produced claims.
        """
        claims: List[AgentClaim] = []
        for agent in agents:
            try:
                claim = agent.evaluate(alert, context)
                claims.append(claim)
            except Exception as exc:  # noqa: BLE001
                import warnings
                warnings.warn(
                    f"Agent '{agent.name}' raised an exception while evaluating "
                    f"alert '{alert.alert_id}': {exc}",
                    stacklevel=2,
                )
        return claims
