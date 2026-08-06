INSERT INTO terminals (
    terminal_name,
    country_code,
    latitude,
    longitude,
    detection_radius_metres
)
VALUES (
    'Sabine Pass LNG',
    'US',
    29.7540967,
    -93.8740512,
    5000
)
ON CONFLICT (terminal_name)
DO UPDATE SET
    country_code = EXCLUDED.country_code,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    detection_radius_metres = EXCLUDED.detection_radius_metres;
