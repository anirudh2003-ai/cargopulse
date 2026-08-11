{{ config(materialized='table') }}

-- ============================================================
-- CargoPulse Phase 2B
-- Full AIS position state with optional primary terminal zone.
--
-- IMPORTANT:
-- Positions outside all terminal zones are retained with
-- zone_code = NULL. These NULL states are required to detect
-- vessels leaving and later re-entering operational zones.
-- ============================================================

select
    p.mmsi,
    p.recorded_at,

    p.latitude,
    p.longitude,
    p.speed_knots,
    p.course_degrees,
    p.heading_degrees,

    z.terminal_id,
    z.zone_code,
    z.zone_type,
    z.zone_priority

from {{ ref('stg_ais_positions') }} as p

left join {{ ref('int_ais_position_primary_zone') }} as z
    on z.mmsi = p.mmsi
    and z.recorded_at = p.recorded_at
