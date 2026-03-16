"""
veritas_agent.py — VeritasAgent: the ground-truth assembler.

Responsibility
--------------
VeritasAgent is the *only* component that touches the raw data sources.  It
ingests four streams of patient information, tags each piece with a provenance
label, and emits a unified VeritasRecord that the rest of the pipeline consumes.

Raw sources
-----------
1. EHR data     — historical, relatively static (diagnoses, meds, baselines).
2. Conversations — daily patient reports (symptoms, activities, adherence).
3. Vital signs  — near-real-time RPM device readings (HR, SpO₂, signal quality).
4. Patient input — immediate "speak now" utterances (highest immediacy ground truth).

Provenance contract
-------------------
Every field populated in the output VeritasRecord MUST have a corresponding
entry in the ``provenance`` dict.  Downstream agents rely on provenance to
weight evidence appropriately.  A missing provenance tag should be treated as
an error, not silently ignored.

Design note
-----------
In production this agent would connect to live data feeds (EHR APIs, RPM
device streams, conversational AI pipelines).  In this reference implementation
all ingest methods accept plain Python dicts to keep the example runnable
without any external infrastructure.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional

from veritas_rpm.models import (
    CandidateAlert,
    ConversationData,
    EHRData,
    PatientInput,
    ProvenanceTag,
    VeritasRecord,
    VitalSigns,
)


class VeritasAgent:
    """
    Assembles ground-truth VeritasRecord objects from four raw data sources.

    Usage
    -----
    agent = VeritasAgent()

    # Feed raw data for a patient:
    agent.ingest_ehr(patient_id, ehr_dict)
    agent.ingest_conversation(patient_id, conversation_dict)
    agent.ingest_vitals(patient_id, vitals_dict)
    agent.ingest_patient_input(patient_id, input_dict)   # optional

    # Build and emit a record:
    record = agent.build_record(patient_id)

    Provenance update
    -----------------
    DashboardService may call ``update_provenance_override`` when a clinician
    confirms or corrects a data point.  This override is applied to all
    subsequently built records for that patient.
    """

    def __init__(self) -> None:
        # Staged raw data per patient (keyed by patient_id)
        self._ehr_cache: Dict[str, Dict[str, Any]] = {}
        self._conversation_cache: Dict[str, Dict[str, Any]] = {}
        self._vitals_cache: Dict[str, Dict[str, Any]] = {}
        self._patient_input_cache: Dict[str, Dict[str, Any]] = {}

        # Provenance overrides set by clinicians via DashboardService
        self._provenance_overrides: Dict[str, Dict[str, ProvenanceTag]] = {}

        # Optional callbacks registered by SentinelLayer (publish/subscribe)
        self._subscribers: List[Callable[[VeritasRecord], None]] = []

    # ------------------------------------------------------------------
    # Subscriber registration (pub/sub interface for SentinelLayer)
    # ------------------------------------------------------------------

    def subscribe(self, callback: Callable[[VeritasRecord], None]) -> None:
        """
        Register a callback to be invoked whenever a new VeritasRecord is emitted.

        SentinelLayer uses this to receive records without polling.

        Parameters
        ----------
        callback:
            A function that accepts a single VeritasRecord argument.
        """
        self._subscribers.append(callback)

    def _emit(self, record: VeritasRecord) -> None:
        """Notify all registered subscribers with a newly built record."""
        for cb in self._subscribers:
            cb(record)

    # ------------------------------------------------------------------
    # Ingest methods — one per raw data source
    # ------------------------------------------------------------------

    def ingest_ehr(self, patient_id: str, raw: Dict[str, Any]) -> None:
        """
        Ingest a batch of EHR data for a patient.

        Parameters
        ----------
        patient_id:
            Identifier of the patient whose EHR is being updated.
        raw:
            Dict matching the EHRData schema (diagnoses, medications,
            baseline_spo2, baseline_hr, recent_admissions, …).

        Notes
        -----
        EHR data is treated as EHR_verified unless overridden.  In a real
        system this method would validate the data against the EHR schema and
        raise on unexpected fields.
        """
        self._ehr_cache[patient_id] = raw

    def ingest_conversation(self, patient_id: str, raw: Dict[str, Any]) -> None:
        """
        Ingest a conversation-derived data payload for a patient.

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        raw:
            Dict matching the ConversationData schema (symptoms, activities,
            adherence_notes, …).

        Notes
        -----
        Conversation data provenance is typically LLM_extracted_* because the
        symptoms and activities are usually extracted by a language model from
        free-text transcripts.  The exact tag depends on whether a second
        extraction pass confirmed the result.
        """
        self._conversation_cache[patient_id] = raw

    def ingest_vitals(self, patient_id: str, raw: Dict[str, Any]) -> None:
        """
        Ingest a vital-signs snapshot from the RPM device.

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        raw:
            Dict matching the VitalSigns schema (hr, spo2, resp_rate,
            signal_quality, activity_level, …).

        Notes
        -----
        Device data is always tagged device_stream.  Missing values (None)
        should be left as None rather than filled with defaults, because
        downstream agents treat None as "unknown" — distinct from a measured
        value of zero.
        """
        self._vitals_cache[patient_id] = raw

    def ingest_patient_input(
        self, patient_id: str, raw: Dict[str, Any]
    ) -> None:
        """
        Ingest an immediate patient statement (the 'speak now' input).

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        raw:
            Dict matching the PatientInput schema (free_text, symptom_severity).

        Notes
        -----
        Patient input is tagged human_confirmed because it represents the
        patient's own real-time account.  Agents are expected to treat this
        as high-priority context — for example a statement like 'probe fell
        off' should cause ProbeIntegrityAgent to suppress a false-positive
        desaturation alert.
        """
        self._patient_input_cache[patient_id] = raw

    # ------------------------------------------------------------------
    # Provenance management
    # ------------------------------------------------------------------

    def tag_provenance(
        self,
        patient_id: str,
        field_path: str,
        tag: ProvenanceTag,
    ) -> None:
        """
        Manually set the provenance tag for a specific field of a patient's record.

        This is called internally during ``build_record`` and also by
        DashboardService when a clinician confirms or corrects a value.

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        field_path:
            Dot-separated path to the field within VeritasRecord
            (e.g. 'ehr_data.baseline_spo2', 'vital_signs.hr').
        tag:
            The ProvenanceTag to apply.
        """
        if patient_id not in self._provenance_overrides:
            self._provenance_overrides[patient_id] = {}
        self._provenance_overrides[patient_id][field_path] = tag

    def update_provenance_override(
        self,
        patient_id: str,
        corrections: Dict[str, ProvenanceTag],
    ) -> None:
        """
        Apply a batch of provenance overrides for a patient.

        Typically called by DashboardService when a clinician reviews and
        confirms or corrects data — for example confirming that a patient
        does have COPD (elevating 'ehr_data.diagnoses' to 'human_confirmed')
        or marking that a probe was physically faulty ('vital_signs.spo2'
        to 'human_confirmed' with a note).

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        corrections:
            Mapping of field_path → ProvenanceTag to apply.
        """
        for field_path, tag in corrections.items():
            self.tag_provenance(patient_id, field_path, tag)

    # ------------------------------------------------------------------
    # Record assembly
    # ------------------------------------------------------------------

    def build_record(self, patient_id: str) -> VeritasRecord:
        """
        Assemble a VeritasRecord from all currently staged data for a patient.

        This is the core output method.  It:
        1. Combines EHR, conversation, vital-signs, and patient-input data.
        2. Assigns default provenance tags to each top-level section.
        3. Applies any clinician-supplied provenance overrides.
        4. Constructs and returns a validated VeritasRecord.
        5. Notifies all registered subscribers (e.g. SentinelLayer).

        Parameters
        ----------
        patient_id:
            Identifier of the patient for whom to build the record.

        Returns
        -------
        VeritasRecord
            A fully populated, validated record ready for the Sentinel pipeline.

        Raises
        ------
        ValueError
            If no data at all has been ingested for the given patient_id.
        """
        ehr_raw = self._ehr_cache.get(patient_id, {})
        conv_raw = self._conversation_cache.get(patient_id, {})
        vitals_raw = self._vitals_cache.get(patient_id, {})
        input_raw = self._patient_input_cache.get(patient_id, {})

        if not any([ehr_raw, conv_raw, vitals_raw, input_raw]):
            raise ValueError(
                f"No data has been ingested for patient_id='{patient_id}'.  "
                "Call at least one ingest_*() method before build_record()."
            )

        # Default provenance assignments per section
        provenance: Dict[str, ProvenanceTag] = {
            "ehr_data": "EHR_verified",
            "conversation_data": "LLM_extracted_dual_confirmed",
            "vital_signs": "device_stream",
            "patient_input": "human_confirmed",
        }

        # Apply any clinician-confirmed overrides
        overrides = self._provenance_overrides.get(patient_id, {})
        provenance.update(overrides)

        record = VeritasRecord(
            record_id=str(uuid.uuid4()),
            patient_id=patient_id,
            timestamp=datetime.now(timezone.utc),
            ehr_data=EHRData(**ehr_raw) if ehr_raw else EHRData(),
            conversation_data=ConversationData(**conv_raw) if conv_raw else ConversationData(),
            vital_signs=VitalSigns(**vitals_raw) if vitals_raw else VitalSigns(),
            patient_input=PatientInput(**input_raw) if input_raw else PatientInput(),
            provenance=provenance,
        )

        self._emit(record)
        return record

    def build_and_stream(
        self, patient_id: str, vitals_sequence: List[Dict[str, Any]]
    ) -> Iterator[VeritasRecord]:
        """
        Convenience generator: update vitals and yield a fresh VeritasRecord
        for each entry in ``vitals_sequence``.

        This simulates a live RPM stream for demonstration purposes.

        Parameters
        ----------
        patient_id:
            Identifier of the patient.
        vitals_sequence:
            List of VitalSigns-compatible dicts, one per time step.

        Yields
        ------
        VeritasRecord
            One record per vitals snapshot.
        """
        for vitals in vitals_sequence:
            self.ingest_vitals(patient_id, vitals)
            yield self.build_record(patient_id)
