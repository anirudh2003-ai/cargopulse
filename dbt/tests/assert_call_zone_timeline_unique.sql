select
    validated_call_id,
    episode_number,
    count(*) as row_count

from {{ ref('int_lng_call_zone_timeline') }}

group by
    validated_call_id,
    episode_number

having count(*) > 1
