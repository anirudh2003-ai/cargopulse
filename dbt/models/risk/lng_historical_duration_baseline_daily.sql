-- depends_on: {{ ref('lng_terminal_daily_metrics') }}
{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 4D
-- Leakage-safe historical duration baselines.
--
-- For each calendar day, use ONLY calls completed before
-- that day.
-- ============================================================

with days as (

    select
        metric_date

    from {{ ref('lng_terminal_daily_metrics') }}
),

eligible_completed_calls as (

    select
        validated_call_id,
        berth_zone_code,
        berth_departure_time,
        berth_duration_minutes

    from {{ ref('int_lng_call_operations') }}

    where
        berth_detection_confidence = 'high'

        and berth_continuity <> 'review'

        and movement_coverage = 'full'
),

berth_history as (

    select

        days.metric_date,

        calls.berth_zone_code,

        count(calls.validated_call_id)
            as berth_history_calls,

        percentile_cont(0.50)
        within group (
            order by calls.berth_duration_minutes
        ) as berth_median_minutes,

        percentile_cont(0.75)
        within group (
            order by calls.berth_duration_minutes
        ) as berth_p75_minutes,

        percentile_cont(0.90)
        within group (
            order by calls.berth_duration_minutes
        ) as berth_p90_minutes,

        percentile_cont(0.95)
        within group (
            order by calls.berth_duration_minutes
        ) as berth_p95_minutes

    from days

    left join eligible_completed_calls as calls
        on calls.berth_departure_time
            < days.metric_date::timestamp

    group by
        days.metric_date,
        calls.berth_zone_code
),

terminal_history as (

    select

        days.metric_date,

        count(calls.validated_call_id)
            as terminal_history_calls,

        percentile_cont(0.50)
        within group (
            order by calls.berth_duration_minutes
        ) as terminal_median_minutes,

        percentile_cont(0.75)
        within group (
            order by calls.berth_duration_minutes
        ) as terminal_p75_minutes,

        percentile_cont(0.90)
        within group (
            order by calls.berth_duration_minutes
        ) as terminal_p90_minutes,

        percentile_cont(0.95)
        within group (
            order by calls.berth_duration_minutes
        ) as terminal_p95_minutes

    from days

    left join eligible_completed_calls as calls
        on calls.berth_departure_time
            < days.metric_date::timestamp

    group by days.metric_date
),

zones as (

    select distinct
        berth_zone_code

    from {{ ref('int_lng_call_operations') }}
)

select

    days.metric_date,

    zones.berth_zone_code,

    coalesce(
        berth.berth_history_calls,
        0
    ) as berth_history_calls,

    terminal.terminal_history_calls,

    case

        when berth.berth_history_calls >= 5
            then 'historical_berth'

        when terminal.terminal_history_calls >= 5
            then 'historical_terminal'

        else 'insufficient_history'

    end as baseline_scope,

    case

        when berth.berth_history_calls >= 5
            then berth.berth_median_minutes

        when terminal.terminal_history_calls >= 5
            then terminal.terminal_median_minutes

        else null

    end as expected_minutes,

    case

        when berth.berth_history_calls >= 5
            then berth.berth_p75_minutes

        when terminal.terminal_history_calls >= 5
            then terminal.terminal_p75_minutes

        else null

    end as p75_minutes,

    case

        when berth.berth_history_calls >= 5
            then berth.berth_p90_minutes

        when terminal.terminal_history_calls >= 5
            then terminal.terminal_p90_minutes

        else null

    end as p90_minutes,

    case

        when berth.berth_history_calls >= 5
            then berth.berth_p95_minutes

        when terminal.terminal_history_calls >= 5
            then terminal.terminal_p95_minutes

        else null

    end as p95_minutes

from days

cross join zones

left join berth_history as berth
    on berth.metric_date = days.metric_date

    and berth.berth_zone_code
        = zones.berth_zone_code

join terminal_history as terminal
    on terminal.metric_date
       = days.metric_date
