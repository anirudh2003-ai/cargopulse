{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 3B
-- Estimated operational delay per LNG call
-- ============================================================

with dataset_bounds as (

    select
        min(recorded_at) as dataset_start,
        max(recorded_at) as dataset_end

    from {{ ref('stg_ais_positions') }}
),

baseline_input as (

    select

        calls.*,

        bounds.dataset_start,
        bounds.dataset_end,

        -- Prefer berth-specific baseline when at least
        -- five eligible historical calls are available.
        case
            when berth_base.baseline_calls >= 5
                then 'berth'
            else 'terminal'
        end as baseline_scope,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.baseline_calls
            else terminal_base.baseline_calls
        end as baseline_sample_size,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.median_minutes
            else terminal_base.median_minutes
        end as expected_duration_minutes,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.p75_minutes
            else terminal_base.p75_minutes
        end as p75_minutes,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.p90_minutes
            else terminal_base.p90_minutes
        end as p90_minutes,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.p95_minutes
            else terminal_base.p95_minutes
        end as p95_minutes,

        case
            when berth_base.baseline_calls >= 5
                then berth_base.iqr_minutes
            else terminal_base.iqr_minutes
        end as baseline_iqr_minutes

    from {{ ref('int_lng_call_operations') }} as calls

    left join {{ ref('lng_berth_duration_baseline') }} as berth_base
        on berth_base.berth_zone_code
           = calls.berth_zone_code

    cross join {{ ref('lng_terminal_duration_baseline') }} as terminal_base

    cross join dataset_bounds as bounds
),

quality as (

    select
        *,

        (
            berth_arrival_time
            <= dataset_start + interval '10 minutes'
        ) as left_censored,

        (
            berth_departure_time
            >= dataset_end - interval '10 minutes'
        ) as right_censored

    from baseline_input
),

scored as (

    select
        *,

        berth_duration_minutes
            - expected_duration_minutes
            as duration_variance_minutes,

        greatest(
            berth_duration_minutes
            - expected_duration_minutes,
            0
        ) as estimated_delay_minutes,

        case

            when left_censored
              or right_censored
                then 'censored'

            when berth_continuity = 'review'
                then 'review'

            when berth_continuity = 'moderate_gap'
                then 'usable_with_gap'

            when berth_detection_confidence <> 'high'
                then 'lower_confidence'

            else 'usable'

        end as delay_quality

    from quality
)

select
    *,

    estimated_delay_minutes / 60.0
        as estimated_delay_hours,

    case

        when delay_quality in (
            'censored',
            'review',
            'lower_confidence'
        )
            then 'unscored'

        when berth_duration_minutes <= p75_minutes
            then 'normal'

        when berth_duration_minutes <= p90_minutes
            then 'elevated'

        when berth_duration_minutes <= p95_minutes
            then 'high'

        else 'severe'

    end as delay_band

from scored
