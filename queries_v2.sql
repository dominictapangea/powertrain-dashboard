-- ============================================================
-- Query 1: KPI-uri pe tip de propulsie (versiune de bază, ca în v1)
-- ============================================================
SELECT
    powertrain_type,
    COUNT(*) AS total_vehicles,
    ROUND(AVG(co2_emissions_g_km), 2) AS avg_co2_emissions_g_km,
    ROUND(AVG(combined_consumption_le_100km), 2) AS avg_combined_consumption,
    ROUND(AVG(eco_score), 1) AS avg_eco_score
FROM
    `your_project.your_dataset.analytics`
GROUP BY
    powertrain_type
ORDER BY
    avg_co2_emissions_g_km ASC;


-- ============================================================
-- Query 2: Ranking producători -- top 5 cei mai curați, cu min. 5 modele
-- (window function RANK() in loc de simplu ORDER BY + LIMIT)
-- ============================================================
WITH manufacturer_stats AS (
    SELECT
        manufacturer,
        COUNT(*) AS total_models,
        ROUND(AVG(co2_emissions_g_km), 2) AS avg_fleet_co2,
        RANK() OVER (ORDER BY AVG(co2_emissions_g_km) ASC) AS cleanliness_rank
    FROM
        `your_project.your_dataset.analytics`
    GROUP BY
        manufacturer
    HAVING
        COUNT(*) >= 5
)
SELECT *
FROM manufacturer_stats
WHERE cleanliness_rank <= 5
ORDER BY cleanliness_rank;


-- ============================================================
-- Query 3: Mix de electrificare pe clasă de vehicul
-- (ce % din fiecare clasă e deja BEV/PHEV vs ICE -- insight de business)
-- ============================================================
SELECT
    vehicle_class,
    COUNTIF(powertrain_type = 'Battery Electric (BEV)') AS bev_count,
    COUNTIF(powertrain_type = 'Plug-in Hybrid (PHEV)') AS phev_count,
    COUNTIF(powertrain_type LIKE '%ICE%' OR powertrain_type LIKE 'Flex-Fuel%') AS ice_count,
    ROUND(
        100 * COUNTIF(powertrain_type IN ('Battery Electric (BEV)', 'Plug-in Hybrid (PHEV)'))
        / COUNT(*), 1
    ) AS pct_electrified
FROM
    `your_project.your_dataset.analytics`
GROUP BY
    vehicle_class
ORDER BY
    pct_electrified DESC;
