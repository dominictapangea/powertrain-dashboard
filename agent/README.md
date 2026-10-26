# Analytics agent

A small terminal script that answers plain-language questions about the BigQuery `analytics` table (the cleaned vehicle data, 872 rows). Gemini gets one tool, `run_sql`, writes the SQL it needs, and explains the result. You can see every query it runs.

## Setup

From the project root, with the venv active:

```powershell
pip install -r requirements-agent.txt
copy .env.example .env
gcloud auth application-default login
```

Then fill in `.env`: your Gemini API key (from Google AI Studio), plus `BQ_PROJECT` and `BQ_DATASET` for the table. BigQuery access goes through your own `gcloud` login, so there is no key file in the repo, and `.env` is git-ignored.

## Run

```powershell
python agent\agent.py                          # interactive, follow-up questions work
python agent\agent.py "which powertrain has the lowest CO2?"
```

## Examples

**Which powertrain type has the lowest average CO2?**

```sql
SELECT powertrain_type, AVG(co2_emissions_g_km) AS avg_co2, COUNT(*) AS count FROM analytics GROUP BY powertrain_type ORDER BY avg_co2 ASC LIMIT 100
```

> **Battery Electric (BEV)** has the lowest average CO2 emissions at **0 g/km** (by definition, as CO2 measures tailpipe emissions only).
>
> Among combustion-based powertrains, **Plug-in Hybrids (PHEV)** have the lowest average tailpipe emissions at **91 g/km**

**What share of each vehicle class is electrified?**

```sql
SELECT vehicle_class, COUNT(*) AS total, SUM(CASE WHEN powertrain_type IN ('Battery Electric (BEV)', 'Plug-in Hybrid (PHEV)') THEN 1 ELSE 0 END) AS electrified_count, SAFE_DIVIDE(SUM(CASE WHEN powertrain_type IN ('Battery Electric (BEV)', 'Plug-in Hybrid (PHEV)') THEN 1 ELSE 0 END), COUNT(*)) * 100 AS electrified_share_pct FROM analytics GROUP BY vehicle_class ORDER BY electrified_share_pct DESC, total DESC LIMIT 100
```

> Here is the share of electrified vehicles (Battery Electric and Plug-in Hybrid) by vehicle class, ordered from highest to lowest share:
>
> 1. **Station wagon: Small**: 38.9% (7 of 18)
> 2. **Minivan**: 30.0% (3 of 10)
> 3. **Sport utility vehicle: Small**: 22.9% (53 of 231)
> 4. **Full-size**: 22.7% (10 of 44)
> 5. **Sport utility vehicle: Standard**: 17.4% (27 of 155)
> 6. **Compact**: 14.5% (8 of 55)
> 7. **Station wagon: Mid-size**: 14.3% (1 of 7)
> 8. **Mid-size**: 11.8% (11 of 93)
> 9. **Pickup truck: Standard**: 9.9% (8 of 81)
> 10. **Minicompact**: 4.1% (2 of 49)
> 11. **Two-seater**: 3.9% (2 of 51)
> 12. **Subcompact**: 1.7% (1 of 59)
> 13. **Pickup truck: Small**: 0.0% (0 of 19)
>
> *(Note: Conventional ICE vehicles in the dataset only cover model year 2024, which affects the relative proportions across classes.)*

**Who are the top 5 manufacturers by average CO2, with at least 5 models?**

```sql
SELECT manufacturer, AVG(co2_emissions_g_km) AS avg_co2, COUNT(*) AS vehicle_count FROM analytics GROUP BY manufacturer HAVING COUNT(*) >= 5 ORDER BY avg_co2 DESC LIMIT 5
```

> Top 5 manufacturers with the highest average tailpipe CO2 emissions (among those with at least 5 variants in the dataset):
>
> 1. **Lamborghini**: 379 g/km (7 variants)
> 2. **Ferrari**: 356 g/km (7 variants)
> 3. **Rolls-Royce**: 342 g/km (8 variants)
> 4. **Aston Martin**: 339 g/km (5 variants)
> 5. **Bentley**: 308 g/km (10 variants)
>
> *Note: CO2 figures reflect tailpipe emissions only.*

## What keeps it safe

The model's SQL goes through a validator (`sql_guard.py`) before BigQuery sees it:

- exactly one statement, and it has to be a `SELECT` (CTEs and `UNION` are fine); `DROP`, `DELETE`, `INSERT`, `UPDATE`, `CREATE` and stacked statements are rejected
- it can only read the `analytics` table
- `LIMIT 100` is added, or a bigger limit is cut down to 100
- queries run with a 100 MB cap on bytes billed, after a dry run

If a query is rejected or fails, the error goes back to the model so it can fix the SQL (up to 5 queries per question). API or login problems print a short message instead of a traceback.

Gemini receives your question, the column names and allowed values, and the query results. It does not receive the project or dataset name.

## Tests

```powershell
python -m pytest agent
```

These run offline: the SQL validator (valid queries pass; `DROP`, `DELETE` and multiple statements are rejected), the table description against the CSV, and the agent loop with fake clients.
