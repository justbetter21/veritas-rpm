"""
async_pipeline.py — AsyncRPMPipeline: async variant of the pipeline orchestrator.

This module provides an async-compatible pipeline that mirrors RPMPipeline
but uses ``await`` for the pub/sub callback chain.  All specialist agent
``evaluate()`` methods remain synchronous (they are CPU-bound) — only the
inter-component wiring is async.

Typical usage
-------------
    import asyncio
    from veritas_rpm.async_pipeline import AsyncRPMPipeline

    async def main():
        pipeline = AsyncRPMPipeline()
        pipeline.ingest_ehr("patient-001", ehr_dict)
        pipeline.ingest_vitals("patient-001", vitals_dict)
        record = await pipeline.process("patient-001")
        print(pipeline.get_all_decisions())

    asyncio.run(main())
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from veritas_rpm.agents.director_agent import DirectorAgent
from veritas_rpm.agents.meta_sentinel_agent import MetaSentinelAgent
from veritas_rpm.agents.sentinel_layer import SentinelLayer
from veritas_rpm.agents.veritas_agent import VeritasAgent
from veritas_rpm.config import PipelineConfig
from veritas_rpm.metrics import PipelineMetrics
from veritas_rpm.models import SystemDecision, VeritasRecord
from veritas_rpm.services.dashboard_service import DashboardService

logger = logging.getLogger(__name__)


class AsyncRPMPipeline:
    """
    Async-compatible end-to-end orchestrator.

    The synchronous components (detectors, specialist agents) run in the
    calling coroutine.  The async layer allows the pipeline to be embedded
    in event-loop-based applications (e.g. FastAPI, aiohttp) without
    blocking the loop for I/O-bound extensions.
    """

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
    ) -> None:
        if config is None:
            config = PipelineConfig()

        self.metrics = PipelineMetrics()

        self.dashboard = DashboardService()

        self.meta = MetaSentinelAgent(
            cooldown_config=config.cooldown,
            dashboard_service=self.dashboard,
            metrics=self.metrics,
        )

        self.director = DirectorAgent(
            meta_sentinel=self.meta,
            routing_config=config.routing,
            metrics=self.metrics,
        )

        self.sentinel = SentinelLayer(
            director=self.director,
            metrics=self.metrics,
        )

        self.veritas = VeritasAgent()

        # Wire DashboardService back-references
        self.dashboard._veritas_agent = self.veritas
        self.dashboard._meta_sentinel = self.meta

    # ------------------------------------------------------------------
    # Ingest delegates (sync — no I/O involved)
    # ------------------------------------------------------------------

    def ingest_ehr(self, patient_id: str, raw: Dict[str, Any]) -> None:
        self.veritas.ingest_ehr(patient_id, raw)

    def ingest_conversation(self, patient_id: str, raw: Dict[str, Any]) -> None:
        self.veritas.ingest_conversation(patient_id, raw)

    def ingest_vitals(self, patient_id: str, raw: Dict[str, Any]) -> None:
        self.veritas.ingest_vitals(patient_id, raw)

    def ingest_patient_input(self, patient_id: str, raw: Dict[str, Any]) -> None:
        self.veritas.ingest_patient_input(patient_id, raw)

    # ------------------------------------------------------------------
    # Async processing
    # ------------------------------------------------------------------

    async def process(self, patient_id: str) -> VeritasRecord:
        """
        Build a VeritasRecord and run it through the pipeline asynchronously.

        The detection and evaluation steps are CPU-bound and run synchronously
        within this coroutine.  The async boundary allows callers to ``await``
        this method inside an event loop and enables future extension points
        (e.g. async database writes, async notification delivery) without
        changing the public interface.

        Parameters
        ----------
        patient_id:
            The patient for whom to run the pipeline.

        Returns
        -------
        VeritasRecord
            The assembled record.
        """
        # Build record (sync — fast, in-memory)
        record = self.veritas.build_record(patient_id)

        # Update director context
        self.director.update_context(record)

        # Run sentinel detectors (sync — CPU-bound)
        alerts = self.sentinel.on_record(record)

        logger.info(
            "Async pipeline processed patient=%s  alerts=%d",
            patient_id,
            len(alerts),
        )

        return record

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def get_all_decisions(self) -> List[SystemDecision]:
        return (
            self.dashboard.get_patient_queue()
            + self.dashboard.get_nurse_queue()
            + self.dashboard.get_doctor_queue()
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        return self.metrics.summary()
