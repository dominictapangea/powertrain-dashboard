"""
What the model is told about the `analytics` table.

Column names and types are read from BigQuery at startup, so they can't drift
from the real table. The allowed values below are static; test_schema_info.py
checks them against cleaned_horse_powertrain_data_v2.csv.
"""

POWERTRAIN_TYPES = [
    "Battery Electric (BEV)",
    "Conventional ICE (Gasoline)",
    "Diesel ICE",
    "Flex-Fuel (Ethanol)",
    "Plug-in Hybrid (PHEV)",
]

EFFICIENCY_TIERS = [
    "A - Best in Class",
    "B - Above Average",
    "C - Below Average",
    "D - High Emissions",
]

FUEL_TYPE_CODES = ["B", "B/X", "B/Z", "D", "E", "X", "Z"]

MODEL_YEARS = [2023, 2024, 2025]

COLUMN_NOTES = {
    "model_year": "Model year (2023, 2024 or 2025).",
    "manufacturer": "Manufacturer, title case (e.g. 'Ford').",
    "model": "Model name.",
    "vehicle_class": "Vehicle class, e.g. 'Compact', 'Mid-size', 'Sport utility vehicle: Small'.",
    "transmission": "Transmission code (e.g. 'M6', 'AV7').",
    "engine_size_l": "Engine size in litres. NULL for battery-electric vehicles.",
    "cylinders": "Number of cylinders. NULL for battery-electric vehicles.",
    "motor_kw": "Electric motor power in kW. NULL for conventional (ICE) vehicles.",
    "fuel_type_code": "Fuel code: X regular gasoline, Z premium gasoline, D diesel, E ethanol, "
    "B electricity, B/X and B/Z electricity + gasoline (plug-in hybrids).",
    "fuel_type_label": "Human-readable fuel type.",
    "combined_consumption_le_100km": "Combined consumption in litres-equivalent per 100 km "
    "(comparable across all powertrains; plug-in hybrids include electricity).",
    "co2_emissions_g_km": "Tailpipe CO2 in g/km. 0 for battery-electric vehicles by definition.",
    "powertrain_type": "Powertrain category (see allowed values).",
    "source_dataset": "Which Natural Resources Canada dataset the row comes from.",
    "eco_score": "0-100, higher is cleaner: 100 - CO2 / max(CO2) * 100. Battery-electric vehicles score 100.",
    "efficiency_tier": "Quartile tier on CO2 (see allowed values).",
}

DATA_NOTES = """\
- The table has 872 rows, one per vehicle variant, from Natural Resources Canada.
- Conventional (ICE, diesel, flex-fuel) vehicles exist only for model_year 2024. Battery-electric
  and plug-in hybrid vehicles cover 2023-2025. Filtering on 2023 or 2025 therefore excludes ICE vehicles.
- CO2 is tailpipe only: electricity generation and battery production are not included.
- "Electrified" means powertrain_type is 'Battery Electric (BEV)' or 'Plug-in Hybrid (PHEV)'.
- Averages over powertrain_type are unweighted averages of vehicle variants, not sales-weighted.\
"""


def _quote(values) -> str:
    return ", ".join(repr(v) if isinstance(v, str) else str(v) for v in values)


def build_schema_prompt(fields) -> str:
    """Describe the table for the model. `fields` is a list of (name, type, mode) tuples."""
    lines = ["Table `analytics` (BigQuery, GoogleSQL) has these columns:"]
    for name, type_, mode in fields:
        note = COLUMN_NOTES.get(name, "")
        nullable = "" if mode == "REQUIRED" else ", nullable"
        lines.append(f"- {name} ({type_}{nullable}): {note}".rstrip(": ").rstrip())

    lines += [
        "",
        f"powertrain_type values: {_quote(POWERTRAIN_TYPES)}",
        f"efficiency_tier values: {_quote(EFFICIENCY_TIERS)}",
        f"fuel_type_code values: {_quote(FUEL_TYPE_CODES)}",
        "",
        "Notes about the data:",
        DATA_NOTES,
    ]
    return "\n".join(lines)
