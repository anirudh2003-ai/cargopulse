SELECT
    mmsi,
    vessel_name,
    imo,
    COUNT(*) AS call_count
FROM probable_terminal_calls
GROUP BY
    mmsi,
    vessel_name,
    imo
HAVING COUNT(*) > 1
ORDER BY call_count DESC, vessel_name;
