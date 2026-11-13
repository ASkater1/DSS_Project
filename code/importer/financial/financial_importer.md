# Economy Statistics Loader

## Description

This script downloads monthly economic indicators for the Netherlands from the CBS Open Data API and loads them into the PostgreSQL `EconomyStatistics` table. It stores one row per month, dated the 1st of that month, from November 2022 onwards (the first month of the supermarket price data).

The importer combines three CBS datasets:

* `83136NED`, *Consumentenprijzen; basisjaren vanaf 1969*: the monthly consumer price index (CPI) and its rate of change compared with the same month a year earlier.
* `83932NED`, *Inkomen van huishoudens; inkomensklassen, huishoudenskenmerken*: the average gross, disposable and standardized income of all private households.
* `85663NED`, *Cao-lonen, contractuele loonkosten en arbeidsduur*: the monthly increase of collective (cao) wages compared with a year earlier. Neither of the other two tables contains wages, so this table supplies `yearlyWageIncrease`.

CPI and wages use monthly periods (CBS keys such as `2024MM03`). CBS publishes household income only per year (`2024JJ00`), so every month gets the income of its own year. Months in a year CBS has not published income for yet store `NULL` in the income columns.

## Imported Database Columns

| Column | Source | Meaning |
|---|---|---|
| `date` | all | The month, stored as its 1st day because the column has type `DATE`. |
| `CPI` | 83136NED | Monthly CPI with **2015 = 100**. |
| `CPIYearlyRateOfChange` | 83136NED | Percentage change of the CPI compared with the same month a year earlier (the official CBS inflation figure). |
| `CPIMonthlyRateOfChange` | 83136NED | Percentage change of the CPI compared with the previous month. |
| `averageGrossIncome` | 83932NED | Average gross income (*bruto inkomen*) per private household for that month's year, in euros. |
| `averageDisposableIncome` | 83932NED | Average disposable income (*besteedbaar inkomen*) per private household for that month's year, in euros. |
| `averageStandardizedIncome` | 83932NED | Average standardized income (*gestandaardiseerd inkomen*) for that month's year, in euros. It corrects for household size and composition. |
| `yearlyWageIncrease` | 85663NED | Percentage change of collective wages per month, including special payments, compared with the same month a year earlier. It covers all cao sectors and all economic activities, and uses the current (not first-published) figures. |

Available at the time of writing: CPI, CPI change and wage increase November 2022 – October 2026; income 2022–2025 (2025 is provisional).

## How the Values Are Derived

**CPI base year.** The `CPI` column is a monthly index with **2015 = 100**: the average price level of 2015 is 100, so 135 means prices are 35 % higher than in 2015. CBS stopped publishing the 2015 = 100 series after December 2025 and continues it as 2025 = 100. For the months it still has, the importer uses the official 2015 = 100 figures. Later months are converted from the 2025 = 100 series, using the ratio of the averages over the months both series share (2025). This is the same factor CBS uses to convert between base years, about 1.3456. The base year is set by `CPI_BASE_YEAR` in the script.

**CPI rates of change.** `CPIYearlyRateOfChange` compares each month with the same month a year earlier (the official CBS inflation figure). `CPIMonthlyRateOfChange` compares it with the previous month. Both are computed within a single CBS series that has both months, so the conversion between base years and rounding cannot distort them. The 2015 = 100 series is used first, so the rates match the stored `CPI`. The 2025 = 100 series only fills months the older series no longer covers. That is also why the importer downloads one extra year of CPI (2021 for a start in November 2022). All 24 figures for 2025 match CBS's published *maandmutatie* and *jaarmutatie* (table 83131NED). For example, January 2023 shows 7.6 % on a year earlier and −1.4 % on the previous month.

**Start and end month.** Rows start in `START_MONTH` (November 2022), so the economy statistics start in the same month as the supermarket price data and can be compared with it from the first month. The CBS tables are downloaded from January of that year, because the `Perioden ge` filter works per year and is not applied reliably by every CBS table; months before the start month are then removed in the code.

The last month is set by today's date in `get_latest_month`: it is the month before the current one. CBS publishes a month's figures during the following month, so the current month is never complete. Run on 11 November 2026, the importer fetches up to October 2026. If CBS has not published the previous month yet, the last available month is used.

**Income unit.** CBS publishes income in units of 1 000 euro with one decimal. The importer multiplies by 1 000 and stores euros, so the values are always multiples of 100.

**CBS keys.** Categories are found by their Dutch title (for example *Particuliere huishoudens* and *Totaal*), not by hard-coded keys. Some CBS keys are padded with spaces, and filters only match the padded form, so the raw key is used in `$filter`.

## Expected Input and Variables

The importer needs no local files. It downloads all data from `https://opendata.cbs.nl/ODataApi/OData` and follows CBS pagination links until every row has been retrieved.

The configuration lives at the top of the script:

* `CPI_BASE_YEAR`: base year of the stored CPI, currently `2015`.
* `START_MONTH`: first month to import, written as YYYY-MM, currently `2022-11`. It can be overridden with the environment variable `ECONOMY_IMPORTER_START_MONTH`, for example `ECONOMY_IMPORTER_START_MONTH=2023-01`.
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
* CBS helper functions: `get_cbs_data` downloads paginated OData responses. `get_category_key` and `get_topic_key` find keys from their titles. `period_to_year` turns `2024JJ00` into `2024`, and `period_to_month` turns `2024MM03` into the month 2024-03.
* Source loaders: `load_cpi`, `load_income` and `load_wage_increase` each return one DataFrame: CPI and wages indexed by month, income indexed by year.
* `get_latest_month`: works out the last month to import from today's date.
* `load_economy_statistics`: joins the three sources into the final table layout, giving every month the income of its year.
* `check_data_quality`: prints how many months and values each column has, and checks the decimal limits.
* `load_stored_statistics`: reads the months already in `EconomyStatistics`.
* `find_outdated_months`: compares the CBS data with the stored data and returns only the months that are new or have a changed value.
* Main execution: reads the environment, downloads and checks the data, compares it with the database, and writes only the outdated months in one transaction.

## Running the Script

Make sure PostgreSQL is running, the `EconomyStatistics` table exists, and the `.env` file contains valid settings. Then run, from this folder:

```text
python financial_importer.py
```

The machine needs internet access to the CBS API.

## Comparison with the Stored Data

Before writing, the importer reads the months already stored from `START_MONTH` onwards and compares them with the latest CBS data. A month is **outdated** when:

* it is not in the database yet (a **new** month), or
* at least one of its values differs from the latest CBS value (a **changed** month). This happens when CBS revises provisional figures, such as the latest income year. Two empty values count as equal.

Only outdated months are written. If nothing is outdated, the importer prints this message and stops without writing:

```text
[INFO] Stored economy statistics are up to date. Nothing to import.
```

Otherwise it lists the new and changed months before writing them, for example:

```text
Comparison with the database:
  Months stored: 45
  New months: 1 ['2026-10']
  Changed months: 0 []
```

Months in the database that are not in the CBS data, such as rows from before `START_MONTH`, are left alone. The importer never deletes rows.

## Database Transaction

The outdated months are written in one transaction with `INSERT ... ON CONFLICT (date) DO UPDATE`: new months are added, and changed months are overwritten. A failure leaves the table unchanged. Unlike the static importers, this loader is safe to run as often as you like.

## Docker Note

The `financial_importer` service in `docker-compose.yaml` builds this folder and runs the script. Run it from the project root with:

```text
docker compose run --rm --build financial_importer
```

The PostgreSQL database uses a persistent Docker volume. Avoid `docker compose down -v` unless you intend to delete the database and all its data.
