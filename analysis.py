"""
NYC TLC Taxi — Demand & Operations Analysis
===========================================
Computes every figure that appears in the report. Reads the raw TLC parquet
files, applies a documented validation waterfall, then runs the analysis
queries. All output lands in results.json so the report generator never
invents a number.

Run:  .venv/bin/python analysis.py
"""

import json
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "results.json"

YELLOW_2024 = str(DATA / "yellow_tripdata_2024-*.parquet")
GREEN_2024 = str(DATA / "green_tripdata_2024-*.parquet")
YELLOW_2025_01 = str(DATA / "yellow_tripdata_2025-01.parquet")
ZONES = str(DATA / "taxi_zone_lookup.csv")

con = duckdb.connect()
con.execute("SET memory_limit='4GB'")
con.execute("SET preserve_insertion_order=false")

R = {}  # results


def q1(sql):
    """Scalar query."""
    return con.execute(sql).fetchone()[0]


def qall(sql):
    """List-of-dicts query."""
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Zone reference
# ---------------------------------------------------------------------------
con.execute(f"""
CREATE OR REPLACE TABLE zones AS
SELECT LocationID::INT AS location_id, Borough AS borough, Zone AS zone,
       service_zone
FROM read_csv_auto('{ZONES}')
""")

# ---------------------------------------------------------------------------
# Raw union: yellow + green share the fields we care about
# ---------------------------------------------------------------------------
con.execute(f"""
CREATE OR REPLACE VIEW raw_trips AS
SELECT 'yellow' AS service,
       tpep_pickup_datetime  AS pickup_ts,
       tpep_dropoff_datetime AS dropoff_ts,
       PULocationID AS pu_id, DOLocationID AS do_id,
       passenger_count, trip_distance, RatecodeID AS ratecode,
       payment_type, fare_amount, tip_amount, tolls_amount,
       congestion_surcharge, total_amount
FROM read_parquet('{YELLOW_2024}')
UNION ALL
SELECT 'green' AS service,
       lpep_pickup_datetime  AS pickup_ts,
       lpep_dropoff_datetime AS dropoff_ts,
       PULocationID, DOLocationID,
       passenger_count, trip_distance, RatecodeID,
       payment_type, fare_amount, tip_amount, tolls_amount,
       congestion_surcharge, total_amount
FROM read_parquet('{GREEN_2024}')
""")

# ---------------------------------------------------------------------------
# Validation waterfall — each rule applied in sequence, losses attributed
# ---------------------------------------------------------------------------
RULES = [
    ("Raw records loaded (yellow + green, 2024 files)", "TRUE"),
    ("Pickup timestamp falls inside calendar 2024",
     "pickup_ts >= '2024-01-01' AND pickup_ts < '2025-01-01'"),
    ("Dropoff strictly after pickup",
     "dropoff_ts > pickup_ts"),
    ("Trip duration between 1 minute and 3 hours",
     "date_diff('second', pickup_ts, dropoff_ts) BETWEEN 60 AND 10800"),
    ("Trip distance greater than 0 and under 100 miles",
     "trip_distance > 0 AND trip_distance < 100"),
    ("Fare and total non-negative, total greater than 0",
     "fare_amount >= 0 AND total_amount > 0"),
    ("Total fare under $1,000 (caps data-entry outliers)",
     "total_amount < 1000"),
    ("Pickup and dropoff zones are known (excludes 264/265)",
     "pu_id NOT IN (264,265) AND do_id NOT IN (264,265)"),
    ("Implied average speed between 1 and 70 mph",
     "trip_distance / (date_diff('second', pickup_ts, dropoff_ts)/3600.0) "
     "BETWEEN 1 AND 70"),
]

print("Running validation waterfall...")
waterfall = []
clauses = []
prev = None
for label, cond in RULES:
    if cond != "TRUE":
        clauses.append(cond)
    where = " AND ".join(clauses) if clauses else "TRUE"
    n = q1(f"SELECT count(*) FROM raw_trips WHERE {where}")
    removed = 0 if prev is None else prev - n
    waterfall.append({
        "rule": label,
        "rows_remaining": n,
        "rows_removed": removed,
        "pct_removed": round(removed / prev * 100, 3) if prev else 0.0,
    })
    print(f"  {n:>12,}  (-{removed:,})  {label}")
    prev = n

R["validation"] = waterfall
R["rows_raw"] = waterfall[0]["rows_remaining"]
R["rows_clean"] = waterfall[-1]["rows_remaining"]
R["pct_retained"] = round(R["rows_clean"] / R["rows_raw"] * 100, 2)

CLEAN_WHERE = " AND ".join(clauses)

con.execute(f"""
CREATE OR REPLACE VIEW trips AS
SELECT
    service, pickup_ts, dropoff_ts, pu_id, do_id,
    passenger_count, trip_distance, ratecode, payment_type,
    fare_amount, tip_amount, tolls_amount, congestion_surcharge, total_amount,
    date_diff('second', pickup_ts, dropoff_ts)/60.0 AS duration_min,
    trip_distance / (date_diff('second', pickup_ts, dropoff_ts)/3600.0) AS mph,
    total_amount / (date_diff('second', pickup_ts, dropoff_ts)/60.0) AS rev_per_min,
    hour(pickup_ts) AS hr,
    dayofweek(pickup_ts) AS dow,
    date_trunc('month', pickup_ts) AS mth
FROM raw_trips
WHERE {CLEAN_WHERE}
""")

# ---------------------------------------------------------------------------
# Headline KPIs
# ---------------------------------------------------------------------------
print("Computing headline KPIs...")
R["kpi"] = qall("""
SELECT count(*) AS trips,
       sum(total_amount) AS revenue,
       avg(total_amount) AS avg_fare,
       avg(trip_distance) AS avg_miles,
       avg(duration_min) AS avg_duration,
       avg(mph) AS avg_mph,
       avg(rev_per_min) AS avg_rev_per_min,
       sum(total_amount)/sum(trip_distance) AS rev_per_mile
FROM trips
""")[0]

R["by_service"] = qall("""
SELECT service, count(*) AS trips, avg(total_amount) AS avg_fare,
       avg(mph) AS avg_mph
FROM trips GROUP BY service ORDER BY trips DESC
""")

# ---------------------------------------------------------------------------
# Monthly trend
# ---------------------------------------------------------------------------
print("Computing monthly trends...")
R["monthly"] = qall("""
SELECT strftime(mth, '%Y-%m') AS month,
       count(*) AS trips,
       avg(total_amount) AS avg_fare,
       avg(fare_amount/trip_distance) AS fare_per_mile,
       avg(mph) AS avg_mph,
       avg(duration_min) AS avg_duration
FROM trips
WHERE trip_distance >= 0.5
GROUP BY mth ORDER BY mth
""")

# ---------------------------------------------------------------------------
# Demand heatmap: hour x day-of-week
# ---------------------------------------------------------------------------
print("Computing demand heatmap...")
R["heatmap"] = qall("""
SELECT dow, hr, count(*) AS trips, avg(mph) AS avg_mph
FROM trips GROUP BY dow, hr ORDER BY dow, hr
""")

# ---------------------------------------------------------------------------
# Speed & yield by hour
# ---------------------------------------------------------------------------
print("Computing hourly efficiency...")
R["hourly"] = qall("""
SELECT hr, count(*) AS trips, avg(mph) AS avg_mph,
       avg(rev_per_min) AS rev_per_min, avg(total_amount) AS avg_fare,
       avg(duration_min) AS avg_duration
FROM trips GROUP BY hr ORDER BY hr
""")

# ---------------------------------------------------------------------------
# Borough performance (pickup side)
# ---------------------------------------------------------------------------
print("Computing borough performance...")
R["borough"] = qall("""
SELECT z.borough,
       count(*) AS trips,
       sum(t.total_amount) AS revenue,
       avg(t.total_amount) AS avg_fare,
       avg(t.trip_distance) AS avg_miles,
       avg(t.duration_min) AS avg_duration,
       avg(t.mph) AS avg_mph,
       avg(t.rev_per_min) AS rev_per_min
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE z.borough <> 'Unknown'
GROUP BY z.borough ORDER BY trips DESC
""")

# ---------------------------------------------------------------------------
# Zone-level efficiency — the weakest yield among high-volume zones
# ---------------------------------------------------------------------------
print("Computing zone-level efficiency...")
R["zones_worst"] = qall("""
SELECT z.zone, z.borough, count(*) AS trips,
       avg(t.mph) AS avg_mph, avg(t.rev_per_min) AS rev_per_min,
       avg(t.total_amount) AS avg_fare, avg(t.duration_min) AS avg_duration
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE z.borough <> 'Unknown'
GROUP BY z.zone, z.borough
HAVING count(*) >= 50000
ORDER BY rev_per_min ASC LIMIT 10
""")

R["zones_best"] = qall("""
SELECT z.zone, z.borough, count(*) AS trips,
       avg(t.mph) AS avg_mph, avg(t.rev_per_min) AS rev_per_min,
       avg(t.total_amount) AS avg_fare, avg(t.duration_min) AS avg_duration
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE z.borough <> 'Unknown'
GROUP BY z.zone, z.borough
HAVING count(*) >= 50000
ORDER BY rev_per_min DESC LIMIT 10
""")

R["zones_top_volume"] = qall("""
SELECT z.zone, z.borough, count(*) AS trips,
       avg(t.mph) AS avg_mph, avg(t.rev_per_min) AS rev_per_min,
       avg(t.total_amount) AS avg_fare
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE z.borough <> 'Unknown'
GROUP BY z.zone, z.borough ORDER BY trips DESC LIMIT 12
""")

# ---------------------------------------------------------------------------
# Tipping behaviour (card trips only — cash tips are not recorded)
# ---------------------------------------------------------------------------
print("Computing tipping behaviour...")
R["tip_by_payment"] = qall("""
SELECT payment_type, count(*) AS trips,
       avg(tip_amount) AS avg_tip,
       avg(CASE WHEN fare_amount > 0 THEN tip_amount/fare_amount END)*100 AS tip_pct
FROM trips GROUP BY payment_type ORDER BY trips DESC
""")

R["tip_by_hour"] = qall("""
SELECT hr, avg(tip_amount/fare_amount)*100 AS tip_pct, count(*) AS trips
FROM trips WHERE payment_type = 1 AND fare_amount > 0
GROUP BY hr ORDER BY hr
""")

R["tip_by_borough"] = qall("""
SELECT z.borough, avg(t.tip_amount/t.fare_amount)*100 AS tip_pct,
       count(*) AS trips
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE t.payment_type = 1 AND t.fare_amount > 0 AND z.borough <> 'Unknown'
GROUP BY z.borough ORDER BY tip_pct DESC
""")

# ---------------------------------------------------------------------------
# Airport trips
# ---------------------------------------------------------------------------
print("Computing airport analysis...")
R["airport"] = qall("""
SELECT z.zone, count(*) AS trips, avg(t.total_amount) AS avg_fare,
       avg(t.trip_distance) AS avg_miles, avg(t.mph) AS avg_mph,
       avg(t.duration_min) AS avg_duration
FROM trips t JOIN zones z ON t.pu_id = z.location_id
WHERE z.zone IN ('JFK Airport','LaGuardia Airport','Newark Airport')
GROUP BY z.zone ORDER BY trips DESC
""")

# ---------------------------------------------------------------------------
# Congestion pricing: Jan 2024 vs Jan 2025
# CBD trips in 2025 are identified from the data via cbd_congestion_fee.
# ---------------------------------------------------------------------------
print("Computing congestion pricing comparison...")
CBD_FILTER = f"""
    pickup_ts >= '{{start}}' AND pickup_ts < '{{end}}'
    AND dropoff_ts > pickup_ts
    AND date_diff('second', pickup_ts, dropoff_ts) BETWEEN 60 AND 10800
    AND trip_distance > 0 AND trip_distance < 100
    AND fare_amount >= 0 AND total_amount > 0 AND total_amount < 1000
    AND PULocationID NOT IN (264,265) AND DOLocationID NOT IN (264,265)
    AND trip_distance / (date_diff('second', pickup_ts, dropoff_ts)/3600.0)
        BETWEEN 1 AND 70
"""

# Identify the congestion zone from the data rather than a hardcoded list.
# The CBD fee is levied on trips *entering* the zone, so a simple
# "fee > 0" filter wrongly sweeps in pickups from all over the city.
# Instead: score each zone by the SHARE of its pickups that paid the fee.
# Zones inside the CBD cluster near 88%; zones north of 60th St sit at
# 16-30%. The gap between them is wide and unambiguous.
con.execute(f"""
CREATE OR REPLACE TABLE zone_fee_share AS
SELECT PULocationID AS location_id,
       count(*) AS trips_2025_01,
       avg(CASE WHEN cbd_congestion_fee > 0 THEN 1.0 ELSE 0 END) AS fee_share
FROM read_parquet('{YELLOW_2025_01}')
GROUP BY 1
HAVING count(*) >= 1000
""")

# Treatment = inside the tolled zone
con.execute("""
CREATE OR REPLACE TABLE cbd_zones AS
SELECT location_id FROM zone_fee_share WHERE fee_share >= 0.70
""")
# Control = Manhattan zones outside the toll (Harlem, UWS, UES, etc.)
con.execute("""
CREATE OR REPLACE TABLE control_zones AS
SELECT f.location_id FROM zone_fee_share f
JOIN zones z ON f.location_id = z.location_id
WHERE f.fee_share < 0.40 AND z.borough = 'Manhattan'
""")

R["cbd_zone_count"] = q1("SELECT count(*) FROM cbd_zones")
R["control_zone_count"] = q1("SELECT count(*) FROM control_zones")
# How many zones the naive "fee > 0" definition would have swept in. Kept
# because the report cites it when explaining why that approach fails.
R["naive_cbd_zone_count"] = q1(f"""
SELECT count(DISTINCT PULocationID) FROM read_parquet('{YELLOW_2025_01}')
WHERE cbd_congestion_fee > 0""")
R["cbd_zone_list"] = [r["zone"] for r in qall("""
    SELECT z.zone FROM cbd_zones c JOIN zones z ON c.location_id=z.location_id
    ORDER BY z.zone""")]
R["control_zone_list"] = [r["zone"] for r in qall("""
    SELECT z.zone FROM control_zones c JOIN zones z ON c.location_id=z.location_id
    ORDER BY z.zone""")]
R["zone_fee_share_sample"] = qall("""
    SELECT z.zone, f.trips_2025_01 AS trips, f.fee_share
    FROM zone_fee_share f JOIN zones z ON f.location_id=z.location_id
    WHERE f.trips_2025_01 >= 20000
    ORDER BY f.fee_share DESC""")

def cbd_stats(path, start, end):
    where = CBD_FILTER.format(start=start, end=end)
    return qall(f"""
    SELECT count(*) AS trips,
           avg(total_amount) AS avg_fare,
           avg(fare_amount) AS avg_base_fare,
           avg(trip_distance) AS avg_miles,
           avg(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)/60.0) AS avg_duration,
           avg(trip_distance / (date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)/3600.0)) AS avg_mph
    FROM read_parquet('{path}')
    WHERE {where.replace('pickup_ts','tpep_pickup_datetime').replace('dropoff_ts','tpep_dropoff_datetime')}
      AND PULocationID IN (SELECT location_id FROM cbd_zones)
    """)[0]

R["cbd_2024_01"] = cbd_stats(str(DATA / "yellow_tripdata_2024-01.parquet"),
                             "2024-01-01", "2024-02-01")
R["cbd_2025_01"] = cbd_stats(YELLOW_2025_01, "2025-01-01", "2025-02-01")

# Control group: Manhattan zones north of the tolled area. Same borough,
# same weather, same seasonality — but not subject to the charge.
def noncbd_stats(path, start, end):
    where = CBD_FILTER.format(start=start, end=end)
    return qall(f"""
    SELECT count(*) AS trips,
           avg(total_amount) AS avg_fare,
           avg(fare_amount) AS avg_base_fare,
           avg(trip_distance) AS avg_miles,
           avg(date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)/60.0) AS avg_duration,
           avg(trip_distance / (date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)/3600.0)) AS avg_mph
    FROM read_parquet('{path}')
    WHERE {where.replace('pickup_ts','tpep_pickup_datetime').replace('dropoff_ts','tpep_dropoff_datetime')}
      AND PULocationID IN (SELECT location_id FROM control_zones)
    """)[0]

R["noncbd_2024_01"] = noncbd_stats(str(DATA / "yellow_tripdata_2024-01.parquet"),
                                   "2024-01-01", "2024-02-01")
R["noncbd_2025_01"] = noncbd_stats(YELLOW_2025_01, "2025-01-01", "2025-02-01")

# Hourly speed profile inside the CBD, both years
def cbd_hourly(path, start, end):
    where = CBD_FILTER.format(start=start, end=end)
    return qall(f"""
    SELECT hour(tpep_pickup_datetime) AS hr,
           avg(trip_distance / (date_diff('second', tpep_pickup_datetime, tpep_dropoff_datetime)/3600.0)) AS avg_mph,
           count(*) AS trips
    FROM read_parquet('{path}')
    WHERE {where.replace('pickup_ts','tpep_pickup_datetime').replace('dropoff_ts','tpep_dropoff_datetime')}
      AND PULocationID IN (SELECT location_id FROM cbd_zones)
    GROUP BY 1 ORDER BY 1
    """)

R["cbd_hourly_2024"] = cbd_hourly(str(DATA / "yellow_tripdata_2024-01.parquet"),
                                  "2024-01-01", "2024-02-01")
R["cbd_hourly_2025"] = cbd_hourly(YELLOW_2025_01, "2025-01-01", "2025-02-01")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
def default(o):
    import datetime
    from decimal import Decimal
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(str(type(o)))


OUT.write_text(json.dumps(R, indent=2, default=default))
print(f"\nWrote {OUT}")
print(f"Raw rows:   {R['rows_raw']:,}")
print(f"Clean rows: {R['rows_clean']:,}  ({R['pct_retained']}% retained)")
