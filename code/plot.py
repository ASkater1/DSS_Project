from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_DIR = Path(__file__).resolve().parent.parent
OUTPUT = PROJECT_DIR / "data" / "processed"


def plot_product_history():
    query = input("Enter a product name or ID: ").strip()
    if not query:
        print("Please enter a product name or ID.")
        return

    if not OUTPUT.exists():
        print(f"Processed data folder not found: {OUTPUT}")
        return

    matches = []

    for store_folder in OUTPUT.iterdir():
        products_file = store_folder / "products.csv"
        if not store_folder.is_dir() or not products_file.exists():
            continue

        products = pd.read_csv(
            products_file, dtype=str, keep_default_na=False, encoding="utf-8-sig"
        )
        if "prod_id" not in products.columns:
            continue

        found = products["prod_id"].str.contains(query, case=False, regex=False)
        for column in products.columns:
            if column != "prod_id":
                found |= products[column].str.contains(query, case=False, regex=False)

        for _, product in products[found].drop_duplicates("prod_id").iterrows():
            matches.append((store_folder, product))

    if not matches:
        print(f"No products found matching '{query}'.")
        return

    print("\nMatches:")
    for index, (store_folder, product) in enumerate(matches, start=1):
        details = " | ".join(
            f"{column}: {product[column]}"
            for column in product.index
            if column != "prod_id" and product[column]
        )
        print(f"{index}. {store_folder.name} | ID: {product['prod_id']} | {details}")

    if len(matches) == 1:
        choice = 1
    else:
        try:
            choice = int(input("\nChoose a match number: "))
            if not 1 <= choice <= len(matches):
                raise ValueError
        except ValueError:
            print("Invalid selection.")
            return

    store_folder, product = matches[choice - 1]
    prices_file = store_folder / "prices.csv"

    if not prices_file.exists():
        print(f"Price history not found: {prices_file}")
        return

    prices = pd.read_csv(prices_file, dtype={"prod_id": str}, encoding="utf-8-sig")
    history = prices[prices["prod_id"] == product["prod_id"]].copy()
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["price"] = pd.to_numeric(history["price"], errors="coerce")
    history = history.dropna(subset=["date", "price"]).sort_values("date")

    if history.empty:
        print("No valid price history found for this product.")
        return

    plt.figure(figsize=(10, 5))
    plt.plot(history["date"], history["price"], marker="o")
    plt.title(f"Price history — {product['prod_id']} ({store_folder.name})")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.grid(True)
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    plot_product_history()