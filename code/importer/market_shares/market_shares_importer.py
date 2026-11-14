import os
import psycopg2

# Annual market shares (%) from 2021 to 2025
market_shares = {
    "AH": [35.7, 36.7, 36.8, 37.7, 38.2],
    "Jumbo": [21.7, 21.5, 20.9, 20.3, 19.9],
    "Lidl": [10.6, 10.8, 11.0, 11.1, 11.2],
    "Plus": [6.5, 6.8, 7.7, 8.1, 8.1]
}

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"]
)

try:
    with conn.cursor() as cursor:
        for supermarket_name, shares in market_shares.items():
            for year, share in zip(range(2021, 2026), shares):
                cursor.execute("""
                    INSERT INTO MarketShares (supermarketId, year, marketShare)
                    SELECT supermarketId, %s, %s
                    FROM Supermarkets
                    WHERE LOWER(name) = LOWER(%s)
                    ON CONFLICT (supermarketId, year)
                    DO UPDATE SET marketShare = EXCLUDED.marketShare
                """, (year, share, supermarket_name))

    conn.commit()
    print("Market shares imported successfully.")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()