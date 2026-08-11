{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3A
-- Empirical berth-specific duration baselines
-- ============================================================

select

    berth_zone_code,

    count(*) as baseline_calls,

    round(
        avg(berth_duration_minutes)::numeric,
        2
    ) as mean_minutes,

    percentile_cont(0.25)
    within group (
        order by berth_duration_minutes
    ) as p25_minutes,

    percentile_cont(0.50)
    within group (
        order by berth_duration_minutes
    ) as median_minutes,

    percentile_cont(0.75)
    within group (
        order by berth_duration_minutes
    ) as p75_minutes,

    percentile_cont(0.90)
    within group (
        order by berth_duration_minutes
    ) as p90_minutes,

    percentile_cont(0.95)
    within group (
        order by berth_duration_minutes
    ) as p95_minutes,

    percentile_cont(0.75)
    within group (
        order by berth_duration_minutes
    )
    -
    percentile_cont(0.25)
    within group (
        order by berth_duration_minutes
    ) as iqr_minutes

from {{ ref('int_lng_call_operations') }}

where
    movement_coverage = 'full'

    and berth_detection_confidence = 'high'

    and berth_continuity <> 'review'

group by berth_zone_code
