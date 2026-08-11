select
    'berth' as baseline_type,
    berth_zone_code as baseline_key

from {{ ref('lng_berth_duration_baseline') }}

where
    baseline_calls <= 0
    or p25_minutes > median_minutes
    or median_minutes > p75_minutes
    or p75_minutes > p90_minutes
    or p90_minutes > p95_minutes
    or iqr_minutes < 0

union all

select
    'terminal' as baseline_type,
    'terminal' as baseline_key

from {{ ref('lng_terminal_duration_baseline') }}

where
    baseline_calls <= 0
    or p25_minutes > median_minutes
    or median_minutes > p75_minutes
    or p75_minutes > p90_minutes
    or p90_minutes > p95_minutes
    or iqr_minutes < 0
