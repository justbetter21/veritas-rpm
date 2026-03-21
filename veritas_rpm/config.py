"""
config.py — Configuration dataclasses for the Veritas-RPM pipeline.

These dataclasses centralise all tuneable parameters that were previously
hard-coded across multiple modules.  Passing a ``PipelineConfig`` to
``RPMPipeline`` (or ``AsyncRPMPipeline``) makes the system fully
configurable from a single point.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class CooldownConfig:
    """Per-role cooldown durations in minutes."""

    doctor_minutes: int = 30
    nurse_minutes: int = 15
    patient_minutes: int = 5

    def as_dict(self) -> Dict[str, int]:
        return {
            "doctor": self.doctor_minutes,
            "nurse": self.nurse_minutes,
            "patient": self.patient_minutes,
        }


@dataclass
class RoutingConfig:
    """Maps alert_type strings to lists of specialist-agent name strings."""

    routing_table: Dict[str, List[str]] = field(default_factory=lambda: {
        "tachycardia": ["TachycardiaAgent", "ActivityIntegrityAgent", "ProbeIntegrityAgent"],
        "bradycardia": ["BradycardiaAgent", "NocturnalAgent"],
        "desaturation": ["ProbeIntegrityAgent", "COPDAgent", "NocturnalAgent"],
        "flatline": ["ProbeIntegrityAgent"],
        "nocturnal_event": ["NocturnalAgent", "COPDAgent", "ProbeIntegrityAgent"],
        "probe_issue": ["ProbeIntegrityAgent", "ActivityIntegrityAgent"],
        "activity_spike": ["ActivityIntegrityAgent", "TachycardiaAgent"],
        "other": ["TachycardiaAgent", "BradycardiaAgent", "ProbeIntegrityAgent"],
    })


@dataclass
class PipelineConfig:
    """Top-level configuration for RPMPipeline."""

    cooldown: CooldownConfig = field(default_factory=CooldownConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
