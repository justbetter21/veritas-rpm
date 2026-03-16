"""
veritas_rpm — Public reference implementation of the Veritas-Sentinel-Director-MetaSentinel
architecture for Remote Patient Monitoring (RPM).

This package is an educational/research framework only.
It is NOT a certified medical device and MUST NOT be used for clinical decision-making.

Package layout
--------------
veritas_rpm/
    models.py                   Core data models (VeritasRecord, CandidateAlert,
                                AgentClaim, SystemDecision)
    pipeline.py                 Top-level orchestrator that wires all agents together
    agents/
        veritas_agent.py        Ingests the four ground-truth sources; emits VeritasRecord
        sentinel_layer.py       Detects candidate issues; emits CandidateAlert
        director_agent.py       Routes alerts to the right specialist agents
        specialist_agents.py    Specialist agents (Tachycardia, Bradycardia, COPD, …)
        meta_sentinel_agent.py  Aggregates AgentClaims into a SystemDecision
    services/
        dashboard_service.py    Routes SystemDecisions to patient / nurse / doctor
"""

from veritas_rpm.models import (
    VeritasRecord,
    CandidateAlert,
    AgentClaim,
    SystemDecision,
)
from veritas_rpm.pipeline import RPMPipeline

__all__ = [
    "VeritasRecord",
    "CandidateAlert",
    "AgentClaim",
    "SystemDecision",
    "RPMPipeline",
]
