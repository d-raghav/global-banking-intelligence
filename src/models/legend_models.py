"""
src/models/legend_models.py
Pure/Legend class definitions mirrored as Python dataclasses.
Package: model::global::banking
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


class Region(Enum):
    US    = "US"
    INDIA = "India"

class BankSector(Enum):
    INVESTMENT_BANKING  = "Investment Banking"
    UNIVERSAL_BANKING   = "Universal Banking"
    PRIVATE_SECTOR_BANK = "Private Sector Bank"
    PUBLIC_SECTOR_BANK  = "Public Sector Bank"

class DQStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"

class DQCheckType(Enum):
    NULL_KEY             = "NULL_KEY"
    DUPLICATE_PERIOD     = "DUPLICATE_PERIOD"
    RANGE_CHECK          = "RANGE_CHECK"
    REFERENTIAL_INTEGRITY= "REFERENTIAL_INTEGRITY"
    CURRENCY_NORM        = "CURRENCY_NORM"


@dataclass
class BankDim:
    """model::global::banking::dim::BankDim — dimension table for each bank entity."""
    bank_id:          str
    name:             str
    region:           Region
    exchange:         str
    index_membership: str          # SP500 / NIFTY50
    sector:           BankSector
    currency_native:  str          # USD or INR
    is_active:        bool = True


@dataclass
class RawBankRecord:
    """model::global::banking::source::RawBankRecord — one row from Bloomberg/BSE feed."""
    bank_id:       str
    period:        str             # e.g. "Q1_2024"
    net_revenue:   Decimal         # native currency
    net_income:    Decimal
    total_assets:  Decimal
    nim_pct:       Optional[Decimal]
    roe_pct:       Optional[Decimal]
    tier1_ratio:   Optional[Decimal]
    source_ref:    str
    load_timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class StagedBankRecord:
    """model::global::banking::staging::StagedBankRecord — DQ-gated, currency-normalised."""
    stage_id:          str
    bank_id:           str
    period:            str
    net_revenue_usd:   Decimal     # normalised to USD millions
    net_income_usd:    Decimal
    total_assets_usd:  Decimal
    nim_pct:           Optional[Decimal]
    roe_pct:           Optional[Decimal]
    tier1_ratio:       Optional[Decimal]
    fx_rate_used:      Decimal     # 1.0 for USD banks, ~83.5 for INR banks
    dq_status:         DQStatus
    source_ref:        str
    loaded_at:         datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_raw(cls, raw: RawBankRecord, fx_rate: Decimal, dq_status: DQStatus) -> StagedBankRecord:
        return cls(
            stage_id         = str(uuid.uuid4()),
            bank_id          = raw.bank_id,
            period           = raw.period,
            net_revenue_usd  = (raw.net_revenue / fx_rate).quantize(Decimal("0.01")),
            net_income_usd   = (raw.net_income  / fx_rate).quantize(Decimal("0.01")),
            total_assets_usd = (raw.total_assets / fx_rate).quantize(Decimal("0.01")),
            nim_pct          = raw.nim_pct,
            roe_pct          = raw.roe_pct,
            tier1_ratio      = raw.tier1_ratio,
            fx_rate_used     = fx_rate,
            dq_status        = dq_status,
            source_ref       = raw.source_ref,
        )


@dataclass
class GlobalBankFact:
    """model::global::banking::cdw::GlobalBankFact — star-schema CDW fact."""
    fact_id:            str
    bank_id:            str
    period:             str
    # source fields
    net_revenue_usd:    Decimal
    net_income_usd:     Decimal
    total_assets_usd:   Decimal
    nim_pct:            Optional[Decimal]
    roe_pct:            Optional[Decimal]
    tier1_ratio:        Optional[Decimal]
    # derived metrics
    net_margin_pct:     Decimal
    revenue_rank:       Optional[int]       # rank within period across all banks
    region_rank:        Optional[int]       # rank within region & period
    yoy_revenue_pct:    Optional[Decimal]   # LAG(4) YoY growth
    qoq_revenue_pct:    Optional[Decimal]   # LAG(1) QoQ growth
    # audit
    stage_id:           str
    loaded_at:          datetime = field(default_factory=datetime.utcnow)


@dataclass
class PeerComparisonMart:
    """model::global::banking::mart::PeerComparisonMart — pre-agg cross-bank comparison."""
    mart_id:             str
    period:              str
    bank_id:             str
    net_revenue_usd:     Decimal
    net_margin_pct:      Decimal
    roe_pct:             Optional[Decimal]
    tier1_ratio:         Optional[Decimal]
    revenue_rank_global: int
    revenue_rank_region: int
    vs_gs_revenue_pct:   Optional[Decimal]  # pct diff vs GS (anchor bank)
    refreshed_at:        datetime = field(default_factory=datetime.utcnow)


@dataclass
class DQCheckResult:
    check_id:       str
    table_name:     str
    check_type:     DQCheckType
    run_timestamp:  datetime
    rows_loaded:    int
    fail_count:     int
    status:         DQStatus
    alert_sent:     bool
    detail:         str = ""


@dataclass
class FieldLineageEntry:
    lineage_id:     str
    target_entity:  str
    target_field:   str
    source_entity:  str
    source_fields:  list
    transform_logic:str
    transform_type: str
    recorded_at:    datetime = field(default_factory=datetime.utcnow)
