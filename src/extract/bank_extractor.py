"""
src/extract/bank_extractor.py
Extracts raw records from Bloomberg (US banks) and BSE/NSE filings (Indian banks).
"""
from __future__ import annotations
import json, logging
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from src.models.legend_models import RawBankRecord, BankDim, Region, BankSector

logger = logging.getLogger(__name__)

FX_RATES = {"USD": Decimal("1.0"), "INR": Decimal("83.5")}

class GlobalBankExtractor:
    def __init__(self, data_path: str = "data/global_banks_raw.json"):
        self.data_path = Path(data_path)

    def extract(self) -> tuple[list[BankDim], list[RawBankRecord]]:
        with open(self.data_path) as f:
            payload = json.load(f)

        dims, records = [], []
        for bank in payload["banks"]:
            dims.append(BankDim(
                bank_id          = bank["bank_id"],
                name             = bank["name"],
                region           = Region(bank["region"]),
                exchange         = bank["exchange"],
                index_membership = bank["index"],
                sector           = BankSector(bank["sector"]),
                currency_native  = bank["currency_native"],
            ))
            for rec in bank["records"]:
                records.append(RawBankRecord(
                    bank_id      = bank["bank_id"],
                    period       = rec["period"],
                    net_revenue  = Decimal(str(rec["net_revenue"])),
                    net_income   = Decimal(str(rec["net_income"])),
                    total_assets = Decimal(str(rec["total_assets"])),
                    nim_pct      = Decimal(str(rec["nim_pct"])) if rec["nim_pct"] else None,
                    roe_pct      = Decimal(str(rec["roe_pct"])) if rec["roe_pct"] else None,
                    tier1_ratio  = Decimal(str(rec["tier1_ratio"])) if rec["tier1_ratio"] else None,
                    source_ref   = rec["source"],
                    load_timestamp = datetime.utcnow(),
                ))

        logger.info(f"[EXTRACT] {len(dims)} banks, {len(records)} records")
        return dims, records

    def fx_rate(self, bank_id: str, dims: list[BankDim]) -> Decimal:
        dim = next((d for d in dims if d.bank_id == bank_id), None)
        return FX_RATES.get(dim.currency_native if dim else "USD", Decimal("1.0"))
