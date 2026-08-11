{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2A
-- AIS position -> all intersecting terminal zones
-- ============================================================

select
    p.mmsi,
    p.recorded_at,
    z.terminal_id,
    z.zone_code,
    z.zone_type,
    z.zone_priority

from {{ ref('stg_ais_positions') }} as p

join {{ ref('stg_terminal_zones') }} as z
    on ST_Covers(
        z.geom,
        p.location::geometry
    )

where
    p.location is not null

    and (
        z.valid_from is null
        or p.recorded_at >= z.valid_from
    )

    and (
        z.valid_to is null
        or p.recorded_at < z.valid_to
    )
