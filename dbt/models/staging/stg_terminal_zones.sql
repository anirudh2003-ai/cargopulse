{{ config(materialized='view') }}

select
    terminal_id,
    zone_code,
    zone_type,
    zone_priority,
    geom,
    valid_from,
    valid_to

from {{ source('cargopulse_raw', 'terminal_zones') }}
