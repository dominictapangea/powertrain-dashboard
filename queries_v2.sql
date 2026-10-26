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
    `horse-503615.horse_updated.analytics`
GROUP BY
    powertrain_type
ORDER BY
    avg_co2_emissions_g_km ASC;


-- ============================================================
-- Query 2: Evoluție an-de-an a emisiilor medii, pe tip de propulsie
-- (arată tendința de electrificare a flotei -- foarte relevant pt HORSE)
-- ============================================================
SELECT
    model_year,
    powertrain_type,
    COUNT(*) AS vehicles_that_year,
    ROUND(AVG(co2_emissions_g_km), 2) AS avg_co2_emissions_g_km,
    ROUND(
        AVG(co2_emissions_g_km) - LAG(AVG(co2_emissions_g_km)) OVER (
            PARTITION BY powertrain_type ORDER BY model_year
        ), 2
    ) AS co2_change_vs_prev_year
FROM
    `horse-503615.horse_updated.analytics`
GROUP BY
    model_year, powertrain_type
ORDER BY
    powertrain_type, model_year;


-- ============================================================
-- Query 3: Ranking producători -- top 5 cei mai curați, cu min. 5 modele
-- (window function RANK() in loc de simplu ORDER BY + LIMIT)
-- ============================================================
WITH manufacturer_stats AS (
    SELECT
        manufacturer,
        COUNT(*) AS total_models,
        ROUND(AVG(co2_emissions_g_km), 2) AS avg_fleet_co2,
        RANK() OVER (ORDER BY AVG(co2_emissions_g_km) ASC) AS cleanliness_rank
    FROM
        `horse-503615.horse_updated.analytics`
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
-- Query 4: Mix de electrificare pe clasă de vehicul
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
    `horse-503615.horse_updated.analytics`
GROUP BY
    vehicle_class
ORDER BY
    pct_electrified DESC;
