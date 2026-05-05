-- sql/transforms/fact_transforms.sql
-- Promote staged records to CDW fact + compute derived metrics

INSERT INTO global_bank_fact (
    fact_id, bank_id, period,
    net_revenue_usd, net_income_usd, total_assets_usd,
    nim_pct, roe_pct, tier1_ratio, stage_id, loaded_at
)
SELECT
    gen_random_uuid()::text,
    s.bank_id, s.period,
    s.net_revenue_usd, s.net_income_usd, s.total_assets_usd,
    s.nim_pct, s.roe_pct, s.tier1_ratio,
    s.stage_id, NOW()
FROM stg_bank_records s
WHERE s.dq_status = 'PASS'
ON CONFLICT (bank_id, period) DO UPDATE SET
    net_revenue_usd = EXCLUDED.net_revenue_usd,
    net_income_usd  = EXCLUDED.net_income_usd,
    loaded_at       = NOW();


-- Derived metrics
UPDATE global_bank_fact f SET
    net_margin_pct  = ROUND(f.net_income_usd  / NULLIF(f.net_revenue_usd, 0) * 100, 2),

    yoy_revenue_pct = ROUND(
        (f.net_revenue_usd
         - LAG(f.net_revenue_usd, 4) OVER (PARTITION BY f.bank_id ORDER BY f.period))
        / NULLIF(LAG(f.net_revenue_usd, 4) OVER (PARTITION BY f.bank_id ORDER BY f.period), 0) * 100,
        2),

    qoq_revenue_pct = ROUND(
        (f.net_revenue_usd
         - LAG(f.net_revenue_usd, 1) OVER (PARTITION BY f.bank_id ORDER BY f.period))
        / NULLIF(LAG(f.net_revenue_usd, 1) OVER (PARTITION BY f.bank_id ORDER BY f.period), 0) * 100,
        2),

    revenue_rank = RANK() OVER (PARTITION BY f.period ORDER BY f.net_revenue_usd DESC)
FROM global_bank_fact f2 WHERE f.fact_id = f2.fact_id;


-- Refresh peer comparison mart
INSERT INTO peer_comparison_mart (
    mart_id, period, bank_id,
    net_revenue_usd, net_margin_pct, roe_pct, tier1_ratio,
    revenue_rank_global,
    vs_gs_revenue_pct, refreshed_at
)
SELECT
    gen_random_uuid()::text,
    f.period, f.bank_id,
    f.net_revenue_usd, f.net_margin_pct, f.roe_pct, f.tier1_ratio,
    RANK() OVER (PARTITION BY f.period ORDER BY f.net_revenue_usd DESC),
    ROUND(
      (f.net_revenue_usd - gs.net_revenue_usd)
      / NULLIF(gs.net_revenue_usd, 0) * 100, 2
    ) AS vs_gs_revenue_pct,
    NOW()
FROM global_bank_fact f
LEFT JOIN global_bank_fact gs
    ON gs.period = f.period AND gs.bank_id = 'GS'
ON CONFLICT (period, bank_id) DO UPDATE SET
    net_revenue_usd    = EXCLUDED.net_revenue_usd,
    net_margin_pct     = EXCLUDED.net_margin_pct,
    revenue_rank_global= EXCLUDED.revenue_rank_global,
    vs_gs_revenue_pct  = EXCLUDED.vs_gs_revenue_pct,
    refreshed_at       = NOW();
