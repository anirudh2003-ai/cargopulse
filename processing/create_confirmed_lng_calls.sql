BEGIN;

DROP VIEW IF EXISTS public.confirmed_lng_port_calls;

CREATE VIEW public.confirmed_lng_port_calls AS
SELECT
    calls.*,

    registry.registry_vessel_name,
    registry.psix_vessel_id,

    registry.service_type,
    registry.service_sub_type,
    registry.cargo_authorization,

    registry.flag AS registry_flag,
    registry.vessel_status AS registry_status,

    registry.classification_status,
    registry.source_name AS classification_source,
    registry.source_reference,
    registry.last_checked_at AS classification_checked_at,

    CASE
        WHEN calls.vessel_name IS NULL
          OR registry.registry_vessel_name IS NULL
        THEN FALSE

        WHEN UPPER(TRIM(calls.vessel_name))
             <> UPPER(TRIM(registry.registry_vessel_name))
        THEN TRUE

        ELSE FALSE
    END AS vessel_name_changed

FROM public.validated_terminal_calls AS calls

INNER JOIN public.vessel_registry AS registry
    ON registry.imo = calls.imo

WHERE registry.classification_status = 'confirmed_lng';

COMMIT;
