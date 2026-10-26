"""
HORSE Powertrain Portfolio Project — ETL v2
Merges three real Natural Resources Canada datasets (ICE/gasoline+diesel,
Plug-in Hybrid, Battery Electric) into one clean, analysis-ready table.

Key fix vs v1: powertrain_type now comes from the SOURCE dataset the
vehicle actually belongs to (fact, not inferred from engine size).

Changes in this revision:
- combined_consumption_le_100km is now comparable across powertrains
  (litres-equivalent per 100 km). For PHEV it is parsed from the NRCan
  "Combined Le/100 km" text instead of using the gasoline-only column.
- efficiency_tier uses fixed quartile thresholds on CO2, so equal CO2
  values always land in the same tier.
- transmission / engine_size_l / cylinders / motor_kw are kept, so
  distinct variants of one model are no longer identical rows; any
  remaining exact duplicates are dropped explicitly.
"""

import pandas as pd
import numpy as np

FUEL_LABELS = {
    "X": "Regular Gasoline",
    "Z": "Premium Gasoline",
    "D": "Diesel",
    "E": "Ethanol (E85)",
    "N": "Natural Gas",
}

TIER_LABELS = ["A - Best in Class", "B - Above Average", "C - Below Average", "D - High Emissions"]


def read_nrcan(path: str) -> pd.DataFrame:
    """Read an NRCan CSV and normalise column names to snake_case."""
    df = pd.read_csv(path, encoding="latin1")
    df.columns = (
        df.columns.str.strip().str.lower()
        .str.replace(" ", "_").str.replace("(", "", regex=False)
        .str.replace(")", "", regex=False).str.replace("/", "_", regex=False)
    )
    return df


def to_common_schema(df: pd.DataFrame, *, consumption, fuel_type_code, fuel_type_label,
                     powertrain_type, source_dataset) -> pd.DataFrame:
    """Map one source dataset onto the shared output schema."""
    def optional(col):
        return pd.to_numeric(df[col], errors="coerce") if col in df else pd.Series(np.nan, index=df.index)

    return pd.DataFrame({
        "model_year": df["model_year"],
        "manufacturer": df["make"].astype(str).str.strip().str.title(),
        "model": df["model"],
        "vehicle_class": df["vehicle_class"],
        "transmission": df["transmission"] if "transmission" in df else pd.Series(pd.NA, index=df.index),
        "engine_size_l": optional("engine_size_l"),
        "cylinders": optional("cylinders"),
        "motor_kw": optional("motor_kw"),
        "fuel_type_code": fuel_type_code,
        "fuel_type_label": fuel_type_label,
        "combined_consumption_le_100km": pd.to_numeric(consumption, errors="coerce"),
        "co2_emissions_g_km": pd.to_numeric(df["co2_emissions_g_km"], errors="coerce"),
        "powertrain_type": powertrain_type,
        "source_dataset": source_dataset,
    }, index=df.index)


def load_ice(path: str) -> pd.DataFrame:
    df = read_nrcan(path)
    code = df["fuel_type"].astype(str).str.upper()
    powertrain = np.where(
        code == "D", "Diesel ICE",
        np.where(code == "E", "Flex-Fuel (Ethanol)", "Conventional ICE (Gasoline)")
    )
    return to_common_schema(
        df,
        consumption=df["combined_l_100_km"],
        fuel_type_code=code,
        fuel_type_label=code.map(FUEL_LABELS).fillna(code),
        powertrain_type=powertrain,
        source_dataset="ICE / Conventional (2024 Fuel Consumption Ratings)",
    )


def load_phev(path: str) -> pd.DataFrame:
    df = read_nrcan(path)
    fuel2 = df["fuel_type_2"].astype(str).str.upper()
    # "3.9 ([34.8 kWh + 0.0 L]/100 km)" -> 3.9 : electricity + gasoline in Le/100 km,
    # directly comparable with the BEV (Le/100 km) and ICE (L/100 km) figures.
    le_100km = df["combined_le_100_km"].astype(str).str.extract(r"^\s*(\d+(?:\.\d+)?)")[0]
    return to_common_schema(
        df,
        consumption=le_100km,
        fuel_type_code="B/" + fuel2,
        fuel_type_label="Electricity + " + fuel2.map(FUEL_LABELS).fillna(fuel2),
        powertrain_type="Plug-in Hybrid (PHEV)",
        source_dataset="Plug-in Hybrid Electric Vehicles 2012-2025",
    )


def load_bev(path: str) -> pd.DataFrame:
    df = read_nrcan(path)
    return to_common_schema(
        df,
        consumption=df["combined_le_100_km"],
        fuel_type_code="B",
        fuel_type_label="Electricity (Battery)",
        powertrain_type="Battery Electric (BEV)",
        source_dataset="Battery-Electric Vehicles 2012-2025",
    )


def assign_efficiency_tier(co2: pd.Series) -> pd.Series:
    """Quartile thresholds on the CO2 value (not the rank): ties share a tier."""
    edges = co2.quantile([0, 0.25, 0.5, 0.75, 1.0]).to_numpy()
    return pd.cut(co2, bins=edges, labels=TIER_LABELS, include_lowest=True)


def run_etl_pipeline():
    print("[INFO] Starting ETL v2 — merging ICE + PHEV + BEV datasets...")

    ice = load_ice("real_fuel_consumption.csv")
    phev = load_phev("plugin_hybrid_vehicles.csv")
    bev = load_bev("battery_electric_vehicles.csv")

    print(f"[INFO] ICE records:  {len(ice)}")
    print(f"[INFO] PHEV records: {len(phev)}")
    print(f"[INFO] BEV records:  {len(bev)}")

    combined = pd.concat([ice, phev, bev], ignore_index=True)
    combined = combined.dropna(subset=["co2_emissions_g_km", "combined_consumption_le_100km"])

    before = len(combined)
    combined = combined.drop_duplicates().reset_index(drop=True)
    print(f"[INFO] Dropped {before - len(combined)} exact duplicate rows")

    # Eco score: 0-100, higher = cleaner. BEVs (0 g/km tailpipe) top the scale by design.
    max_co2 = combined["co2_emissions_g_km"].max()
    combined["eco_score"] = np.round(100 - (combined["co2_emissions_g_km"] / max_co2) * 100, 1)

    combined["efficiency_tier"] = assign_efficiency_tier(combined["co2_emissions_g_km"])

    combined = combined.sort_values(["model_year", "manufacturer", "model", "transmission"]).reset_index(drop=True)

    output_file = "cleaned_horse_powertrain_data_v2.csv"
    combined.to_csv(output_file, index=False)

    print(f"[SUCCESS] Wrote {len(combined)} records to '{output_file}'")
    print("\n--- Powertrain distribution ---")
    print(combined["powertrain_type"].value_counts())
    print("\n--- Preview ---")
    print(combined.head(8).to_string())


if __name__ == "__main__":
    run_etl_pipeline()
