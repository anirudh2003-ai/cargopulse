{{ config(materialized='view') }}

select
    *
from {{ source('cargopulse_raw', 'ais_positions') }}
