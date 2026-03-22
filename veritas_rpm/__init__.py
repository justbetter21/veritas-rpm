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
    config.py                   Configuration dataclasses (PipelineConfig, CooldownConfig,
                                RoutingConfig)
    exceptions.py               Custom exception hierarchy (VeritasRPMError, …)
    metrics.py                  Pipeline-level metrics (PipelineMetrics)
    pipeline.py                 Top-level orchestrator that wires all agents together
    async_pipeline.py           Async variant of the pipeline orchestrator
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
from veritas_rpm.config import (
    PipelineConfig,
    CooldownConfig,
    RoutingConfig,
)
from veritas_rpm.exceptions import (
    VeritasRPMError,
    NoDataIngestedError,
    InvalidRoleError,
    ValidationError,
    AgentEvaluationError,
)
from veritas_rpm.metrics import PipelineMetrics
from veritas_rpm.pipeline import RPMPipeline

__all__ = [
    # Models
    "VeritasRecord",
    "CandidateAlert",
    "AgentClaim",
    "SystemDecision",
    # Config
    "PipelineConfig",
    "CooldownConfig",
    "RoutingConfig",
    # Exceptions
    "VeritasRPMError",
    "NoDataIngestedError",
    "InvalidRoleError",
    "ValidationError",
    "AgentEvaluationError",
    # Metrics
    "PipelineMetrics",
    # Pipeline
    "RPMPipeline",
]
