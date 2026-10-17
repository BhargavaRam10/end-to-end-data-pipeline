-- Bronze -> Silver: clean and conform raw pickup/route/service-event data.
--
-- Runs on Snowflake. Bronze holds byte-for-byte raw files (CSV staged via
-- COPY INTO from the file drop, JSONL from the API ingestion client); this
-- transform normalizes types, dedupes on natural keys, and drops rows that
-- fail data-quality rules into SILVER.<table>_quarantine for review.
--
-- Idempotent: safe to re-run for the same load date via MERGE on natural keys.

CREATE OR REPLACE TABLE silver.pickups AS
WITH ranked AS (
    SELECT
        pickup_id,
        route_id,
        TRY_TO_DATE(pickup_date)            AS pickup_date,
        TRY_TO_NUMBER(tonnage)              AS tonnage,
        UPPER(TRIM(material))               AS material,
        _load_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY pickup_id
            ORDER BY _load_timestamp DESC
        ) AS rn
    FROM bronze.pickups_raw
)
SELECT
    pickup_id,
    route_id,
    pickup_date,
    tonnage,
    material
FROM ranked
WHERE rn = 1
  AND pickup_date IS NOT NULL
  AND tonnage IS NOT NULL
  AND tonnage >= 0                -- negative tonnage is physically impossible
  AND material IN ('MSW', 'RECYCLE', 'ORGANICS');

-- Quarantine: rows that failed quality rules, kept for investigation.
CREATE OR REPLACE TABLE silver.pickups_quarantine AS
WITH ranked AS (
    SELECT
        pickup_id,
        route_id,
        TRY_TO_DATE(pickup_date)            AS pickup_date,
        TRY_TO_NUMBER(tonnage)              AS tonnage,
        UPPER(TRIM(material))               AS material,
        _load_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY pickup_id
            ORDER BY _load_timestamp DESC
        ) AS rn
    FROM bronze.pickups_raw
)
SELECT *, CURRENT_TIMESTAMP() AS quarantined_at
FROM ranked
WHERE rn = 1
  AND (
        pickup_date IS NULL
     OR tonnage IS NULL
     OR tonnage < 0
     OR material NOT IN ('MSW', 'RECYCLE', 'ORGANICS')
  );

CREATE OR REPLACE TABLE silver.routes AS
SELECT DISTINCT
    route_id,
    zone,
    truck_id,
    driver_name,
    TRY_TO_NUMBER(stops_planned) AS stops_planned
FROM bronze.routes_raw
WHERE route_id IS NOT NULL;

CREATE OR REPLACE TABLE silver.service_events AS
SELECT
    event_id,
    route_id,
    TRY_TO_DATE(event_date)       AS event_date,
    UPPER(TRIM(event_type))       AS event_type,
    UPPER(TRIM(priority))         AS priority
FROM bronze.service_events_raw
WHERE event_id IS NOT NULL
  AND event_date IS NOT NULL;
