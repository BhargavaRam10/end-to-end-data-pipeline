# DAX measures — gold.daily_route_summary & gold.zone_kpis

Model relationships (import model):

- `daily_route_summary[route_id]` → `dim_route[route_id]` (1:N, single direction)
- `daily_route_summary[report_date]` → `dim_date[date]` (1:N, single direction)
- `zone_kpis` is a pre-aggregated snapshot; relate `zone_kpis[zone]` → `dim_zone[zone]` (1:N)

> Screenshots to capture after building the report: model diagram view with
> these relationships, plus one screenshot per visual below.

## Measures

```dax
-- Total tonnage collected (base fact)
Total Tonnage =
SUM ( daily_route_summary[total_tonnage] )

-- Average tonnage per active route — route productivity
Avg Tonnage per Route =
AVERAGEX (
    VALUES ( daily_route_summary[route_id] ),
    CALCULATE ( SUM ( daily_route_summary[total_tonnage] ) )
)

-- Missed-pickup rate: headline reliability KPI
Missed Pickup % =
DIVIDE (
    SUM ( daily_route_summary[missed_pickups] ),
    SUM ( daily_route_summary[pickup_count] ),
    0
)

-- Diversion rate (recycle + organics share of total tonnage)
Diversion Rate % =
DIVIDE (
    SUM ( daily_route_summary[recycle_tonnage] )
        + SUM ( daily_route_summary[organics_tonnage] ),
    SUM ( daily_route_summary[total_tonnage] ),
    0
)

-- MoM tonnage change for trend analysis
Tonnage MoM % =
VAR PrevMonth =
    CALCULATE (
        [Total Tonnage],
        PREVIOUSMONTH ( dim_date[date] )
    )
RETURN
    DIVIDE ( [Total Tonnage] - PrevMonth, PrevMonth, 0 )

-- Routes under the reliability threshold this period
Routes Below Reliability Target =
COUNTROWS (
    FILTER (
        VALUES ( daily_route_summary[route_id] ),
        [Missed Pickup %] > 0.05
    )
)
```

## "So what" per visual

| Visual | Measure(s) | Why it matters |
|---|---|---|
| KPI cards | Total Tonnage, Missed Pickup %, Diversion Rate % | The three numbers operations leadership checks first |
| Line chart by date | Tonnage MoM %, Missed Pickup % | Trend and seasonality — is reliability improving? |
| Bar by zone | Avg Tonnage per Route, Missed Pickup % | Zones are comparable units; outliers get investigated |
| Table: routes below target | Routes Below Reliability Target | Actionable list — which routes need schedule changes |
