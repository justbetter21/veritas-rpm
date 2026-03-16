"""
example.py — End-to-end demonstration of the Veritas-RPM pipeline.

This script runs four synthetic patient scenarios through the pipeline and
prints the resulting SystemDecisions to the terminal.

Scenarios
---------
1. Exertional tachycardia        — Patient with COPD; elevated HR during exercise.
2. Probable probe displacement   — Sudden SpO₂ drop with 'probe fell off' patient input.
3. Nocturnal bradycardia         — Low HR at 02:00; patient on beta-blockers.
4. Unexplained desaturation      — SpO₂ drop with no clear contextual explanation.

NOTE
----
This code is for research and educational purposes only.
It is NOT a medical device and MUST NOT be used for clinical decisions.
All specialist-agent evaluate() methods contain TODO stubs — no real clinical
thresholds are applied.  The pipeline structure and data flow are illustrated,
but the SystemDecisions produced are placeholder outputs.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from veritas_rpm import RPMPipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str) -> None:
    """Print a formatted section header."""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_pipeline_state(pipeline: RPMPipeline, patient_id: str) -> None:
    """Print all queued decisions for a patient across all role queues."""
    queues = {
        "Patient notifications": pipeline.dashboard.get_patient_queue(),
        "Nurse queue":           pipeline.dashboard.get_nurse_queue(),
        "Doctor escalations":    pipeline.dashboard.get_doctor_queue(),
    }
    for queue_name, decisions in queues.items():
        relevant = [d for d in decisions if d.alert_id]  # all alerts are relevant here
        if relevant:
            print(f"\n  [{queue_name}]")
            for d in relevant:
                print(
                    f"    alert_id       : {d.alert_id[:16]}..."
                    f"\n    final_action   : {d.final_action}"
                    f"\n    target_role    : {d.target_role}"
                    f"\n    priority       : {d.priority}"
                    f"\n    cooldown_until : {d.cooldown_until}"
                    f"\n    agents         : {d.meta.participating_agents if d.meta else '[]'}"
                )


# ---------------------------------------------------------------------------
# Scenario 1 — Exertional tachycardia
# ---------------------------------------------------------------------------

def scenario_exertional_tachycardia() -> RPMPipeline:
    """
    A patient with COPD has an elevated heart rate during afternoon exercise.

    Context clues available to specialist agents:
    - EHR: COPD diagnosis, baseline HR documented.
    - Vitals: elevated HR, activity_level = 'moderate'.
    - Conversation: patient reported 'went for a 20-minute walk' this morning.
    - No patient input (probe is on correctly).

    Expected reasoning (if specialist logic were implemented):
    - TachycardiaAgent: activity explains the HR → classify as
      'benign_exertional_tachycardia' → low risk → suppress or notify_patient.
    - ActivityIntegrityAgent: activity_level = 'moderate' is consistent with
      the vital readings → activity_explains_vitals → suppress.
    - ProbeIntegrityAgent: signal quality is 'good' → probe_integrity_acceptable.
    - MetaSentinelAgent: majority low-risk → suppress or notify_patient.
    """
    section("Scenario 1: Exertional Tachycardia (COPD patient, post-exercise)")

    pipeline = RPMPipeline()
    pid = "patient-001"

    pipeline.ingest_ehr(pid, {
        "diagnoses": ["COPD", "Hypertension"],
        "medications": ["Salbutamol inhaler", "Lisinopril 10mg"],
        "baseline_spo2": 93.0,   # Lower than average due to COPD
        "baseline_hr": 72.0,
        "recent_admissions": [],
    })

    pipeline.ingest_conversation(pid, {
        "symptoms": ["mild breathlessness on exertion"],
        "activities": ["walked 20 minutes this afternoon"],
        "adherence_notes": "took all medications this morning",
    })

    pipeline.ingest_vitals(pid, {
        "hr": 108.0,             # Elevated; context: moderate exercise
        "spo2": 91.0,            # Slightly below baseline; expected post-exercise
        "resp_rate": 22.0,
        "signal_quality": "good",
        "activity_level": "moderate",
    })

    print(f"\n  Processing patient '{pid}'...")
    pipeline.process(pid)
    print_pipeline_state(pipeline, pid)
    return pipeline


# ---------------------------------------------------------------------------
# Scenario 2 — Probable probe displacement
# ---------------------------------------------------------------------------

def scenario_probe_displacement() -> RPMPipeline:
    """
    A patient reports their probe fell off.  A simultaneous SpO₂ drop should
    be attributed to the device issue rather than a clinical event.

    Context clues available to specialist agents:
    - Patient input: 'The probe slipped off my finger again.'
    - Vitals: SpO₂ = None (no signal), signal_quality = 'no_signal'.
    - EHR: Hypertension only — no respiratory conditions.

    Expected reasoning (if specialist logic were implemented):
    - ProbeIntegrityAgent: patient explicitly reported probe off +
      signal_quality = 'no_signal' → 'probable_probe_displacement' → suppress.
    - MetaSentinelAgent: probe artefact likely → notify_patient to reattach probe.
    """
    section("Scenario 2: Probable Probe Displacement (patient reported)")

    pipeline = RPMPipeline()
    pid = "patient-002"

    pipeline.ingest_ehr(pid, {
        "diagnoses": ["Hypertension"],
        "medications": ["Amlodipine 5mg"],
        "baseline_spo2": 97.0,
        "baseline_hr": 68.0,
        "recent_admissions": [],
    })

    pipeline.ingest_conversation(pid, {
        "symptoms": [],
        "activities": ["resting at home"],
        "adherence_notes": "",
    })

    pipeline.ingest_vitals(pid, {
        "hr": None,              # No signal
        "spo2": None,            # No signal
        "resp_rate": None,
        "signal_quality": "no_signal",
        "activity_level": "resting",
    })

    # Patient 'speak now' input — highest-priority ground truth
    pipeline.ingest_patient_input(pid, {
        "free_text": "The probe slipped off my finger again.",
        "symptom_severity": None,
    })

    print(f"\n  Processing patient '{pid}'...")
    pipeline.process(pid)
    print_pipeline_state(pipeline, pid)
    return pipeline


# ---------------------------------------------------------------------------
# Scenario 3 — Nocturnal bradycardia (medication-related)
# ---------------------------------------------------------------------------

def scenario_nocturnal_bradycardia() -> RPMPipeline:
    """
    A patient on a beta-blocker has a low HR at 02:00 while asleep.
    Low resting HR during sleep is physiologically normal and expected
    in a patient on rate-limiting medication.

    Context clues available to specialist agents:
    - EHR: Metoprolol (beta-blocker) in medications; known to lower HR.
    - Vitals: HR = 48, signal_quality = 'good', activity_level = 'resting'.
    - Timestamp: 02:00 UTC (within typical sleep window).
    - No patient input.

    Expected reasoning (if specialist logic were implemented):
    - BradycardiaAgent: HR low but patient is on beta-blocker →
      'expected_medication_bradycardia' → low risk.
    - NocturnalAgent: event at 02:00, resting, within sleep window →
      'expected_nocturnal_physiology' → suppress.
    - MetaSentinelAgent: consensus low risk, nocturnal context → suppress.
    """
    section("Scenario 3: Nocturnal Bradycardia (beta-blocker, during sleep)")

    pipeline = RPMPipeline()
    pid = "patient-003"

    pipeline.ingest_ehr(pid, {
        "diagnoses": ["Atrial fibrillation (rate-controlled)"],
        "medications": ["Metoprolol 50mg BD", "Warfarin 3mg"],
        "baseline_spo2": 97.0,
        "baseline_hr": 58.0,     # Chronically lower on beta-blocker
        "recent_admissions": [],
    })

    pipeline.ingest_conversation(pid, {
        "symptoms": ["no complaints today"],
        "activities": ["watching TV, then went to bed at 22:30"],
        "adherence_notes": "all medications taken",
    })

    pipeline.ingest_vitals(pid, {
        "hr": 48.0,              # Low; expected on beta-blocker during sleep
        "spo2": 96.0,
        "resp_rate": 14.0,
        "signal_quality": "good",
        "activity_level": "resting",
    })

    print(f"\n  Processing patient '{pid}'...")
    pipeline.process(pid)
    print_pipeline_state(pipeline, pid)
    return pipeline


# ---------------------------------------------------------------------------
# Scenario 4 — Unexplained desaturation (no clear benign context)
# ---------------------------------------------------------------------------

def scenario_unexplained_desaturation() -> RPMPipeline:
    """
    A patient has a sustained SpO₂ drop with no activity, no probe issue
    reported, and no obvious medication effect.  This is the scenario where
    the pipeline should escalate for clinical review.

    Context clues available to specialist agents:
    - EHR: No respiratory conditions; normal baseline SpO₂.
    - Vitals: SpO₂ sustained drop, signal_quality = 'good', resting.
    - No patient input — patient is unaware.

    Expected reasoning (if specialist logic were implemented):
    - ProbeIntegrityAgent: signal quality good, no patient report →
      'probe_integrity_acceptable'.
    - COPDAgent: no COPD diagnosis → 'not_copd_relevant'.
    - The lack of any benign explanation elevates risk.
    - MetaSentinelAgent: no suppression context → escalate_to_doctor or
      queue_for_nurse depending on severity.
    """
    section("Scenario 4: Unexplained Desaturation (no clear benign context)")

    pipeline = RPMPipeline()
    pid = "patient-004"

    pipeline.ingest_ehr(pid, {
        "diagnoses": ["Type 2 Diabetes"],
        "medications": ["Metformin 500mg BD"],
        "baseline_spo2": 98.0,
        "baseline_hr": 74.0,
        "recent_admissions": [],
    })

    pipeline.ingest_conversation(pid, {
        "symptoms": ["mild fatigue since this morning"],
        "activities": ["resting at home all day"],
        "adherence_notes": "medications taken",
    })

    pipeline.ingest_vitals(pid, {
        "hr": 88.0,              # Mildly elevated
        "spo2": 89.0,            # Well below baseline — no obvious explanation
        "resp_rate": 26.0,
        "signal_quality": "good",
        "activity_level": "resting",
    })

    print(f"\n  Processing patient '{pid}'...")
    pipeline.process(pid)
    print_pipeline_state(pipeline, pid)
    return pipeline


# ---------------------------------------------------------------------------
# Demonstrate feedback loop
# ---------------------------------------------------------------------------

def demonstrate_feedback_loop(pipeline: RPMPipeline, patient_id: str) -> None:
    """
    Show how a clinician's feedback flows back through the pipeline.

    After reviewing the nurse queue, a nurse confirms that the patient does
    have COPD (which elevates the EHR provenance from LLM_extracted to
    human_confirmed) and labels the alert as a false positive.
    """
    section("Feedback Loop: Nurse labels false positive + confirms COPD diagnosis")

    nurse_queue = pipeline.dashboard.get_nurse_queue()
    if not nurse_queue:
        print("  (No decisions in nurse queue — feedback loop skipped.)")
        return

    decision = nurse_queue[0]
    print(f"\n  Nurse reviewing: alert_id={decision.alert_id[:16]}...")

    # Report feedback: false positive due to exertion
    pipeline.dashboard.report_feedback(
        alert_id=decision.alert_id,
        label="false_positive_exertion",
        data_corrections={"ehr_data.diagnoses": "human_confirmed"},
        patient_id=patient_id,
    )

    # Acknowledge the alert
    pipeline.dashboard.acknowledge(decision.alert_id, role="nurse")

    print(f"\n  Outcome log: {pipeline.meta.get_outcome_log()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("Veritas-RPM Reference Pipeline — Synthetic Demonstration")
    print("=" * 70)
    print("NOTE: All specialist agents contain TODO stubs.")
    print("      SystemDecisions below are placeholder outputs.")
    print("      No real clinical thresholds are applied.")
    print("=" * 70)

    p1 = scenario_exertional_tachycardia()
    p2 = scenario_probe_displacement()
    p3 = scenario_nocturnal_bradycardia()
    p4 = scenario_unexplained_desaturation()

    demonstrate_feedback_loop(p1, "patient-001")

    section("Summary")
    print()
    for label, pipeline in [
        ("Scenario 1 (Exertional Tachycardia)", p1),
        ("Scenario 2 (Probe Displacement)",     p2),
        ("Scenario 3 (Nocturnal Bradycardia)",  p3),
        ("Scenario 4 (Unexplained Desaturation)", p4),
    ]:
        all_d = pipeline.get_all_decisions()
        if all_d:
            for d in all_d:
                print(
                    f"  {label:<40}  "
                    f"action={d.final_action:<22}  priority={d.priority}"
                )
        else:
            print(f"  {label:<40}  (no decisions generated)")

    print()
    print("Run complete.  See veritas_rpm/ for full source code and TODOs.")
    print()
