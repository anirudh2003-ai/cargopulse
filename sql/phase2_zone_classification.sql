-- ============================================================
-- CargoPulse Phase 2A
-- AIS position → terminal geofence classification
-- ============================================================


-- ------------------------------------------------------------
-- 1. ALL ZONE HITS
--
-- One AIS position can legitimately intersect multiple zones.
-- Example:
--
--   SPL_MANOEUVRE
--   SPL_CHANNEL
--   SPL_APPROACH
--
-- We preserve all of those hits here.
-- ------------------------------------------------------------

DROP MATERIALIZED VIEW IF EXISTS
    public.ais_position_primary_zone;

DROP MATERIALIZED VIEW IF EXISTS
    public.ais_position_zone_hits;


CREATE MATERIALIZED VIEW
public.ais_position_zone_hits
AS
SELECT
    p.mmsi,
    p.recorded_at,

    z.terminal_id,
    z.zone_code,
    z.zone_type,
    z.zone_priority

FROM public.ais_positions AS p

JOIN public.terminal_zones AS z
    ON ST_Covers(
        z.geom,
        p.location::geometry
    )

WHERE
    p.location IS NOT NULL

    AND (
        z.valid_from IS NULL
        OR p.recorded_at >= z.valid_from
    )

    AND (
        z.valid_to IS NULL
        OR p.recorded_at < z.valid_to
    );


-- Fast lookup by AIS observation.
CREATE INDEX
idx_zone_hits_position
ON public.ais_position_zone_hits (
    mmsi,
    recorded_at
);


-- Fast lookup by terminal zone.
CREATE INDEX
idx_zone_hits_zone
ON public.ais_position_zone_hits (
    zone_code,
    recorded_at
);


-- ------------------------------------------------------------
-- 2. PRIMARY ZONE
--
-- If an AIS point hits several overlapping zones,
-- select the zone with the LOWEST zone_priority.
--
-- Example:
--
-- berth       10
-- manoeuvre   30
-- channel     40
-- approach    50
--
-- So berth beats everything else.
-- ------------------------------------------------------------

CREATE MATERIALIZED VIEW
public.ais_position_primary_zone
AS
SELECT
    mmsi,
    recorded_at,
    terminal_id,
    zone_code,
    zone_type,
    zone_priority

FROM (
    SELECT
        hits.*,

        ROW_NUMBER() OVER (
            PARTITION BY
                mmsi,
                recorded_at

            ORDER BY
                zone_priority ASC,
                zone_code ASC
        ) AS zone_rank

    FROM public.ais_position_zone_hits AS hits

) ranked

WHERE zone_rank = 1;


CREATE UNIQUE INDEX
idx_primary_zone_position
ON public.ais_position_primary_zone (
    mmsi,
    recorded_at
);


CREATE INDEX
idx_primary_zone_code
ON public.ais_position_primary_zone (
    zone_code,
    recorded_at
);


ANALYZE public.ais_position_zone_hits;
ANALYZE public.ais_position_primary_zone;
