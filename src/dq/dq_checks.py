"""src/dq/dq_checks.py — DQ engine for global bank pipeline."""
from __future__ import annotations
import logging, uuid
from datetime import datetime
from decimal import Decimal
from src.models.legend_models import DQCheckResult, DQCheckType, DQStatus, StagedBankRecord

logger = logging.getLogger(__name__)

class DQEngine:
    def run(self, records: list[StagedBankRecord]) -> tuple[list[DQCheckResult], list[StagedBankRecord]]:
        all_results, failed_ids = [], set()
        for fn in [self._null_key, self._duplicate, self._range, self._integrity]:
            result, bad = fn(records)
            all_results.append(result)
            failed_ids.update(bad)
            if result.status == DQStatus.FAIL:
                logger.warning(f"[DQ ALERT] {result.check_type.value} FAIL — {result.detail}")
        passed = [r for r in records if (r.bank_id, r.period) not in failed_ids]
        logger.info(f"[DQ] {len(passed)}/{len(records)} records passed")
        return all_results, passed

    def _null_key(self, records):
        bad = {(r.bank_id, r.period) for r in records if not r.bank_id or not r.period}
        st = DQStatus.FAIL if bad else DQStatus.PASS
        return DQCheckResult(str(uuid.uuid4()), "stg_bank_records", DQCheckType.NULL_KEY,
            datetime.utcnow(), len(records), len(bad), st, bool(bad),
            f"{len(bad)} null-key rows" if bad else "OK"), bad

    def _duplicate(self, records):
        seen, dupes = {}, set()
        for r in records:
            key = (r.bank_id, r.period)
            if key in seen: dupes.add(key)
            seen[key] = r
        st = DQStatus.FAIL if dupes else DQStatus.PASS
        return DQCheckResult(str(uuid.uuid4()), "stg_bank_records", DQCheckType.DUPLICATE_PERIOD,
            datetime.utcnow(), len(records), len(dupes), st, bool(dupes),
            f"{len(dupes)} duplicate (bank,period) pairs" if dupes else "OK"), dupes

    def _range(self, records):
        bad = {(r.bank_id, r.period) for r in records
               if r.net_revenue_usd <= 0 or r.net_revenue_usd > Decimal("500000")}
        st = DQStatus.WARN if bad else DQStatus.PASS
        return DQCheckResult(str(uuid.uuid4()), "stg_bank_records", DQCheckType.RANGE_CHECK,
            datetime.utcnow(), len(records), len(bad), st, False,
            f"{len(bad)} out-of-range revenues" if bad else "OK"), set()

    def _integrity(self, records):
        bad = {(r.bank_id, r.period) for r in records
               if r.net_income_usd is None or r.total_assets_usd <= 0}
        st = DQStatus.FAIL if bad else DQStatus.PASS
        return DQCheckResult(str(uuid.uuid4()), "stg_bank_records", DQCheckType.REFERENTIAL_INTEGRITY,
            datetime.utcnow(), len(records), len(bad), st, bool(bad),
            f"{len(bad)} integrity failures" if bad else "OK"), bad
