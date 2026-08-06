CREATE TABLE IF NOT EXISTS ais_data_outages (
    outage_id BIGSERIAL PRIMARY KEY,
    outage_start TIMESTAMPTZ NOT NULL,
    outage_end TIMESTAMPTZ NOT NULL,
    source_name TEXT NOT NULL,
    reason TEXT,
    UNIQUE (outage_start, outage_end, source_name)
);

INSERT INTO ais_data_outages (
    outage_start,
    outage_end,
    source_name,
    reason
)
VALUES
(
    '2023-01-05 07:20:00+00',
    '2023-01-05 12:30:00+00',
    'NOAA AIS',
    'Dataset-wide absence of AIS position records'
),
(
    '2023-01-28 10:55:00+00',
    '2023-01-28 20:05:00+00',
    'NOAA AIS',
    'Dataset-wide absence of AIS position records'
)
ON CONFLICT (
    outage_start,
    outage_end,
    source_name
)
DO NOTHING;
