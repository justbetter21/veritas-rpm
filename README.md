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
├── pipeline.py                 RPMPipeline — top-level orchestrator
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

example.py                      Runnable demonstration with 4 synthetic scenarios
requirements.txt                Python dependencies (pydantic only)
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
pipeline = RPMPipeline(cooldown_minutes={"doctor": 60, "nurse": 20, "patient": 10})
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
