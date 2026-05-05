"""
pipeline.py — Global Banking Revenue Intelligence Pipeline orchestrator.
11 banks: GS, JPM, BAC, WFC, MS, C (S&P500) + HDFC, SBI, ICICI, Axis, Kotak (India)
"""
from __future__ import annotations
import logging
from decimal import Decimal
from src.extract.bank_extractor import GlobalBankExtractor
from src.models.legend_models import DQStatus, StagedBankRecord
from src.dq.dq_checks import DQEngine
from src.transform.transformers import GlobalBankTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

REGION_MAP = {"GS":"US","JPM":"US","BAC":"US","WFC":"US","MS":"US","C":"US",
              "HDFC":"India","SBI":"India","ICICI":"India","AXISBANK":"India","KOTAK":"India"}
FX = {"US": Decimal("1.0"), "India": Decimal("8.35")}

def run():
    logger.info("="*60)
    logger.info("Global Banking Revenue Intelligence Pipeline")
    logger.info("S&P500 Banks + Top Indian Banks | Legend/Pure ETL")
    logger.info("="*60)

    # 1. Extract
    extractor = GlobalBankExtractor()
    dims, raw_records = extractor.extract()
    logger.info(f"[1/4] EXTRACT: {len(dims)} banks, {len(raw_records)} raw records")

    # 2. Stage + currency normalise
    staged = []
    for r in raw_records:
        region = REGION_MAP.get(r.bank_id, "US")
        fx = FX[region]
        staged.append(StagedBankRecord.from_raw(r, fx, DQStatus.PASS))

    # 3. DQ
    dq_engine = DQEngine()
    dq_results, passed = dq_engine.run(staged)
    logger.info(f"[2/4] DQ: {len(dq_results)} checks, {len(passed)}/{len(staged)} passed")

    # 4. Transform
    transformer = GlobalBankTransformer()
    facts, mart, lineage = transformer.transform(passed)
    logger.info(f"[3/4] TRANSFORM: {len(facts)} facts, {len(mart)} mart rows")

    # 5. Print report
    print_report(facts, mart, dims)
    logger.info("[4/4] Pipeline complete")

def print_report(facts, mart, dims):
    PERIODS = ["Q1_2024","Q2_2024","Q3_2024","Q4_2024","Q1_2025","Q2_2025"]
    BANKS   = ["JPM","BAC","WFC","C","MS","GS","HDFC","SBI","ICICI","AXISBANK","KOTAK"]

    print()
    print("╔══════════════════════════════════════════════════════════════════════════════════════╗")
    print("║         Global Banking Revenue Intelligence — Net Revenue (USD mn)                  ║")
    print("╠══════════╦" + "═"*10*len(PERIODS) + "╣")
    header = "║ Bank     ║" + "".join(f" {p:<9}║" for p in PERIODS)
    print(header)
    print("╠══════════╬" + "╬".join(["═"*10]*len(PERIODS)) + "╣")

    fact_map = {(f.bank_id, f.period): f for f in facts}
    for bid in BANKS:
        row = f"║ {bid:<8} ║"
        for p in PERIODS:
            f = fact_map.get((bid, p))
            row += f" {float(f.net_revenue_usd):>8,.0f} ║" if f else "        — ║"
        print(row)
    print("╚══════════╩" + "╩".join(["═"*10]*len(PERIODS)) + "╝")

    print()
    print("── Peer Comparison vs GS (Q1 2025) ─────────────────────────────")
    q1_mart = sorted([m for m in mart if m.period == "Q1_2025"],
                      key=lambda m: m.net_revenue_usd, reverse=True)
    print(f"  {'Bank':<12} {'Rev(USD mn)':>12} {'Margin%':>8} {'ROE%':>7} {'vs GS':>9} {'Rank':>5}")
    print("  " + "-"*55)
    for m in q1_mart:
        vs = f"{float(m.vs_gs_revenue_pct):+.1f}%" if m.vs_gs_revenue_pct else "  base"
        print(f"  {m.bank_id:<12} {float(m.net_revenue_usd):>12,.0f} {float(m.net_margin_pct):>7.1f}% "
              f"{float(m.roe_pct) if m.roe_pct else 0:>6.1f}% {vs:>9} #{m.revenue_rank_global}")
    print()

if __name__ == "__main__":
    run()
