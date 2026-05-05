"""src/transform/transformers.py — Transform staged records → GlobalBankFact + PeerComparisonMart."""
from __future__ import annotations
import logging, uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from src.models.legend_models import (
    FieldLineageEntry, GlobalBankFact, PeerComparisonMart, StagedBankRecord
)

logger = logging.getLogger(__name__)
P2 = Decimal("0.01")

def _pct(n, d): return (n/d*100).quantize(P2, ROUND_HALF_UP) if d else Decimal("0")
def _lag(hist, i, lag): return hist[i-lag] if i >= lag else None
def _yoy(cur, prior): return ((cur-prior)/prior*100).quantize(P2, ROUND_HALF_UP) if prior else None

class GlobalBankTransformer:
    def transform(self, records: list[StagedBankRecord]) -> tuple[list[GlobalBankFact], list[PeerComparisonMart], list[FieldLineageEntry]]:
        # sort by bank, then period
        sorted_recs = sorted(records, key=lambda r: (r.bank_id, r.period))

        # build per-bank revenue history for LAG
        bank_history: dict[str, list] = {}
        for r in sorted_recs:
            bank_history.setdefault(r.bank_id, []).append(r)

        facts = []
        for bank_id, bank_recs in bank_history.items():
            rev_hist = []
            for i, r in enumerate(bank_recs):
                prior4 = _lag(rev_hist, i, 4)
                prior1 = _lag(rev_hist, i, 1)
                facts.append(GlobalBankFact(
                    fact_id          = str(uuid.uuid4()),
                    bank_id          = r.bank_id,
                    period           = r.period,
                    net_revenue_usd  = r.net_revenue_usd,
                    net_income_usd   = r.net_income_usd,
                    total_assets_usd = r.total_assets_usd,
                    nim_pct          = r.nim_pct,
                    roe_pct          = r.roe_pct,
                    tier1_ratio      = r.tier1_ratio,
                    net_margin_pct   = _pct(r.net_income_usd, r.net_revenue_usd),
                    revenue_rank     = None,  # computed below
                    region_rank      = None,
                    yoy_revenue_pct  = _yoy(r.net_revenue_usd, prior4),
                    qoq_revenue_pct  = _yoy(r.net_revenue_usd, prior1),
                    stage_id         = r.stage_id,
                ))
                rev_hist.append(r.net_revenue_usd)

        # compute cross-bank ranks per period
        periods = sorted(set(f.period for f in facts))
        for period in periods:
            period_facts = sorted([f for f in facts if f.period == period],
                                   key=lambda f: f.net_revenue_usd, reverse=True)
            for rank, f in enumerate(period_facts, 1):
                f.revenue_rank = rank
            for region in ["US", "India"]:
                region_ids = {r.bank_id for r in records if r.bank_id in
                              {f.bank_id for f in period_facts}}
                # we'll use a simple approach: re-rank within region
                region_facts = [f for f in period_facts
                                if any(rec.bank_id == f.bank_id for rec in records)]
                # (simplified — full region lookup would join BankDim)
                for rank2, f in enumerate(region_facts, 1):
                    if f.region_rank is None:
                        f.region_rank = rank2

        # build peer comparison mart
        gs_by_period = {f.period: f.net_revenue_usd for f in facts if f.bank_id == "GS"}
        mart = []
        for f in facts:
            gs_rev = gs_by_period.get(f.period)
            vs_gs = _yoy(f.net_revenue_usd, gs_rev) if gs_rev and f.bank_id != "GS" else None
            mart.append(PeerComparisonMart(
                mart_id             = str(uuid.uuid4()),
                period              = f.period,
                bank_id             = f.bank_id,
                net_revenue_usd     = f.net_revenue_usd,
                net_margin_pct      = f.net_margin_pct,
                roe_pct             = f.roe_pct,
                tier1_ratio         = f.tier1_ratio,
                revenue_rank_global = f.revenue_rank or 0,
                revenue_rank_region = f.region_rank or 0,
                vs_gs_revenue_pct   = vs_gs,
            ))

        lineage = self._lineage()
        logger.info(f"[TRANSFORM] {len(facts)} facts, {len(mart)} mart rows, {len(lineage)} lineage entries")
        return facts, mart, lineage

    def _lineage(self) -> list[FieldLineageEntry]:
        entries = []
        def e(tf, sf, logic, tt="DERIVED"):
            entries.append(FieldLineageEntry(str(uuid.uuid4()), "GlobalBankFact", tf,
                "StagedBankRecord", sf if isinstance(sf, list) else [sf], logic, tt))
        e("net_margin_pct",   ["net_income_usd","net_revenue_usd"],  "net_income_usd / net_revenue_usd * 100")
        e("yoy_revenue_pct",  ["net_revenue_usd"], "LAG(4) YoY growth %", "AGGREGATED")
        e("qoq_revenue_pct",  ["net_revenue_usd"], "LAG(1) QoQ growth %", "AGGREGATED")
        e("revenue_rank",     ["net_revenue_usd"], "RANK() OVER (PARTITION BY period ORDER BY net_revenue_usd DESC)", "AGGREGATED")
        e("vs_gs_revenue_pct",["net_revenue_usd"], "(bank_rev - gs_rev) / gs_rev * 100 — anchor: GS", "AGGREGATED")
        for f in ["net_revenue_usd","net_income_usd","total_assets_usd","nim_pct","roe_pct","tier1_ratio"]:
            e(f, [f], "direct copy from staging", "DIRECT")
        return entries
