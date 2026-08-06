CREATE OR REPLACE VIEW validated_terminal_calls AS

WITH ordered_calls AS (
    SELECT
        pc.*,

        LAG(pc.departure_time) OVER (
            PARTITION BY pc.terminal_id, pc.mmsi
            ORDER BY pc.arrival_time
        ) AS previous_departure_time

    FROM probable_terminal_calls pc
),

marked_calls AS (
    SELECT
        oc.*,

        CASE
            WHEN previous_departure_time IS NULL THEN 1

            WHEN EXISTS (
                SELECT 1
                FROM ais_data_outages outage
                WHERE
                    previous_departure_time
                        >= outage.outage_start - INTERVAL '5 minutes'

                    AND arrival_time
                        <= outage.outage_end + INTERVAL '5 minutes'

                    AND tstzrange(
                        previous_departure_time,
                        arrival_time,
                        '[]'
                    ) && tstzrange(
                        outage.outage_start,
                        outage.outage_end,
                        '[]'
                    )
            )
            THEN 0

            ELSE 1
        END AS starts_new_validated_call

    FROM ordered_calls oc
),

grouped_calls AS (
    SELECT
        mc.*,

        SUM(starts_new_validated_call) OVER (
            PARTITION BY terminal_id, mmsi
            ORDER BY arrival_time
            ROWS BETWEEN UNBOUNDED PRECEDING
                AND CURRENT ROW
        ) AS validated_call_group

    FROM marked_calls mc
),

merged_calls AS (
    SELECT
        terminal_id,
        mmsi,
        validated_call_group,

        MIN(arrival_time) AS arrival_time,
        MAX(departure_time) AS departure_time,

        EXTRACT(
            EPOCH FROM (
                MAX(departure_time) - MIN(arrival_time)
            )
        ) / 60.0 AS duration_minutes,

        SUM(position_count) AS position_count,
        MIN(closest_distance_metres)
            AS closest_distance_metres,

        SUM(
            average_speed_knots * position_count
        ) / NULLIF(
            SUM(position_count) FILTER (
                WHERE average_speed_knots IS NOT NULL
            ),
            0
        ) AS average_speed_knots,

        MAX(maximum_speed_knots)
            AS maximum_speed_knots,

        BOOL_OR(starts_at_dataset_boundary)
            AS starts_at_dataset_boundary,

        BOOL_OR(ends_at_dataset_boundary)
            AS ends_at_dataset_boundary,

        COUNT(*) AS merged_segment_count,

        ARRAY_AGG(
            port_call_id
            ORDER BY arrival_time
        ) AS source_port_call_ids

    FROM grouped_calls

    GROUP BY
        terminal_id,
        mmsi,
        validated_call_group
)

SELECT
    ROW_NUMBER() OVER (
        ORDER BY mc.arrival_time
    ) AS validated_call_id,

    mc.terminal_id,
    t.terminal_name,

    mc.mmsi,
    v.imo,
    v.vessel_name,
    v.vessel_type,
    v.length_metres,
    v.width_metres,

    mc.arrival_time,
    mc.departure_time,
    mc.duration_minutes,
    mc.position_count,

    mc.closest_distance_metres,
    mc.average_speed_knots,
    mc.maximum_speed_knots,

    mc.starts_at_dataset_boundary,
    mc.ends_at_dataset_boundary,

    mc.merged_segment_count,
    mc.source_port_call_ids,

    CASE
        WHEN mc.merged_segment_count > 1
            THEN 'merged_across_source_outage'
        ELSE 'original_probable_call'
    END AS validation_method

FROM merged_calls mc

JOIN terminals t
    ON t.terminal_id = mc.terminal_id

JOIN vessels v
    ON v.mmsi = mc.mmsi;
