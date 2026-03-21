# Veritas-RPM: Multi-Agent Reference Architecture for Remote Patient Monitoring

> **Research and educational code only.**
> This repository is **not a certified medical device** and **must not be used
> for clinical decision-making**.  No clinical thresholds, triage rules, or
> proprietary decision logic are included.  All specialist-agent `evaluate()`
> methods contain clearly marked `# TODO` placeholders where such logic would go.

---

## Overview

This repository is a public, self-contained Python reference implementation of the
**Veritas–Sentinel–Director–MetaSentinel** architecture — a provenance-guided
multi-agent system designed for Remote Patient Monitoring (RPM).

The goal is to demonstrate:

- How four ground-truth sources are assembled into a single patient record.
- How a layered agent architecture detects, routes, evaluates, and suppresses
  alerts before they reach clinical staff.
- How provenance tags flow through the pipeline to inform decision-making.
- How cooldown / debouncing protects staff from continuous alerts.

It is structured so that researchers or engineers can extend it by filling in
the `TODO` sections with their own domain-specific logic.

---

## Architecture

```
Ground-Truth Sources
┌──────┐  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
│ EHR  │  │ Conversations│  │ Vital Signs │  │ Patient Input│
└──┬───┘  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘
   │             │                 │                 │
   └─────────────┴─────────────────┴─────────────────┘
                             │
                     ┌───────▼────────┐
                     │  VeritasAgent  │  Assembles all sources + provenance tags
                     └───────┬────────┘
                             │  VeritasRecord (stream)
                     ┌───────▼────────┐
                     │  SentinelLayer │  Detects signal anomalies
                     └───────┬────────┘
                             │  CandidateAlert
                     ┌───────▼────────┐
                     │ DirectorAgent  │  Routes to relevant specialist agents
                     └───────┬────────┘
               ┌─────────────┼─────────────┐
       ┌───────▼──────┐  ┌───▼────┐  ┌────▼──────────────┐
       │ Tachycardia  │  │  COPD  │  │ ProbeIntegrity     │
       │ Bradycardia  │  │ Agent  │  │ ActivityIntegrity  │
       │   Nocturnal  │  └───┬────┘  │ (+ others)         │
       └───────┬──────┘      │       └────┬───────────────-┘
               └─────────────┴────────────┘
                             │  AgentClaim (×N)
                     ┌───────▼────────────┐
                     │ MetaSentinelAgent  │  Aggregates + applies cooldown
                     └───────┬────────────┘
                             │  SystemDecision
                     ┌───────▼────────┐
                     │DashboardService│  Routes to patient / nurse / doctor
                     └───────┬────────┘
                             │
              ┌──────────────┼──────────────┐
           Patient         Nurse          Doctor
```

### The four core data objects

| Object | Produced by | Consumed by | Purpose |
|---|---|---|---|
| `VeritasRecord` | VeritasAgent | SentinelLayer | Unified, provenance-tagged patient snapshot |
| `CandidateAlert` | SentinelLayer | DirectorAgent | Potential anomaly with aggregated features |
| `AgentClaim` | Specialist agents | MetaSentinelAgent | Specialist interpretation + risk level |
| `SystemDecision` | MetaSentinelAgent | DashboardService | Final action routed to a human role |

---

## Repository Structure

```
veritas_rpm/
├── __init__.py                 Package init; exports public API
├── models.py                   Pydantic data models for all four core objects
├── config.py                   Configuration dataclasses (PipelineConfig, CooldownConfig,
│                               RoutingConfig)
├── exceptions.py               Custom exception hierarchy (VeritasRPMError, …)
├── metrics.py                  Pipeline-level metrics (PipelineMetrics)
├── pipeline.py                 RPMPipeline — top-level synchronous orchestrator
├── async_pipeline.py           AsyncRPMPipeline — async variant for event-loop apps
├── agents/
│   ├── __init__.py
│   ├── veritas_agent.py        Ingests raw sources; emits VeritasRecord
│   ├── sentinel_layer.py       Signal detectors; emits CandidateAlert
│   ├── director_agent.py       Routes alerts to specialist agents
│   ├── specialist_agents.py    TachycardiaAgent, BradycardiaAgent, COPDAgent,
│   │                           NocturnalAgent, ActivityIntegrityAgent,
│   │                           ProbeIntegrityAgent
│   └── meta_sentinel_agent.py  Aggregates claims; enforces cooldown
└── services/
    ├── __init__.py
    └── dashboard_service.py    Routes decisions to patient / nurse / doctor

tests/                          Pytest test suite (73 tests)
example.py                      Runnable demonstration with 4 synthetic scenarios
requirements.txt                Python dependencies (pydantic only)
requirements-dev.txt            Dev dependencies (pytest, pytest-asyncio)
README.md                       This file
```

---

## Quickstart

### Requirements

- Python 3.9 or later
- [pydantic](https://docs.pydantic.dev/) v2

### Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/veritas-rpm.git
cd veritas-rpm

# Install dependencies
pip install -r requirements.txt
```

### Run the example

```bash
python example.py
```

This runs four synthetic scenarios through the full pipeline and prints the
resulting `SystemDecision` objects to the terminal.

### Run the tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

---

## Configuration

All tuneable parameters are centralised in `PipelineConfig`:

```python
from veritas_rpm import RPMPipeline, PipelineConfig
from veritas_rpm.config import CooldownConfig, RoutingConfig

config = PipelineConfig(
    cooldown=CooldownConfig(
        doctor_minutes=60,
        nurse_minutes=20,
        patient_minutes=10,
    ),
    routing=RoutingConfig(
        routing_table={
            "tachycardia": ["TachycardiaAgent", "ActivityIntegrityAgent"],
            "desaturation": ["ProbeIntegrityAgent", "COPDAgent"],
            # ... add or remove agent mappings as needed
        },
    ),
)

pipeline = RPMPipeline(config=config)
```

### Configuration classes

| Class | Purpose | Key fields |
|---|---|---|
| `PipelineConfig` | Top-level container | `cooldown`, `routing` |
| `CooldownConfig` | Per-role cooldown durations | `doctor_minutes`, `nurse_minutes`, `patient_minutes` |
| `RoutingConfig` | Maps alert types to specialist agent names | `routing_table` (Dict[str, List[str]]) |

---

## Logging

The library uses Python's standard `logging` module.  No log handlers are
configured by the library itself — the caller controls output format and level:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

pipeline = RPMPipeline()
# All pipeline components now emit structured log messages
```

---

## Error Handling

Custom exceptions are defined in `veritas_rpm.exceptions`:

| Exception | Raised when |
|---|---|
| `VeritasRPMError` | Base class for all package exceptions |
| `NoDataIngestedError` | `build_record()` called before any `ingest_*()` method |
| `InvalidRoleError` | An unknown role string is passed to `acknowledge()` |
| `ValidationError` | Input data fails validation (empty patient_id, wrong types, etc.) |
| `AgentEvaluationError` | A specialist agent fails during evaluation |

All exceptions inherit from `VeritasRPMError`, so callers can catch the full
family with a single `except VeritasRPMError` clause.

---

## Async Support

For event-loop-based applications (FastAPI, aiohttp, etc.), use `AsyncRPMPipeline`:

```python
import asyncio
from veritas_rpm.async_pipeline import AsyncRPMPipeline

async def main():
    pipeline = AsyncRPMPipeline()
    pipeline.ingest_ehr("patient-001", ehr_dict)
    pipeline.ingest_vitals("patient-001", vitals_dict)

    record = await pipeline.process("patient-001")
    print(pipeline.get_all_decisions())

asyncio.run(main())
```

The sync `RPMPipeline` remains fully supported and is recommended for scripts,
notebooks, and batch processing.

---

## Metrics

Each pipeline instance tracks operational metrics via `PipelineMetrics`:

```python
pipeline = RPMPipeline()
# ... ingest and process patients ...

summary = pipeline.get_metrics_summary()
# {
#     "alerts_generated": 12,
#     "alerts_suppressed": 3,
#     "alerts_delivered": 9,
#     "suppression_rate": 0.25,
#     "decisions_by_action": {"queue_for_nurse": 7, "suppress": 3, ...},
#     "decisions_by_priority": {"normal": 8, "low": 4},
#     "agent_invocation_count": {"TachycardiaAgent": 5, ...},
#     "agent_total_time_ms": {"TachycardiaAgent": 1.23, ...},
# }
```

Metrics are useful for:
- Monitoring suppression rates to tune cooldown parameters.
- Identifying slow specialist agents.
- Tracking alert volume across pipeline runs.

---

## Synthetic Scenarios (in `example.py`)

| # | Scenario | Key context clues | Expected outcome |
|---|---|---|---|
| 1 | Exertional tachycardia | COPD, moderate activity, post-walk | Suppress / notify patient |
| 2 | Probe displacement | `no_signal`, patient says "probe fell off" | Suppress / notify patient to reattach |
| 3 | Nocturnal bradycardia | Beta-blocker medication, 02:00, resting | Suppress |
| 4 | Unexplained desaturation | No COPD, resting, good signal, SpO₂ drop | Nurse queue / doctor escalation |

> Because all `evaluate()` methods are stubs, the actual outputs are placeholder
> values.  Fill in the `TODO` sections to see clinically-informed outputs.

---

## Provenance System

Every field in `VeritasRecord` carries a `ProvenanceTag` in the `provenance`
dict.  Tags indicate how much trust should be placed in a piece of information:

| Tag | Meaning |
|---|---|
| `EHR_verified` | Read directly from a structured EHR record |
| `human_confirmed` | A clinician explicitly confirmed the value |
| `LLM_extracted_dual_confirmed` | LLM extraction validated by a second pass |
| `LLM_extracted_unconfirmed` | LLM extraction; no secondary confirmation |
| `device_stream` | Live data from an RPM device; no further validation |

Specialist agents and MetaSentinelAgent are expected to inspect provenance when
weighting evidence.  Low-trust fields (`LLM_extracted_unconfirmed`) should be
treated as contextual hints rather than facts.

---

## Extending the Pipeline

### Implementing a specialist agent

To fill in one of the `TODO` methods, subclass `SpecialistAgent` (or edit the
existing class) and implement `evaluate()`:

```python
from veritas_rpm.agents.specialist_agents import TachycardiaAgent
from veritas_rpm.models import AgentClaim, CandidateAlert, VeritasRecord

class MyTachycardiaAgent(TachycardiaAgent):
    def evaluate(self, alert: CandidateAlert, context: VeritasRecord) -> AgentClaim:
        baseline = context.ehr_data.baseline_hr or 75.0
        activity = context.vital_signs.activity_level or "resting"
        max_hr = alert.features.max_hr or 0.0

        # Your clinical logic here
        if activity in ("moderate", "vigorous") and max_hr < baseline * 1.5:
            classification = "benign_exertional_tachycardia"
            risk_level = "low"
            action = "suppress"
        else:
            classification = "possible_clinical_tachycardia"
            risk_level = "moderate"
            action = "queue_for_nurse"

        return self._stub_claim(
            alert=alert,
            classification=classification,
            risk_level=risk_level,
            recommended_action=action,
            justification=f"HR {max_hr} bpm; activity={activity}; baseline={baseline}",
            used_fields=["vital_signs.hr", "vital_signs.activity_level", "ehr_data.baseline_hr"],
        )
```

Then inject your agent into `DirectorAgent`:

```python
from veritas_rpm.pipeline import RPMPipeline

pipeline = RPMPipeline()
pipeline.director._tachycardia_agent = MyTachycardiaAgent()
```

### Adjusting cooldown windows

```python
from veritas_rpm import RPMPipeline, PipelineConfig
from veritas_rpm.config import CooldownConfig

pipeline = RPMPipeline(config=PipelineConfig(
    cooldown=CooldownConfig(doctor_minutes=60, nurse_minutes=20, patient_minutes=10),
))
```

### Receiving decisions via callback

```python
pipeline.meta.on_decision(lambda d: print(f"Decision: {d.final_action} → {d.target_role}"))
```

---

## Design Principles

1. **Provenance-first** — every piece of data carries a trust label.  Agents
   that ignore provenance risk acting on unverified information.
2. **Strict layering** — SentinelLayer never sees raw EHR text; DashboardService
   never makes clinical decisions; VeritasAgent never interacts with humans.
3. **Cooldown as a citizen right** — staff have a right to interruption-free
   periods.  MetaSentinelAgent enforces configurable quiet windows per patient
   per role.
4. **Pluggable clinical logic** — all proprietary rules live behind `# TODO`
   markers and abstract interfaces.  The framework can be adopted without
   revealing any existing production logic.
5. **Observable by design** — structured logging, pipeline metrics, and audit
   trails support monitoring and debugging in production environments.

---

## Disclaimer

This software is provided for **research and educational purposes only**.

- It has **not** been validated for clinical use.
- It **does not** contain any clinically safe thresholds, triage rules, or
  decision algorithms.
- It **must not** be used to inform real patient care decisions.
- The authors accept no liability for any use of this code in clinical contexts.

---

## Licence

MIT — see `LICENSE` for details.
