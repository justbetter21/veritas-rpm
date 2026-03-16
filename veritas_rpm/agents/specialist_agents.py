"""
specialist_agents.py — Specialist agent implementations.

Each specialist agent evaluates a CandidateAlert from one focused clinical
perspective and returns an AgentClaim.  They are invoked by DirectorAgent
and never call each other or any external service.

Abstract base
-------------
SpecialistAgent defines the common interface.  All concrete agents extend it
and implement ``evaluate()``.

Proprietary boundary
--------------------
The bodies of all ``evaluate()`` methods contain only TODO placeholders.
In a production system these would encode the expert clinical rules relevant
to each agent's domain.  This reference implementation shows the interface,
the data flow, and the kinds of reasoning each agent performs — but no
actual thresholds or decision rules.

Agents implemented here
-----------------------
TachycardiaAgent        — Evaluates elevated-HR alerts.
BradycardiaAgent        — Evaluates low-HR alerts.
COPDAgent               — Evaluates SpO₂/HR events in the context of COPD.
NocturnalAgent          — Evaluates events that occur during sleep windows.
ActivityIntegrityAgent  — Evaluates whether activity context explains vitals.
ProbeIntegrityAgent     — Evaluates whether signal quality suggests an artefact.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from veritas_rpm.models import (
    AgentClaim,
    CandidateAlert,
    VeritasRecord,
)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

class SpecialistAgent(ABC):
    """
    Abstract base class for all specialist agents in the RPM pipeline.

    Each specialist agent is responsible for one focused domain of clinical
    reasoning.  DirectorAgent selects which specialists to invoke based on the
    alert_type and context; each selected agent produces an AgentClaim.

    Interface contract
    ------------------
    Concrete agents MUST implement ``evaluate()``.
    Concrete agents SHOULD set a meaningful ``name`` class attribute so that
    AgentClaim.agent_name is human-readable.

    Agents MUST NOT:
    - Emit alerts or make decisions independently — they only return claims.
    - Call other specialist agents.
    - Access raw data sources directly (only VeritasRecord is available).
    """

    name: str = "UnnamedAgent"

    @abstractmethod
    def evaluate(
        self,
        alert: CandidateAlert,
        context: VeritasRecord,
    ) -> AgentClaim:
        """
        Evaluate a CandidateAlert given the current patient context.

        Parameters
        ----------
        alert:
            The CandidateAlert to assess.  Contains aggregated features over
            the alert time window and a provenance summary.
        context:
            The most recent VeritasRecord for this patient.  Contains EHR,
            conversation, vital signs, and patient input — plus provenance tags
            for each field.

        Returns
        -------
        AgentClaim
            The agent's assessment: classification, risk level, recommended
            action, justification, and which fields were used.
        """
        ...

    def _stub_claim(
        self,
        alert: CandidateAlert,
        classification: str,
        risk_level: str,
        recommended_action: str,
        justification: str,
        used_fields: List[str],
    ) -> AgentClaim:
        """
        Convenience method for constructing an AgentClaim.

        Agents should call this (or construct AgentClaim directly) rather than
        duplicating boilerplate in every ``evaluate()`` body.
        """
        return AgentClaim(
            alert_id=alert.alert_id,
            agent_name=self.name,
            classification=classification,
            risk_level=risk_level,           # type: ignore[arg-type]
            recommended_action=recommended_action,  # type: ignore[arg-type]
            justification=justification,
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# TachycardiaAgent
# ---------------------------------------------------------------------------

class TachycardiaAgent(SpecialistAgent):
    """
    Evaluates elevated heart rate alerts.

    This agent's primary question is: *why is the heart rate elevated, and
    does it represent a clinical concern?*

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - The patient's baseline_hr from EHR (is this above their personal norm?).
    - The activity_level at the time: vigorous exercise may fully explain the HR.
    - Conversation data: did the patient report strenuous activity or emotional
      distress earlier today?
    - EHR diagnoses: does the patient have a condition that makes tachycardia
      more significant (e.g. heart failure, recent MI)?
    - Medications that can elevate HR (e.g. salbutamol, certain antidepressants).
    - Duration and trend of the elevated HR over the alert window.
    - Patient input: did they report symptoms like palpitations or dizziness?

    Typical classifications produced
    ---------------------------------
    'benign_exertional_tachycardia'   — HR elevated but activity explains it.
    'medication_related_tachycardia'  — Known pharmacological cause.
    'possible_clinical_tachycardia'   — No clear benign explanation found.
    'probable_sinus_tachycardia'      — Pattern consistent with stress response.
    """

    name = "TachycardiaAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess a tachycardia or elevated-HR alert.

        TODO
        ----
        Replace the placeholder logic below with the actual tachycardia
        evaluation rules:

        1. Retrieve context.ehr_data.baseline_hr and compare with
           alert.features.max_hr and alert.features.avg_hr.
        2. Check context.vital_signs.activity_level and
           context.conversation_data.activities for exertional context.
        3. Check context.ehr_data.medications for drugs that raise HR.
        4. Check context.ehr_data.diagnoses for conditions that elevate risk.
        5. Check context.patient_input.free_text for patient-reported symptoms.
        6. Apply risk stratification (proprietary) to produce risk_level.
        7. Map risk_level to recommended_action (proprietary).
        """
        # TODO: Implement proprietary tachycardia evaluation logic.
        # The lines below are stubs that demonstrate the return structure only.

        used_fields = [
            "vital_signs.hr",
            "vital_signs.activity_level",
            "ehr_data.baseline_hr",
            "ehr_data.diagnoses",
            "ehr_data.medications",
            "conversation_data.activities",
            "patient_input.free_text",
        ]

        return self._stub_claim(
            alert=alert,
            classification="undetermined_tachycardia",
            risk_level="moderate",
            recommended_action="queue_for_nurse",
            justification=(
                "[STUB] TachycardiaAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# BradycardiaAgent
# ---------------------------------------------------------------------------

class BradycardiaAgent(SpecialistAgent):
    """
    Evaluates abnormally low heart rate alerts.

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - The patient's baseline_hr from EHR.
    - Medications known to lower HR (beta-blockers, digoxin, etc.).
    - Sleep context: low HR during sleep is often physiologically normal.
    - EHR diagnoses: conditions like sick sinus syndrome make bradycardia
      more clinically significant.
    - Patient input: reported symptoms such as dizziness or near-syncope.

    Typical classifications produced
    ---------------------------------
    'expected_medication_bradycardia'  — Explained by a rate-lowering drug.
    'nocturnal_physiological_bradycardia' — Low HR during normal sleep.
    'possible_symptomatic_bradycardia' — Low HR with reported symptoms.
    'asymptomatic_bradycardia'         — Low HR, no reported symptoms.
    """

    name = "BradycardiaAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess a bradycardia or low-HR alert.

        TODO
        ----
        Replace the placeholder logic below with the actual bradycardia
        evaluation rules:

        1. Compare alert.features.min_hr / avg_hr against context.ehr_data.baseline_hr.
        2. Check context.ehr_data.medications for rate-lowering drugs.
        3. Determine if the event timestamp falls within a sleep window.
        4. Check context.patient_input for symptom reports.
        5. Apply risk stratification and map to recommended_action.
        """
        # TODO: Implement proprietary bradycardia evaluation logic.

        used_fields = [
            "vital_signs.hr",
            "ehr_data.baseline_hr",
            "ehr_data.medications",
            "ehr_data.diagnoses",
            "patient_input.free_text",
        ]

        return self._stub_claim(
            alert=alert,
            classification="undetermined_bradycardia",
            risk_level="moderate",
            recommended_action="queue_for_nurse",
            justification=(
                "[STUB] BradycardiaAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# COPDAgent
# ---------------------------------------------------------------------------

class COPDAgent(SpecialistAgent):
    """
    Evaluates SpO₂ and HR events in the context of COPD or other chronic
    respiratory conditions.

    Patients with COPD may have a lower 'normal' SpO₂ baseline than the
    general population.  This agent's primary role is to distinguish
    chronic COPD-related patterns from acute deterioration.

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - Whether the patient has COPD or another chronic lung condition in
      context.ehr_data.diagnoses.
    - The patient's documented baseline_spo2 (which may be lower than typical).
    - Recent admission history that might indicate a COPD exacerbation.
    - Conversation data: did the patient report worsening breathlessness?
    - Medications: COPD inhalers, oxygen therapy.

    Typical classifications produced
    ---------------------------------
    'chronic_copd_baseline'           — SpO₂ consistent with patient's known baseline.
    'possible_copd_exacerbation'      — SpO₂ below baseline with reported symptoms.
    'not_copd_relevant'               — Patient does not have COPD; not applicable.
    """

    name = "COPDAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess an alert in the context of COPD or chronic respiratory disease.

        TODO
        ----
        Replace the placeholder logic below:

        1. Check whether 'COPD' (or equivalent) appears in
           context.ehr_data.diagnoses.  If not, return a low-risk 'not_applicable'
           claim immediately.
        2. Compare alert.features.min_spo2 / avg_spo2 against
           context.ehr_data.baseline_spo2 (the patient's personal lower limit).
        3. Review context.conversation_data.symptoms for worsening breathlessness.
        4. Consider recent admission history as evidence of prior exacerbations.
        5. Apply COPD-specific risk stratification.
        """
        # TODO: Implement proprietary COPD evaluation logic.

        used_fields = [
            "vital_signs.spo2",
            "ehr_data.diagnoses",
            "ehr_data.baseline_spo2",
            "ehr_data.recent_admissions",
            "conversation_data.symptoms",
        ]

        return self._stub_claim(
            alert=alert,
            classification="undetermined_copd_context",
            risk_level="low",
            recommended_action="queue_for_nurse",
            justification=(
                "[STUB] COPDAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# NocturnalAgent
# ---------------------------------------------------------------------------

class NocturnalAgent(SpecialistAgent):
    """
    Evaluates events that occur during the patient's sleep window.

    Many vital-sign anomalies that are concerning during waking hours are
    physiologically normal during sleep.  This agent provides the context
    needed to avoid over-alerting for nocturnal physiology.

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - Whether the alert timestamp falls within the patient's sleep window
      (derived from the system or from the patient's stated schedule).
    - Typical nocturnal HR and SpO₂ values for this patient's demographics
      and diagnoses.
    - Sleep-disordered breathing diagnoses (e.g. OSA) in ehr_data.
    - Conversation data: did the patient report poor sleep quality or
      symptoms of sleep apnoea?

    Typical classifications produced
    ---------------------------------
    'expected_nocturnal_physiology'    — Values within expected nocturnal range.
    'possible_sleep_disordered_breathing' — Pattern suggestive of apnoea events.
    'nocturnal_clinical_event'         — Anomaly not explained by sleep physiology.
    """

    name = "NocturnalAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess an alert in the context of the patient's sleep window.

        TODO
        ----
        Replace the placeholder logic below:

        1. Determine whether alert.start_time falls within the patient's
           configured or estimated sleep window.
        2. Apply nocturnal-specific HR and SpO₂ reference ranges.
        3. Check context.ehr_data.diagnoses for OSA or related conditions.
        4. Cross-reference context.conversation_data.symptoms (e.g. 'poor sleep').
        """
        # TODO: Implement proprietary nocturnal event evaluation logic.

        used_fields = [
            "vital_signs.hr",
            "vital_signs.spo2",
            "ehr_data.diagnoses",
            "conversation_data.symptoms",
        ]

        return self._stub_claim(
            alert=alert,
            classification="undetermined_nocturnal_event",
            risk_level="low",
            recommended_action="queue_for_nurse",
            justification=(
                "[STUB] NocturnalAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# ActivityIntegrityAgent
# ---------------------------------------------------------------------------

class ActivityIntegrityAgent(SpecialistAgent):
    """
    Evaluates whether the current activity level explains or contextualises
    the observed vital-sign anomaly.

    This agent is an 'integrity' agent: its job is not to assess clinical risk
    directly, but to determine whether a vital-sign event can be attributed to
    a known activity.  A tachycardia during vigorous exercise is very different
    from one at rest.

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - context.vital_signs.activity_level from the device accelerometer.
    - context.conversation_data.activities (patient-reported activities today).
    - Whether the activity level is consistent with the patient's condition
      (e.g. vigorous exercise in a patient with severe heart failure would be
      unexpected and itself a flag).

    Typical classifications produced
    ---------------------------------
    'activity_explains_vitals'       — The activity level accounts for the anomaly.
    'activity_inconsistent_with_diagnosis' — Activity level is unexpectedly high.
    'activity_context_unavailable'   — No activity data to contextualise the event.
    'vitals_not_explained_by_activity' — Activity present but does not explain vitals.
    """

    name = "ActivityIntegrityAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess whether activity context explains the alert.

        TODO
        ----
        Replace the placeholder logic below:

        1. Retrieve vital_signs.activity_level and conversation_data.activities.
        2. Check provenance of activity_level (device_stream vs. human_confirmed).
        3. Determine whether the reported activity is physiologically consistent
           with the alert features (e.g. max_hr, avg_hr).
        4. Consider whether the activity level is appropriate given
           ehr_data.diagnoses.
        """
        # TODO: Implement proprietary activity integrity evaluation logic.

        used_fields = [
            "vital_signs.activity_level",
            "vital_signs.hr",
            "conversation_data.activities",
            "ehr_data.diagnoses",
        ]

        return self._stub_claim(
            alert=alert,
            classification="activity_context_unavailable",
            risk_level="low",
            recommended_action="suppress",
            justification=(
                "[STUB] ActivityIntegrityAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )


# ---------------------------------------------------------------------------
# ProbeIntegrityAgent
# ---------------------------------------------------------------------------

class ProbeIntegrityAgent(SpecialistAgent):
    """
    Evaluates whether the alert is likely caused by a probe placement or
    signal quality problem rather than a genuine physiological event.

    This is a 'false positive prevention' agent.  Pulse-oximetry probes are
    prone to displacement (especially during sleep), poor perfusion, and
    movement artefact.  Before escalating a low-SpO₂ alert, it is important
    to assess whether the signal itself is reliable.

    Contextual factors it considers (in a full implementation)
    ----------------------------------------------------------
    - vital_signs.signal_quality from the device.
    - patient_input.free_text for explicit 'probe fell off' type reports.
    - The pattern of the SpO₂ time series (sudden step-changes vs. gradual
      decline suggest artefact vs. physiological desaturation).
    - Whether the HR signal was simultaneously affected (corroborating vs.
      isolated SpO₂ drop).

    Typical classifications produced
    ---------------------------------
    'probable_probe_displacement'      — Signal quality or patient report suggests
                                         probe was not properly positioned.
    'probable_movement_artefact'       — Short-duration drop consistent with motion.
    'signal_quality_insufficient'      — Device reports poor quality; data unreliable.
    'probe_integrity_acceptable'       — No evidence of probe issue; vitals likely real.
    """

    name = "ProbeIntegrityAgent"

    def evaluate(
        self, alert: CandidateAlert, context: VeritasRecord
    ) -> AgentClaim:
        """
        Assess whether the alert may be caused by a probe or signal issue.

        TODO
        ----
        Replace the placeholder logic below:

        1. Inspect alert.features.signal_quality_summary and
           alert.provenance_summary.
        2. Read context.vital_signs.signal_quality directly.
        3. Parse context.patient_input.free_text for probe-related keywords.
        4. Apply signal-quality thresholds (proprietary) to classify the probe
           state.
        5. If probe integrity is compromised, return 'suppress' or
           'notify_patient' with low/moderate risk.
        6. If integrity looks acceptable, return 'probe_integrity_acceptable'
           with low risk so MetaSentinelAgent can proceed with other claims.
        """
        # TODO: Implement proprietary probe integrity evaluation logic.

        used_fields = [
            "vital_signs.signal_quality",
            "vital_signs.spo2",
            "patient_input.free_text",
        ]

        return self._stub_claim(
            alert=alert,
            classification="probe_integrity_not_assessed",
            risk_level="low",
            recommended_action="queue_for_nurse",
            justification=(
                "[STUB] ProbeIntegrityAgent has not evaluated this alert.  "
                "Replace this body with proprietary evaluation logic."
            ),
            used_fields=used_fields,
        )
