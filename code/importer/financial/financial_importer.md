# Economy Statistics Loader

## Description

This script downloads yearly economic indicators for the Netherlands from the CBS Open Data API and loads them into the PostgreSQL `EconomyStatistics` table. It stores one row per year, dated 1 January.

The importer combines three CBS datasets:

* `83136NED`, *Consumentenprijzen; basisjaren vanaf 1969*: the consumer price index (CPI) and its yearly rate of change.
* `83932NED`, *Inkomen van huishoudens; inkomensklassen, huishoudenskenmerken*: the average gross, disposable and standardized income of all private households.
* `85663NED`, *Cao-lonen, contractuele loonkosten en arbeidsduur*: the yearly increase of collective (cao) wages. Neither of the other two tables contains wages, so this table supplies `yearlyWageIncrease`.

Only yearly periods (CBS keys ending in `JJ00`, such as `2024JJ00`) are used. The three sources are joined on the year, and every year with at least one value gets a row. A value CBS does not publish for a year is stored as `NULL`.

## Imported Database Columns

| Column | Source | Meaning |
|---|---|---|
| `date` | all | The year, stored as 1 January because the column has type `DATE`. |
| `CPI` | 83136NED | Yearly average CPI with **2025 = 100**. |
| `CPIYearlyRateOfChange` | 83136NED | Percentage change of the yearly CPI compared with the previous year. |
| `averageGrossIncome` | 83932NED | Average gross income (*bruto inkomen*) per private household, in euros. |
| `averageDisposableIncome` | 83932NED | Average disposable income (*besteedbaar inkomen*) per private household, in euros. |
| `averageStandardizedIncome` | 83932NED | Average standardized income (*gestandaardiseerd inkomen*), in euros. It corrects for household size and composition. |
| `yearlyWageIncrease` | 85663NED | Percentage change of collective wages per month, including special payments, for all cao sectors and all economic activities, from the current (not first-published) figures. |

Available years at the time of writing: CPI 1969–2025, CPI change 1970–2025, income 2011–2025 (2025 is provisional), wage increase 1973–2025.

## How the Values Are Derived

**CPI chaining.** 83136NED publishes a separate index column for every base year (1969 = 100 up to 2025 = 100), and each column covers only part of the history. The importer uses the newest base (2025 = 100) and rescales each older base onto it. It links them at the latest year both series share and only fills years the newer base does not cover. The result is one continuous series.

**CPI rate of change.** The importer computes the rate of change within a single base: for each year, the newest base that has both that year and the previous one. This means the chaining and rounding cannot distort it. The results match the inflation figures CBS publishes, for example 10.0 % for 2022 and 3.8 % for 2023.

**Income unit.** CBS publishes income in units of 1 000 euro with one decimal. The importer multiplies by 1 000 and stores euros, so the values are always multiples of 100.

**CBS keys.** Categories are found by their Dutch title (for example *Particuliere huishoudens* and *Totaal*), not by hard-coded keys. Some CBS keys are padded with spaces, and filters only match the padded form, so the raw key is used in `$filter`.

## Expected Input and Variables

The importer needs no local files. It downloads all data from `https://opendata.cbs.nl/ODataApi/OData` and follows CBS pagination links until every row has been retrieved.

The configuration lives at the top of the script:

* `CBS_BASE_URL`: base URL of the CBS OData API.
* `CPI_TABLE`, `INCOME_TABLE`, `WAGE_TABLE`: the CBS table IDs.
* `INCOME_CONCEPTS`: the income concepts that are imported and the column each one fills.
* `column_limits`: the largest value each `DECIMAL` column can hold. The importer stops before writing anything if a value would not fit.

## Dependencies

The required Python packages are listed in `requirements.txt` in this folder:

```text
python -m pip install -r requirements.txt
```

The CBS requests use Python's standard library, so no extra HTTP package is needed.

## Expected Environment Variables

When the script runs locally, the connection settings come from the project's `.env` file. The script finds it by searching upwards from its own folder. In Docker, compose supplies them through `env_file`.

* `DB_HOST`: PostgreSQL server hostname.
* `DB_NAME`: database name.
* `DB_USER`: database username.
* `DB_PASSWORD`: database password.
* `DB_PORT` (optional): PostgreSQL port, default `5432`.

The script never prints the password.

## Code Structure

* Imports and configuration: CBS URL, table IDs, income concepts, output columns and column limits.
* CBS helper functions: `get_cbs_data` downloads paginated OData responses. `get_category_key` and `get_topic_key` find keys from their titles. `period_to_year` turns `2024JJ00` into `2024`.
* Source loaders: `load_cpi`, `load_income` and `load_wage_increase` each return one DataFrame indexed by year.
* `load_economy_statistics`: joins the three sources into the final table layout.
* `check_data_quality`: prints how many years and values each column has, and checks the decimal limits.
* Main execution: reads the environment, downloads and checks the data, then writes it in one transaction.

## Running the Script

Make sure PostgreSQL is running, the `EconomyStatistics` table exists, and the `.env` file contains valid settings. Then run, from this folder:

```text
python financial_importer.py
```

The machine needs internet access to the CBS API.

## Database Transaction and Re-running

All rows are written in one transaction, so a failure leaves the table unchanged.

Unlike the static importers, this loader is safe to run again. It uses `INSERT ... ON CONFLICT (date) DO UPDATE`: new years are added, and existing years are overwritten with the current CBS figures. This matters because CBS revises provisional figures, such as the latest income year. The importer never deletes rows.

## Docker Note

The `financial_importer` service in `docker-compose.yaml` builds this folder and runs the script. Run it from the project root with:

```text
docker compose run --rm --build financial_importer
```

The PostgreSQL database uses a persistent Docker volume. Avoid `docker compose down -v` unless you intend to delete the database and all its data.
