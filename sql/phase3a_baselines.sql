-- ============================================================
-- CargoPulse Phase 3A
-- Empirical berth-duration baselines
-- ============================================================


DROP MATERIALIZED VIEW IF EXISTS
    public.lng_berth_duration_baseline;

DROP MATERIALIZED VIEW IF EXISTS
    public.lng_terminal_duration_baseline;


-- ============================================================
-- BERTH-SPECIFIC BASELINE
-- ============================================================

CREATE MATERIALIZED VIEW
public.lng_berth_duration_baseline
AS

SELECT

    berth_zone_code,

    COUNT(*) AS baseline_calls,

    ROUND(
        AVG(berth_duration_minutes)::numeric,
        2
    ) AS mean_minutes,

    percentile_cont(0.25)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p25_minutes,

    percentile_cont(0.50)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS median_minutes,

    percentile_cont(0.75)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p75_minutes,

    percentile_cont(0.90)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p90_minutes,

    percentile_cont(0.95)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p95_minutes,

    percentile_cont(0.75)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    )
    -
    percentile_cont(0.25)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS iqr_minutes

FROM public.lng_call_operations

WHERE
    movement_coverage = 'full'

    AND berth_detection_confidence = 'high'

    AND berth_continuity <> 'review'

GROUP BY berth_zone_code;


CREATE UNIQUE INDEX
idx_lng_berth_duration_baseline

ON public.lng_berth_duration_baseline (
    berth_zone_code
);


-- ============================================================
-- TERMINAL-WIDE FALLBACK BASELINE
--
-- Used if a berth has too few observations.
-- ============================================================

CREATE MATERIALIZED VIEW
public.lng_terminal_duration_baseline
AS

SELECT

    COUNT(*) AS baseline_calls,

    ROUND(
        AVG(berth_duration_minutes)::numeric,
        2
    ) AS mean_minutes,

    percentile_cont(0.25)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p25_minutes,

    percentile_cont(0.50)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS median_minutes,

    percentile_cont(0.75)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p75_minutes,

    percentile_cont(0.90)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p90_minutes,

    percentile_cont(0.95)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS p95_minutes,

    percentile_cont(0.75)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    )
    -
    percentile_cont(0.25)
    WITHIN GROUP (
        ORDER BY berth_duration_minutes
    ) AS iqr_minutes

FROM public.lng_call_operations

WHERE
    movement_coverage = 'full'

    AND berth_detection_confidence = 'high'

    AND berth_continuity <> 'review';


ANALYZE public.lng_berth_duration_baseline;
ANALYZE public.lng_terminal_duration_baseline;
