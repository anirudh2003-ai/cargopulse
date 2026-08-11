select
    metric_date,
    berth_zone_code

from {{ ref('lng_historical_duration_baseline_daily') }}

group by
    metric_date,
    berth_zone_code

having count(*) > 1
