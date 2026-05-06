# Global Banking Revenue Intelligence Pipeline

End-to-end ETL pipeline sourcing quarterly financial data for **11 banks** across
two geographies — modeled in **FINOS Legend/Pure** with field-level data lineage.

## Banks covered

| Bank | Region | Index | Sector |
|---|---|---|---|
| Goldman Sachs (GS) | US | S&P 500 | Investment Banking |
| JPMorgan Chase (JPM) | US | S&P 500 | Universal Banking |
| Bank of America (BAC) | US | S&P 500 | Universal Banking |
| Wells Fargo (WFC) | US | S&P 500 | Universal Banking |
| Morgan Stanley (MS) | US | S&P 500 | Investment Banking |
| Citigroup (C) | US | S&P 500 | Universal Banking |
| HDFC Bank | India | NIFTY 50 | Private Sector Bank |
| State Bank of India (SBI) | India | NIFTY 50 | Public Sector Bank |
| ICICI Bank | India | NIFTY 50 | Private Sector Bank |
| Axis Bank | India | NIFTY 50 | Private Sector Bank |
| Kotak Mahindra Bank | India | NIFTY 50 | Private Sector Bank |

## Architecture

```
Bloomberg (US)  /  BSE-NSE Filings (India)
           │
           ▼  FX normalisation: INR → USD @ 83.5
    ┌──────────────┐
    │   Staging    │  DQ: null-key, duplicate (bank,period), range, integrity
    └──────┬───────┘
           ▼  star schema
    ┌──────────────┐
    │  GlobalBank  │  CDW Fact: net_margin%, YoY/QoQ LAG, revenue_rank
    │     Fact     │
    └──────┬───────┘
           ▼  pre-aggregated
    ┌──────────────┐
    │  PeerComp    │  Mart: cross-bank rank, vs_gs_revenue_pct anchor
    │    Mart      │
    └──────────────┘
```

## Key derived metrics

- `net_margin_pct` — net_income / net_revenue × 100
- `yoy_revenue_pct` — LAG(4) year-over-year growth per bank
- `revenue_rank` — RANK() across all 11 banks per quarter
- `vs_gs_revenue_pct` — each bank's revenue vs GS as anchor (%)
- `region_rank` — rank within US or India per quarter

## Data sources

- **US banks**: SEC Form 8-K filings, Bloomberg Terminal (Q1 2024 – Q2 2025)
- **Indian banks**: BSE/NSE quarterly filings, RBI data (INR → USD @ 83.5)

## Quickstart

```bash
python pipeline.py
```

## Legend/Pure

Classes follow `model::global::banking::<layer>::<Entity>` package convention.
See `legend/global_bank_pipeline.pure` for full class definitions and Mapping block.
