-- Silver -> Gold: Power BI-ready reporting tables for operations.
--
-- Gold tables are the only layer BI connects to. They are wide, denormalized,
-- and grain-documented, so every DAX measure traces back to a tested model.
-- Intended consumers:
--   gold.daily_route_summary   — one row per route per day
--   gold.zone_kpis             — one row per zone per day

CREATE OR REPLACE TABLE gold.daily_route_summary AS
SELECT
    p.pickup_date                                   AS report_date,
    r.route_id,
    r.zone,
    r.truck_id,
    r.driver_name,
    COUNT(DISTINCT p.pickup_id)                     AS pickup_count,
    SUM(p.tonnage)                                  AS total_tonnage,
    SUM(CASE WHEN p.material = 'MSW' THEN p.tonnage ELSE 0 END)      AS msw_tonnage,
    SUM(CASE WHEN p.material = 'RECYCLE' THEN p.tonnage ELSE 0 END)  AS recycle_tonnage,
    SUM(CASE WHEN p.material = 'ORGANICS' THEN p.tonnage ELSE 0 END) AS organics_tonnage,
    COUNT(DISTINCT CASE WHEN e.event_type = 'MISSED_PICKUP'
                        THEN e.event_id END)        AS missed_pickups,
    COUNT(DISTINCT e.event_id)                      AS total_service_events,
    r.stops_planned
FROM silver.pickups p
LEFT JOIN silver.routes r
    ON p.route_id = r.route_id
LEFT JOIN silver.service_events e
    ON p.route_id = e.route_id
   AND p.pickup_date = e.event_date
GROUP BY 1, 2, 3, 4, 5, 14;

CREATE OR REPLACE TABLE gold.zone_kpis AS
SELECT
    report_date,
    zone,
    COUNT(DISTINCT route_id)                        AS active_routes,
    SUM(pickup_count)                               AS total_pickups,
    SUM(total_tonnage)                              AS total_tonnage,
    SUM(missed_pickups)                             AS missed_pickups,
    -- missed-pickup rate: the headline reliability KPI for operations
    DIV0(SUM(missed_pickups), NULLIF(SUM(pickup_count), 0)) AS missed_pickup_rate,
    AVG(total_tonnage)                              AS avg_tonnage_per_route
FROM gold.daily_route_summary
GROUP BY 1, 2;
