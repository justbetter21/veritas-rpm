"""
metrics.py — Pipeline-level metrics for observability and performance monitoring.

Each ``RPMPipeline`` instance owns a ``PipelineMetrics`` object that
accumulates counters and timing data as records flow through the system.
Call ``metrics.summary()`` at any point to obtain a JSON-serialisable
snapshot of the current state.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Dict

from veritas_rpm.models import SystemDecision


@dataclass
class PipelineMetrics:
    """Accumulates pipeline-wide counters and timing information."""

    alerts_generated: int = 0
    alerts_suppressed: int = 0
    alerts_delivered: int = 0

    decisions_by_action: Dict[str, int] = field(default_factory=dict)
    decisions_by_priority: Dict[str, int] = field(default_factory=dict)

    agent_invocation_count: Dict[str, int] = field(default_factory=dict)
    agent_total_time_ms: Dict[str, float] = field(default_factory=dict)

    def record_alert_generated(self) -> None:
        self.alerts_generated += 1

    def record_decision(self, decision: SystemDecision) -> None:
        action = decision.final_action
        self.decisions_by_action[action] = self.decisions_by_action.get(action, 0) + 1

        priority = decision.priority
        self.decisions_by_priority[priority] = self.decisions_by_priority.get(priority, 0) + 1

        if action == "suppress":
            self.alerts_suppressed += 1
        else:
            self.alerts_delivered += 1

    def record_agent_invocation(self, agent_name: str, elapsed_ms: float) -> None:
        self.agent_invocation_count[agent_name] = (
            self.agent_invocation_count.get(agent_name, 0) + 1
        )
        self.agent_total_time_ms[agent_name] = (
            self.agent_total_time_ms.get(agent_name, 0.0) + elapsed_ms
        )

    @property
    def suppression_rate(self) -> float:
        """Fraction of generated alerts that were suppressed."""
        if self.alerts_generated == 0:
            return 0.0
        return self.alerts_suppressed / self.alerts_generated

    def summary(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of all metrics."""
        return {
            "alerts_generated": self.alerts_generated,
            "alerts_suppressed": self.alerts_suppressed,
            "alerts_delivered": self.alerts_delivered,
            "suppression_rate": round(self.suppression_rate, 4),
            "decisions_by_action": dict(self.decisions_by_action),
            "decisions_by_priority": dict(self.decisions_by_priority),
            "agent_invocation_count": dict(self.agent_invocation_count),
            "agent_total_time_ms": {
                k: round(v, 2) for k, v in self.agent_total_time_ms.items()
            },
        }
