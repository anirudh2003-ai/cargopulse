select
    calls.validated_call_id

from {{ ref('int_lng_operational_calls') }} as calls

left join {{ ref('int_lng_call_operations') }} as operations
    on operations.validated_call_id
       = calls.validated_call_id

where operations.validated_call_id is null
