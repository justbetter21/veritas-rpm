"""
sentinel_layer.py — SentinelLayer: the signal and event detector.

Responsibility
--------------
SentinelLayer subscribes to the stream of VeritasRecord objects emitted by
VeritasAgent.  Its job is to detect potential clinical events and create
CandidateAlert objects that are forwarded to DirectorAgent.

What it sees
------------
SentinelLayer sees only VeritasRecord objects — it never accesses raw EHR
text, conversation transcripts, or the RPM device API directly.

What it produces
----------------
For each detected event, it produces a CandidateAlert containing:
- The alert type (e.g. 'tachycardia', 'desaturation').
- The time window over which the event was observed.
- Aggregated vital-sign features (min/max/avg) for the window.
- A provenance summary indicating which data sources were available.

What it does NOT do
-------------------
- SentinelLayer does NOT interpret the clinical significance of an alert.
  That is the job of the specialist agents.
- SentinelLayer does NOT interact with human staff directly.
- SentinelLayer does NOT contain the thresholds used to define 'tachycardia',
  'desaturation', etc.  Those thresholds belong in the proprietary layer.

Proprietary boundary
--------------------
The methods ``_detect_*`` below contain only placeholder logic (TODO markers).
In a production implementation these methods would encode the exact signal-
detection algorithms and thresholds that are considered proprietary.  This
reference implementation demonstrates the method signatures and data flow only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from veritas_rpm.models import (
    AlertFeatures,
    AlertProvenanceSummary,
    AlertType,
    CandidateAlert,
    ProvenanceTag,
    VeritasRecord,
)


class SentinelLayer:
    """
    Signal and event detector that converts VeritasRecord streams into
    CandidateAlerts.

    Usage
    -----
    sentinel = SentinelLayer(director_agent)
    veritas_agent.subscribe(sentinel.on_record)

    # Now every VeritasRecord emitted by VeritasAgent is automatically
    # processed by the SentinelLayer.

    Alternatively, process a batch:
    alerts = sentinel.generate_candidate_alerts(list_of_records)
    """

    def __init__(self, director: Optional[object] = None) -> None:
        """
        Parameters
        ----------
        director:
            A DirectorAgent instance.  If provided, detected alerts are
            automatically forwarded via ``director.handle_alert()``.
            Pass None to use SentinelLayer in standalone mode.
        """
        self._director = director

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def on_record(self, record: VeritasRecord) -> List[CandidateAlert]:
        """
        Process a single VeritasRecord received from VeritasAgent.

        This method is designed to be registered as a subscriber callback:
            veritas_agent.subscribe(sentinel.on_record)

        It runs all detectors against the record, collects any resulting
        CandidateAlerts, and forwards each one to DirectorAgent.

        Parameters
        ----------
        record:
            The incoming VeritasRecord to scan.

        Returns
        -------
        List[CandidateAlert]
            All alerts generated from this record (may be empty).
        """
        alerts = self._run_all_detectors(record)
        if self._director is not None:
            for alert in alerts:
                self._director.handle_alert(alert)
        return alerts

    def generate_candidate_alerts(
        self, records: List[VeritasRecord]
    ) -> List[CandidateAlert]:
        """
        Process a batch of VeritasRecords and return all detected alerts.

        Useful when replaying historical data or running offline analyses.

        Parameters
        ----------
        records:
            Sequence of VeritasRecord objects to scan, in chronological order.

        Returns
        -------
        List[CandidateAlert]
            All alerts generated across the entire batch.
        """
        all_alerts: List[CandidateAlert] = []
        for record in records:
            all_alerts.extend(self._run_all_detectors(record))
        return all_alerts

    # ------------------------------------------------------------------
    # Internal orchestration
    # ------------------------------------------------------------------

    def _run_all_detectors(self, record: VeritasRecord) -> List[CandidateAlert]:
        """
        Run every registered detector against a single VeritasRecord.

        Returns a list of all CandidateAlerts produced (may be empty if no
        anomalies were detected).
        """
        alerts: List[CandidateAlert] = []

        detectors = [
            self._detect_tachycardia,
            self._detect_bradycardia,
            self._detect_desaturation,
            self._detect_flatline,
            self._detect_nocturnal_event,
            self._detect_probe_issue,
            self._detect_activity_spike,
        ]

        for detector in detectors:
            alert = detector(record)
            if alert is not None:
                alerts.append(alert)

        return alerts

    def _build_provenance_summary(
        self, record: VeritasRecord
    ) -> AlertProvenanceSummary:
        """
        Derive which trusted context sources were available in a given record.

        Maps the record's provenance tags to the narrower vocabulary used by
        AlertProvenanceSummary (which only tracks EHR_verified,
        LLM_extracted_dual_confirmed, and human_confirmed as 'context sources').
        """
        trusted_tags = {"EHR_verified", "LLM_extracted_dual_confirmed", "human_confirmed"}
        context_sources = list(
            {v for v in record.provenance.values() if v in trusted_tags}
        )
        return AlertProvenanceSummary(
            vitals_source="device_stream",
            context_sources=context_sources,  # type: ignore[arg-type]
        )

    def _make_alert(
        self,
        record: VeritasRecord,
        alert_type: AlertType,
        features: AlertFeatures,
    ) -> CandidateAlert:
        """
        Helper: construct a CandidateAlert from a detected event in a record.
        """
        return CandidateAlert(
            alert_id=str(uuid.uuid4()),
            patient_id=record.patient_id,
            alert_type=alert_type,
            start_time=record.timestamp,
            end_time=record.timestamp,
            features=features,
            provenance_summary=self._build_provenance_summary(record),
        )

    # ------------------------------------------------------------------
    # Signal detectors (proprietary logic replaced with TODO placeholders)
    # ------------------------------------------------------------------

    def _detect_tachycardia(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect an elevated heart rate event.

        Returns a CandidateAlert if the current HR reading meets the detection
        criteria, otherwise returns None.

        TODO
        ----
        Replace the placeholder condition below with the actual tachycardia
        detection algorithm:
        - Apply a threshold relative to the patient's baseline_hr from EHR.
        - Consider the activity_level to distinguish exertional from resting
          tachycardia.
        - Apply a minimum duration or persistence window before firing.
        - Incorporate any noise-filtering appropriate to the device.
        """
        vs = record.vital_signs
        if vs.hr is None:
            return None

        # TODO: Replace with proprietary tachycardia detection logic.
        detected = False  # Placeholder — always False in this reference implementation.

        if not detected:
            return None

        features = AlertFeatures(
            max_hr=vs.hr,
            avg_hr=vs.hr,
            avg_spo2=vs.spo2,
            signal_quality_summary=vs.signal_quality,
            activity_summary=vs.activity_level,
        )
        return self._make_alert(record, "tachycardia", features)

    def _detect_bradycardia(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect an abnormally low heart rate event.

        TODO
        ----
        Replace the placeholder condition with the actual bradycardia
        detection logic:
        - Apply a threshold relative to the patient's baseline_hr.
        - Consider medications known to lower HR (from ehr_data.medications).
        - Apply persistence requirements before firing.
        """
        vs = record.vital_signs
        if vs.hr is None:
            return None

        # TODO: Replace with proprietary bradycardia detection logic.
        detected = False  # Placeholder.

        if not detected:
            return None

        features = AlertFeatures(
            min_hr=vs.hr,
            avg_hr=vs.hr,
            avg_spo2=vs.spo2,
            signal_quality_summary=vs.signal_quality,
            activity_summary=vs.activity_level,
        )
        return self._make_alert(record, "bradycardia", features)

    def _detect_desaturation(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect an oxygen desaturation event.

        TODO
        ----
        Replace with actual desaturation detection logic:
        - Apply a threshold relative to the patient's baseline_spo2 from EHR.
        - Consider signal quality: low-quality signals may produce artefactual
          dips that should not trigger alerts.
        - Consider probe-related context from PatientInput (e.g. 'probe fell off').
        """
        vs = record.vital_signs
        if vs.spo2 is None:
            return None

        # TODO: Replace with proprietary desaturation detection logic.
        detected = False  # Placeholder.

        if not detected:
            return None

        features = AlertFeatures(
            min_spo2=vs.spo2,
            avg_spo2=vs.spo2,
            avg_hr=vs.hr,
            signal_quality_summary=vs.signal_quality,
            activity_summary=vs.activity_level,
        )
        return self._make_alert(record, "desaturation", features)

    def _detect_flatline(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect a flatline condition (e.g. no HR or SpO₂ signal for an extended period).

        TODO
        ----
        Replace with actual flatline detection logic:
        - Check for sustained None values across HR and SpO₂.
        - Distinguish between device off/disconnected and clinical emergency using
          signal_quality and patient_input context.
        """
        # TODO: Replace with proprietary flatline detection logic.
        detected = False  # Placeholder.

        if not detected:
            return None

        vs = record.vital_signs
        features = AlertFeatures(signal_quality_summary=vs.signal_quality)
        return self._make_alert(record, "flatline", features)

    def _detect_nocturnal_event(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect events that occur during the patient's typical sleep window.

        TODO
        ----
        Replace with actual nocturnal event detection logic:
        - Use the record timestamp to determine whether the event falls within
          the patient's configured sleep window.
        - Apply different HR/SpO₂ thresholds appropriate for sleep physiology.
        - Consider that resting HR and SpO₂ baselines during sleep may differ
          from daytime baselines stored in EHR.
        """
        # TODO: Replace with proprietary nocturnal event detection logic.
        detected = False  # Placeholder.

        if not detected:
            return None

        vs = record.vital_signs
        features = AlertFeatures(
            avg_hr=vs.hr,
            avg_spo2=vs.spo2,
            signal_quality_summary=vs.signal_quality,
        )
        return self._make_alert(record, "nocturnal_event", features)

    def _detect_probe_issue(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect a probable probe placement or signal quality problem.

        This detector is distinct from desaturation: it is triggered when
        signal characteristics suggest a hardware or placement issue rather
        than a genuine physiological event.

        TODO
        ----
        Replace with actual probe-issue detection logic:
        - Inspect signal_quality from the device.
        - Consider free-text patient_input for explicit reports (e.g. 'probe fell off').
        - Use temporal patterns (sudden drop to None followed by recovery) as
          additional evidence.
        """
        vs = record.vital_signs
        pi = record.patient_input

        # TODO: Replace with proprietary probe-issue detection logic.
        # Hint: patient_input.free_text may contain direct reports of probe problems.
        detected = False  # Placeholder.

        if not detected:
            return None

        features = AlertFeatures(
            min_spo2=vs.spo2,
            signal_quality_summary=vs.signal_quality,
        )
        return self._make_alert(record, "probe_issue", features)

    def _detect_activity_spike(
        self, record: VeritasRecord
    ) -> Optional[CandidateAlert]:
        """
        Detect a sudden or unexplained spike in physical activity.

        An activity spike may explain other anomalous readings (e.g. elevated
        HR that is benign because the patient was exercising) or may itself
        be clinically relevant (e.g. unexpected exertion in a cardiac patient).

        TODO
        ----
        Replace with actual activity-spike detection logic:
        - Compare current activity_level against the patient's typical pattern.
        - Use conversation_data.activities as corroborating context.
        - Consider EHR diagnoses that make certain activity levels concerning.
        """
        vs = record.vital_signs
        if vs.activity_level is None:
            return None

        # TODO: Replace with proprietary activity-spike detection logic.
        detected = False  # Placeholder.

        if not detected:
            return None

        features = AlertFeatures(
            avg_hr=vs.hr,
            avg_spo2=vs.spo2,
            activity_summary=vs.activity_level,
        )
        return self._make_alert(record, "activity_spike", features)
