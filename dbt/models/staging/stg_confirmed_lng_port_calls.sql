{{ config(materialized='view') }}

select
    validated_call_id,
    mmsi,
    imo,
    vessel_name,
    arrival_time,
    departure_time

from {{ source('cargopulse_raw', 'confirmed_lng_port_calls') }}
