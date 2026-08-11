{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2A
-- Select one primary operational zone for each AIS observation.
--
-- Lower zone_priority wins.
-- zone_code ASC provides a deterministic tie-breaker.
-- ============================================================

with ranked as (

    select
        hits.*,

        row_number() over (
            partition by
                mmsi,
                recorded_at

            order by
                zone_priority asc,
                zone_code asc
        ) as zone_rank

    from {{ ref('int_ais_position_zone_hits') }} as hits
)

select
    mmsi,
    recorded_at,
    terminal_id,
    zone_code,
    zone_type,
    zone_priority

from ranked

where zone_rank = 1
