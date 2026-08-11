select
    validated_call_id,
    zone_code,
    berth_stay_number,
    count(*) as row_count

from {{ ref('int_lng_berth_stay_candidates') }}

group by
    validated_call_id,
    zone_code,
    berth_stay_number

having count(*) > 1
