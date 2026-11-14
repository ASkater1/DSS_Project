# Market Shares Importer

## Description

This module imports annual market share data for four Dutch supermarkets (Albert Heijn, Jumbo, Lidl, and Plus) into PostgreSQL.

The data covers the years 2021–2025 and is stored in the `MarketShares` table, defined in `data/db/initdb.sql`.

Each record contains a supermarket ID, year, and market share percentage.

## How It Works

The importer:

1. Connects to PostgreSQL using the database environment variables.
2. Matches supermarket names with their IDs in the `Supermarkets` table.
3. Inserts the annual market share values into `MarketShares`.
4. Updates existing records if the same supermarket and year already exist.

## Docker Execution

The importer runs automatically through Docker Compose:

```bash
docker compose up -d --build
```

It waits for PostgreSQL to become healthy and for the static supermarket importer to finish successfully.

To check its logs:

```bash
docker compose logs market_shares_importer
```

## Validation

The importer was tested successfully with all 20 records (4 supermarkets × 5 years).

The combined market shares are:

| Year | Combined market share |
|---|---|
| 2021 | 74.5% |
| 2022 | 75.8% |
| 2023 | 76.4% |
| 2024 | 77.2% |
| 2025 | 77.4% |

**Data source:** Annual Dutch food retail market shares, 2021–2025. Add the original source URL here.