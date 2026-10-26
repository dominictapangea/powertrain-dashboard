# HORSE Powertrain Dashboard — Context proiect

Proiect de portofoliu pentru aplicația de internship la HORSE Powertrain (autor: Dominic Tapangea). Scop: demonstrează un flux complet de date — **surse CSV → ETL Python → CSV curat → BigQuery (SQL) → dashboard-uri Looker Studio / Power BI** — pe tema emisiilor și consumului pe tipuri de propulsie (ICE, PHEV, BEV).

Limba de lucru cu utilizatorul: **română**. Codul, numele de coloane și comentariile din cod rămân în **engleză** (excepție: comentariile din `queries_v2.sql` sunt în română).

## Structura folderului

| Fișier | Rol |
|---|---|
| `real_fuel_consumption.csv` | Sursă ICE: 739 rânduri, 2024 Fuel Consumption Ratings (Natural Resources Canada). Coloane: `Model year, Make, Model, Vehicle class, Engine size (L), Cylinders, Transmission, Fuel type, City/Highway/Combined (L/100 km), Combined (mpg), CO2 emissions (g/km), CO2 rating, Smog rating` |
| `plugin_hybrid_vehicles.csv` | Sursă PHEV: 43 rânduri (2023–2024), NRCan. Are `Fuel type 1/2`, `Motor (kW)`, `Range 1/2`, `Combined Le/100 km` (text de tip `3.9 ([34.8 kWh + 0.0 L]/100 km)`), `Combined (L/100 km)` |
| `battery_electric_vehicles.csv` | Sursă BEV: 90 rânduri (2023–2025), NRCan. Are `Motor (kW)`, `Combined (kWh/100 km)`, `Combined (Le/100 km)`, `Range (km)`, `Recharge time (h)` |
| `etl_pipeline_v2.py` | Pipeline-ul ETL (pandas + numpy). Un singur script, rulat de la rădăcina folderului |
| `cleaned_horse_powertrain_data_v2.csv` | Output ETL: 872 rânduri × 16 coloane, fără NaN în coloanele de analiză, fără duplicate. Se încarcă în BigQuery |
| `queries_v2.sql` | 3 interogări BigQuery pentru KPI-uri și analize |
| `venv/` | Mediu virtual Python (nu se editează, nu se analizează) |

Repo git (branch `main`, remote `origin` = github.com/dominictapangea/powertrain-dashboard; commit-urile se fac fără trailer `Co-Authored-By`, cu emailul noreply de GitHub); `.gitignore` exclude `venv/`, credențiale (`*.json` de cont de serviciu, `.env`, chei) și fișiere temporare. Dependențe: `pip install -r requirements.txt` (pandas 3.0.5, numpy 2.5.1). Nu există în folder teste. Dashboard-urile (Power BI și Looker Studio) sunt descrise în secțiunea „Dashboard-uri".

## Pipeline

```powershell
.\venv\Scripts\Activate.ps1
python etl_pipeline_v2.py
```

Rulează din folderul proiectului (căile CSV sunt relative). Dependențe: `pandas`, `numpy`. Scrie `cleaned_horse_powertrain_data_v2.csv` și afișează distribuția pe `powertrain_type`.

### Ce face ETL-ul
1. `read_nrcan(path)` citește fiecare CSV (`encoding="latin1"`) și normalizează numele coloanelor (lowercase, `_`, fără paranteze/slash). Un singur loc pentru logica de citire.
2. `to_common_schema(...)` mapează o sursă la schema comună; `load_ice`, `load_phev`, `load_bev` doar îi dau parametrii specifici (consum, cod și etichetă combustibil, tip propulsie). `manufacturer` în `.title()`.
3. `powertrain_type` vine din **dataset-ul sursă** (fix față de v1, unde era dedus din cilindree); doar ICE e subîmpărțit după `fuel_type`: `D` → Diesel ICE, `E` → Flex-Fuel (Ethanol), restul → Conventional ICE (Gasoline).
4. Concatenează, elimină rândurile fără CO2 sau consum, apoi `drop_duplicates()` (plasă de siguranță; loghează câte rânduri a scos, acum 0).
5. Calculează `eco_score = 100 − CO2 / max(CO2) × 100` (rotunjit la 0.1) și `efficiency_tier` prin `assign_efficiency_tier` (praguri pe valoarea CO2, nu pe rang).
6. Sortează după `model_year, manufacturer, model, transmission` și exportă.

### Schema output (16 coloane)
`model_year, manufacturer, model, vehicle_class, transmission, engine_size_l, cylinders, motor_kw, fuel_type_code, fuel_type_label, combined_consumption_le_100km, co2_emissions_g_km, powertrain_type, source_dataset, eco_score, efficiency_tier`

- `engine_size_l`, `cylinders` sunt goale (NaN) pentru BEV; `motor_kw` e gol pentru ICE.
- `combined_consumption_le_100km` = litri-echivalent / 100 km, comparabil între toate tipurile.
- Praguri `efficiency_tier` (g/km CO2): A ≤ 183 · B 184–242 · C 243–291 · D ≥ 292.

Distribuție actuală: Conventional ICE (Gasoline) 715 · BEV 90 · PHEV 43 · Diesel ICE 18 · Flex-Fuel 6. Ani: 2023 (33), 2024 (802), 2025 (37). Tier-uri: A 220 · B 216 · C 218 · D 218.

Consum mediu (Le/100 km): BEV 2,42 · PHEV 3,58 · Diesel 10,33 · Gasoline 11,01 · Flex-Fuel 18,70. CO2 mediu (g/km): BEV 0 · PHEV 91,1 · Gasoline 258,0 · Diesel 277,5 · Flex-Fuel 309,7.

## BigQuery
Tabelă: `` `your_project.your_dataset.analytics` `` — placeholder în toate cele 3 query-uri din `queries_v2.sql`; numele real al proiectului GCP și al datasetului nu sunt păstrate în repo. Înainte de a rula query-urile în BigQuery, înlocuiește placeholderul cu numele real.

**Stare: ✅ rezolvat.** Tabela `analytics` din BigQuery a fost reîncărcată cu schema v2 (16 coloane, 872 rânduri), din `cleaned_horse_powertrain_data_v2.csv`. Query-urile din `queries_v2.sql` nu folosesc coloanele schimbate și rămân valide.

Query-uri: (1) KPI pe tip de propulsie, (2) top 5 producători cei mai curați (`RANK`, minim 5 modele), (3) % electrificare pe clasă de vehicul.

## Agent (întrebări în limbaj natural pe tabela `analytics`)
Folder `agent/`: script de terminal (`python agent\agent.py`) care folosește Gemini (`google-genai`, Interactions API, model implicit `gemini-3.5-flash-lite`; `gemini-3.8-flash` și `3.6-flash` expirau sau durau 40–95 s la testare) cu un singur tool, `run_sql(query)`. Fișiere: `agent.py` (bucla și BigQuery), `sql_guard.py` (validator `sqlglot`: un singur SELECT, doar tabela `analytics`, `LIMIT` forțat la 100), `schema_info.py` (descrierea tabelei pentru model), teste `test_*.py` (`python -m pytest agent`, rulează offline) și `agent/README.md`.
- Setări în `.env` din rădăcină (git-ignorat; model în `.env.example`): `GEMINI_API_KEY`, `GEMINI_MODEL`, `BQ_PROJECT`, `BQ_DATASET`. BigQuery se autentifică prin `gcloud auth application-default login`, fără fișier de chei. Dependențe: `pip install -r requirements-agent.txt`.
- Interogările rulează cu `maximum_bytes_billed` = 100 MB (BigQuery taxează minimum 10 MB pe interogare) și după un dry run.
- Dacă schimbi schema tabelei, actualizează valorile din `schema_info.py` (testul le compară cu CSV-ul).

## Dashboard-uri

**Stare: ✅ ambele dashboard-uri sunt reconectate la datele v2** (tabela BigQuery / CSV-ul curat de 872 rânduri). Același layout în ambele instrumente, „Powertrain & Emissions Dashboard":
- KPI-uri: 872 vehicule · CO2 mediu 223,87 g/km · consum mediu 9,80 Le/100km · 15,3% electrificate.
- Filtre pe `vehicle_class` și `model_year`; două bar chart-uri pe tip de propulsie (CO2 mediu și consum mediu).
- Notă în dashboard: doar CO2 la țeavă (fără producția de electricitate/baterie); sursa: Natural Resources Canada.

| Instrument | Fișier în repo |
|---|---|
| Power BI | `horse_dashboard.pbix` (66 KB) și captura `docs/PowerBI_Dashboard.png` |
| Looker Studio | `docs/Powertrain_Dashboard.pdf` (export PDF) |

Link public Looker Studio: https://datastudio.google.com/s/gN-N_tdDh6o

Istoric: versiunea v1 a dashboard-ului (739 de vehicule, categoriile `Conventional ICE / Hybrid Powertrain / Alternative Synthetic Fuel`, coloane precum `engine_power_hp`) a fost înlocuită de v2 și nu mai este în repo.

## Erori găsite în analiza inițială și cum au fost reparate

| # | Eroare găsită | Cum arăta înainte | Ce s-a făcut în `etl_pipeline_v2.py` | Cum arată acum |
|---|---|---|---|---|
| 1 | **Consum necomparabil între tipuri**: PHEV folosea doar coloana de benzină `Combined (L/100 km)`, fără electricitate; BEV era în Le/100 km, ICE în L/100 km | Medie PHEV 8,53 vs BEV 2,42 | Pentru PHEV se parsează numărul din textul `Combined Le/100 km` (ex. `3.9 ([34.8 kWh + 0.0 L]/100 km)` → 3,9), care include electricitatea. Parsat pe toate cele 43 de rânduri | Medie PHEV **3,58** Le/100 km, comparabil cu BEV 2,42 și ICE ~11 |
| 2 | **`efficiency_tier` după rang** (`rank(method="first")`): grupe forțat egale (218 fiecare), iar vehicule cu același CO2 puteau ajunge în tier-uri diferite | A/B/C/D = 218/218/218/218, limite nedefinite | `assign_efficiency_tier`: cuartilele se calculează pe **valoarea CO2** și se aplică cu `pd.cut`, deci valori egale rămân în același tier | A ≤183 g/km (220) · B 184–242 (216) · C 243–291 (218) · D ≥292 (218). Fără suprapuneri între tier-uri |
| 3 | **3 perechi de rânduri „duplicate"** (Ford Bronco Black Diamond 4WD, Honda Civic Sedan, Porsche 911 Carrera 4S) | Rânduri identice în output | De fapt nu erau duplicate reale, ci variante diferite (transmisie/motor) la care schema nu păstra coloanele de diferențiere. S-au adăugat `transmission`, `engine_size_l`, `cylinders`, `motor_kw`. S-a păstrat și `drop_duplicates()` ca plasă de siguranță, cu log | 0 duplicate, 0 rânduri pierdute. Ex.: Civic Sedan apare ca AV/2.0, AV7/1.5, AV7/2.0 |
| 4 | **Loader-e copy-paste**: normalizarea coloanelor repetată de 3 ori, același `pd.DataFrame({...})` în fiecare | 3 funcții de ~20 de linii fiecare | `read_nrcan()` + `to_common_schema()`; loader-ele rămân subțiri și transmit doar ce diferă | Logica comună e într-un singur loc; o coloană nouă se adaugă o dată |

**Verificat după reparații:** 872 rânduri (la fel ca înainte), 0 duplicate, 0 NaN în CO2/consum/tier/eco_score, `eco_score` neschimbat față de varianta veche, distribuția pe `powertrain_type` identică.

### Probleme rămase (nereparate intenționat sau în afara ETL)
1. ✅ ~~Dashboard-urile și tabela BigQuery pe date v1~~ — rezolvat: BigQuery reîncărcat cu schema v2, Power BI și Looker Studio reconectate.
2. **CO2 = emisii la țeavă**: BEV = 0 prin definiție, deci `eco_score` = 100 pentru toți BEV. Nu includ producția electricității sau a bateriei; de menționat explicit în prezentare.
3. **ICE există doar în 2024**: doar BEV și PHEV au mai mulți ani, cu eșantioane mici (2023: 33, 2025: 37), deci filtrul pe an elimină ICE pentru 2023 și 2025 și nu se poate face o analiză an-de-an relevantă.
4. **Gaz natural (`N`)** ar fi etichetat „Conventional ICE (Gasoline)" (acum 0 rânduri cu `N`, deci fără impact curent).
5. `eco_score` depinde de `max(CO2)` din setul curent (608 g/km): scorul unui vehicul se schimbă dacă setul de date se schimbă.
6. Căi relative și nume de fișier de output hardcodate; fără validări (nr. rânduri, valori negative) și fără teste. (`requirements.txt` există acum.)

## Convenții pentru lucrul în acest proiect
- Păstrează numele de coloane `snake_case` în engleză; orice coloană nouă trebuie propagată în ETL, în tabela BigQuery și în sursele de date din Looker Studio/Power BI.
- Nu modifica fișierele CSV sursă; toate transformările se fac în `etl_pipeline_v2.py`.
- După orice schimbare de schemă: rulează ETL, reîncarcă `cleaned_horse_powertrain_data_v2.csv` în tabela `analytics` din BigQuery, apoi reîmprospătează dashboard-urile.
- Când raportezi cifre (media CO2, nr. vehicule), calculează-le din `cleaned_horse_powertrain_data_v2.csv`, nu din PDF-urile vechi.
- Sursa datelor este Natural Resources Canada (Government of Canada Open Data) — de citat în orice prezentare.


## Următorii pași (prioritizați)
1. ✅ Făcut: `cleaned_horse_powertrain_data_v2.csv` reîncărcat în BigQuery (tabela `analytics`, 16 coloane, 872 rânduri).
2. ✅ Făcut: Looker Studio și Power BI reconectate la v2; exporturile sunt în `docs/`.
3. Argumente CLI pentru căi, câteva teste pe schema output.
4. ✅ Făcut: linkul public Looker Studio e în secțiunea „Dashboard-uri" (de adăugat și într-un README, dacă se creează unul).
5. Adaugă în `docs/` o captură PNG a dashboard-ului Looker Studio (pentru previzualizare pe GitHub).
