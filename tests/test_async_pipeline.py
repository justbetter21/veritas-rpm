"""Tests for AsyncRPMPipeline."""

from __future__ import annotations

import pytest

from veritas_rpm.async_pipeline import AsyncRPMPipeline


@pytest.mark.asyncio
async def test_async_process(sample_ehr_raw, sample_vitals_raw):
    pipeline = AsyncRPMPipeline()
    pipeline.ingest_ehr("p1", sample_ehr_raw)
    pipeline.ingest_vitals("p1", sample_vitals_raw)
    record = await pipeline.process("p1")
    assert record.patient_id == "p1"
    assert record.vital_signs.hr == 108.0


@pytest.mark.asyncio
async def test_async_metrics(sample_ehr_raw, sample_vitals_raw):
    pipeline = AsyncRPMPipeline()
    pipeline.ingest_ehr("p1", sample_ehr_raw)
    pipeline.ingest_vitals("p1", sample_vitals_raw)
    await pipeline.process("p1")
    summary = pipeline.get_metrics_summary()
    assert summary["alerts_generated"] == 0


@pytest.mark.asyncio
async def test_async_decisions(sample_ehr_raw, sample_vitals_raw):
    pipeline = AsyncRPMPipeline()
    pipeline.ingest_ehr("p1", sample_ehr_raw)
    pipeline.ingest_vitals("p1", sample_vitals_raw)
    await pipeline.process("p1")
    decisions = pipeline.get_all_decisions()
    assert isinstance(decisions, list)
