"""
models.py — Core data models for the Veritas-RPM reference implementation.

Each class corresponds directly to one of the four JSON schemas defined in the
architecture specification.  Pydantic v2 is used for validation and serialisation.

Data flow summary
-----------------
VeritasRecord  →  CandidateAlert  →  AgentClaim (×N)  →  SystemDecision

All clinical decision logic is intentionally absent from these models.
They are plain data containers with no embedded thresholds or rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Provenance vocabulary
# ---------------------------------------------------------------------------

ProvenanceTag = Literal[
    "EHR_verified",
    "LLM_extracted_unconfirmed",
    "LLM_extracted_dual_confirmed",
    "human_confirmed",
    "device_stream",
]
"""
A provenance tag describes *how* a piece of information was obtained and
how much trust should be placed in it.  Downstream agents can inspect
provenance to decide how confidently they can interpret a field.

Tags (ordered roughly from most to least trustworthy):
    EHR_verified                Data was read directly from a structured EHR record.
    human_confirmed             A clinician explicitly confirmed the value.
    LLM_extracted_dual_confirmed  An LLM extracted the value and a second pass agreed.
    LLM_extracted_unconfirmed   An LLM extracted the value; no secondary confirmation.
    device_stream               Data arrived live from an RPM device with no further
                                validation.
"""


# ---------------------------------------------------------------------------
# Sub-objects used inside VeritasRecord
# ---------------------------------------------------------------------------

class EHRData(BaseModel):
    """Historical data drawn from the patient's Electronic Health Record."""

    diagnoses: List[str] = Field(
        default_factory=list,
        description="List of active or relevant diagnoses (free-text labels).",
    )
    medications: List[str] = Field(
        default_factory=list,
        description="Current medications (free-text, e.g. 'Metoprolol 25 mg OD').",
    )
    baseline_spo2: Optional[float] = Field(
        None,
        description=(
            "Patient's known baseline SpO₂ percentage when stable.  "
            "Used by specialist agents to contextualise live readings.  "
            "May be None if not recorded."
        ),
    )
    baseline_hr: Optional[float] = Field(
        None,
        description=(
            "Patient's known baseline resting heart rate (bpm).  "
            "May be None if not recorded."
        ),
    )
    recent_admissions: List[str] = Field(
        default_factory=list,
        description="Free-text summaries of hospital admissions in the recent period.",
    )

    model_config = {"extra": "allow"}


class ConversationData(BaseModel):
    """
    Data collected from structured or semi-structured daily patient conversations.

    This source captures the patient's *subjective* experience: what symptoms
    they report, what they have been doing, and whether they are taking their
    medications.  Content is typically obtained via a conversational interface and
    may have been processed by an LLM to extract structured fields — hence the
    provenance may be LLM_extracted_*.
    """

    symptoms: List[str] = Field(
        default_factory=list,
        description="Patient-reported symptoms (e.g. 'shortness of breath', 'fatigue').",
    )
    activities: List[str] = Field(
        default_factory=list,
        description="Activities the patient reports having done (e.g. 'walked 20 min').",
    )
    adherence_notes: str = Field(
        default="",
        description="Free-text notes on medication or care-plan adherence.",
    )

    model_config = {"extra": "allow"}


class VitalSigns(BaseModel):
    """
    Near-real-time physiological data streamed from an RPM device.

    This is the primary input for the SentinelLayer's signal detectors.
    All values may be None if the device is not transmitting (e.g. probe off).
    """

    hr: Optional[float] = Field(None, description="Heart rate in beats per minute.")
    spo2: Optional[float] = Field(None, description="Peripheral oxygen saturation (%).")
    resp_rate: Optional[float] = Field(
        None, description="Respiratory rate in breaths per minute."
    )
    signal_quality: Optional[str] = Field(
        None,
        description=(
            "Device-reported signal quality indicator "
            "(e.g. 'good', 'poor', 'no_signal').  "
            "Used by ProbeIntegrityAgent."
        ),
    )
    activity_level: Optional[str] = Field(
        None,
        description=(
            "Activity level reported by the device accelerometer "
            "(e.g. 'resting', 'light', 'moderate', 'vigorous').  "
            "Used by ActivityIntegrityAgent to contextualise vital-sign readings."
        ),
    )

    model_config = {"extra": "allow"}


class PatientInput(BaseModel):
    """
    Immediate ground-truth statements made by the patient via a 'speak now' interface.

    When present, this source takes high priority because it represents the
    patient's direct, real-time report — for example 'the probe fell off' or
    'I feel very dizzy'.  This can cause the MetaSentinelAgent to override
    or suppress automated alerts.
    """

    free_text: str = Field(
        default="",
        description="Raw patient statement, exactly as entered.",
    )
    symptom_severity: Optional[str] = Field(
        None,
        description=(
            "Optional structured severity label extracted from free_text "
            "(e.g. 'mild', 'moderate', 'severe')."
        ),
    )

    model_config = {"extra": "allow"}


# ---------------------------------------------------------------------------
# VeritasRecord
# ---------------------------------------------------------------------------

class VeritasRecord(BaseModel):
    """
    A timestamped snapshot of everything known about a patient at a point in time.

    VeritasAgent assembles one of these objects each time the patient's state
    is updated — typically triggered by a new batch of vital-sign readings or
    a patient conversation event.

    Provenance
    ----------
    The ``provenance`` dict maps field names (or dot-separated paths like
    'ehr_data.baseline_spo2') to a ProvenanceTag.  Downstream agents MUST
    check provenance before using any field in a clinical assessment.  Fields
    with low-trust provenance (e.g. LLM_extracted_unconfirmed) should be
    treated as contextual hints rather than facts.

    What SentinelLayer sees
    -----------------------
    SentinelLayer subscribes to a stream of VeritasRecords.  It does NOT have
    direct access to the raw EHR text, conversation transcripts, or RPM device
    API.  All data arrives pre-packaged here.
    """

    record_id: str = Field(description="Unique identifier for this record.")
    patient_id: str = Field(description="Identifier of the patient this record describes.")
    timestamp: datetime = Field(description="UTC time at which this record was assembled.")

    ehr_data: EHRData = Field(
        default_factory=EHRData,
        description="Historical EHR context for this patient.",
    )
    conversation_data: ConversationData = Field(
        default_factory=ConversationData,
        description="Most-recent patient-conversation data.",
    )
    vital_signs: VitalSigns = Field(
        default_factory=VitalSigns,
        description="Current RPM vital-sign readings.",
    )
    patient_input: PatientInput = Field(
        default_factory=PatientInput,
        description="Any immediate patient statement received since the last record.",
    )
    provenance: Dict[str, ProvenanceTag] = Field(
        description=(
            "Per-field provenance tags.  Keys are field names or dot-paths; "
            "values are one of the ProvenanceTag literals."
        ),
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# CandidateAlert
# ---------------------------------------------------------------------------

AlertType = Literal[
    "tachycardia",
    "bradycardia",
    "desaturation",
    "flatline",
    "nocturnal_event",
    "probe_issue",
    "activity_spike",
    "other",
]


class AlertFeatures(BaseModel):
    """
    Aggregated vital-sign statistics computed over the alert time window.

    These are summary statistics, not the raw stream.  SentinelLayer computes
    them so that specialist agents receive a compact, consistent view of the
    event without needing to process raw time-series data.
    """

    min_spo2: Optional[float] = Field(None, description="Minimum SpO₂ in the window (%).")
    max_hr: Optional[float] = Field(None, description="Maximum HR in the window (bpm).")
    min_hr: Optional[float] = Field(None, description="Minimum HR in the window (bpm).")
    avg_hr: Optional[float] = Field(None, description="Mean HR in the window (bpm).")
    avg_spo2: Optional[float] = Field(None, description="Mean SpO₂ in the window (%).")
    signal_quality_summary: Optional[str] = Field(
        None, description="Dominant signal-quality label in the window."
    )
    activity_summary: Optional[str] = Field(
        None, description="Dominant activity-level label in the window."
    )

    model_config = {"extra": "allow"}


class AlertProvenanceSummary(BaseModel):
    """
    Provenance metadata attached to a CandidateAlert.

    Records which data sources were available and trusted when the alert was
    generated.  Specialist agents use this to weight their assessments — e.g.
    an alert backed only by device_stream with no human_confirmed context
    should be treated with more caution than one where EHR data confirms the
    patient's baseline.
    """

    vitals_source: Literal["device_stream"] = Field(
        "device_stream",
        description="Vital signs always come from the device stream.",
    )
    context_sources: List[
        Literal["EHR_verified", "LLM_extracted_dual_confirmed", "human_confirmed"]
    ] = Field(
        default_factory=list,
        description=(
            "Which higher-trust sources were available to contextualise the alert.  "
            "An empty list means the alert has no corroborating context."
        ),
    )

    model_config = {"extra": "allow"}


class CandidateAlert(BaseModel):
    """
    A potential clinical event detected by the SentinelLayer over a time window.

    SentinelLayer creates one of these whenever its signal detectors flag an
    anomaly in the VeritasRecord stream.  The alert does NOT contain raw data —
    only aggregated features and provenance metadata.

    DirectorAgent receives CandidateAlerts and is responsible for deciding
    which specialist agents should evaluate each one.
    """

    alert_id: str = Field(description="Unique identifier for this alert.")
    patient_id: str = Field(description="Patient this alert concerns.")
    alert_type: AlertType = Field(
        description="Category of the detected event."
    )
    start_time: datetime = Field(
        description="Start of the time window in which the event was observed."
    )
    end_time: datetime = Field(
        description="End of the time window in which the event was observed."
    )
    features: AlertFeatures = Field(
        default_factory=AlertFeatures,
        description="Aggregated statistics over the alert window.",
    )
    provenance_summary: AlertProvenanceSummary = Field(
        default_factory=AlertProvenanceSummary,
        description="Which data sources were available when this alert was generated.",
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# AgentClaim
# ---------------------------------------------------------------------------

RiskLevel = Literal["low", "moderate", "high", "critical"]
RecommendedAction = Literal[
    "suppress",
    "notify_patient",
    "queue_for_nurse",
    "escalate_to_doctor",
]


class AgentClaim(BaseModel):
    """
    A specialist agent's assessment of a single CandidateAlert.

    Each specialist agent that DirectorAgent invokes for an alert produces
    exactly one AgentClaim.  The claim encodes the agent's interpretation of
    the alert from its particular clinical perspective (e.g. TachycardiaAgent
    considers whether the elevated HR is consistent with known exertional
    patterns, while ProbeIntegrityAgent considers whether the signal quality
    suggests a hardware artefact).

    MetaSentinelAgent receives the full list of AgentClaims for an alert and
    synthesises them into a single SystemDecision.

    Important
    ---------
    ``classification`` is a free-text label coined by the agent (e.g.
    'benign_exertional_tachycardia').  It is NOT a medical diagnosis.
    ``risk_level`` and ``recommended_action`` are the machine-readable outputs
    that MetaSentinelAgent acts on.
    ``justification`` is a human-readable explanation for auditability.
    ``used_fields`` records which VeritasRecord fields influenced the claim,
    enabling provenance tracing.
    """

    alert_id: str = Field(description="ID of the CandidateAlert being assessed.")
    agent_name: str = Field(description="Canonical name of the agent producing this claim.")

    classification: str = Field(
        description=(
            "Agent-specific classification label.  Not a medical diagnosis.  "
            "Examples: 'benign_exertional_tachycardia', 'probable_probe_displacement', "
            "'chronic_copd_baseline', 'possible_clinical_deterioration'."
        )
    )
    risk_level: RiskLevel = Field(
        description="Agent's assessed risk level for this alert."
    )
    recommended_action: RecommendedAction = Field(
        description="Action the agent recommends MetaSentinelAgent takes."
    )
    justification: str = Field(
        default="",
        description=(
            "Human-readable explanation of how the agent reached its classification.  "
            "Should reference which fields and provenance tags were most influential."
        ),
    )
    used_fields: List[str] = Field(
        default_factory=list,
        description=(
            "Names (or dot-paths) of the VeritasRecord fields that contributed to "
            "this claim.  Used for provenance tracing and auditability."
        ),
    )

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# SystemDecision
# ---------------------------------------------------------------------------

FinalAction = Literal[
    "suppress",
    "notify_patient",
    "queue_for_nurse",
    "escalate_to_doctor",
]
TargetRole = Literal["patient", "nurse", "doctor"]
Priority = Literal["low", "normal", "high", "urgent"]


class DecisionMeta(BaseModel):
    """Metadata attached to a SystemDecision for auditability."""

    timestamp: datetime = Field(description="UTC time the decision was made.")
    participating_agents: List[str] = Field(
        default_factory=list,
        description="Names of all specialist agents whose claims were considered.",
    )

    model_config = {"extra": "allow"}


class SystemDecision(BaseModel):
    """
    The final, actionable output of the MetaSentinelAgent for a single alert.

    This is the only object that leaves the automated pipeline and reaches
    human attention.  DashboardService routes it to the appropriate role
    (patient, nurse, or doctor) according to ``final_action`` and ``target_role``.

    Cooldown
    --------
    ``cooldown_until`` is an optional datetime set by MetaSentinelAgent to
    suppress duplicate alerts for the same patient.  DashboardService MUST
    check this before delivering the decision.  The intent is to protect staff
    from continuous interruptions; the exact cooldown duration is a configurable
    parameter, not a hard-coded threshold.

    What MetaSentinelAgent decides
    --------------------------------
    MetaSentinelAgent synthesises all AgentClaims and considers:
    - The distribution of risk_level values across claims.
    - Whether any agent recommends escalation vs. suppression.
    - The available provenance (low-trust context → more caution or deferral).
    - The cooldown state for this patient.
    Proprietary weighting and decision logic goes in MetaSentinelAgent; only
    the output shape is defined here.
    """

    alert_id: str = Field(description="ID of the CandidateAlert this decision resolves.")

    final_action: FinalAction = Field(
        description="What the system will do with this alert."
    )
    target_role: TargetRole = Field(
        description="Which human role (if any) should receive this decision."
    )
    priority: Priority = Field(
        description="Urgency level communicated to DashboardService."
    )

    cooldown_until: Optional[datetime] = Field(
        None,
        description=(
            "If set, DashboardService must not generate another decision of the "
            "same type for this patient until after this datetime — unless a "
            "subsequent alert has risk_level='critical'."
        ),
    )
    meta: Optional[DecisionMeta] = Field(
        None,
        description="Auditability metadata: when the decision was made and which agents contributed.",
    )

    model_config = {"extra": "forbid"}
