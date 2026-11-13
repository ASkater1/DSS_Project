#************************************************************************************
#----------------------------- SHARED CATEGORY IMPORTER -----------------------------*
#************************************************************************************
#
# Every supermarket stores product categories in its own format and with its own names,
# so categories cannot be compared between supermarkets. This script assigns every
# product to one category from a shared list (shared_categories.csv) and stores it in
# the database:
#
#   Categories          one row per shared category
#   Products.categoryId the shared category of each product
#
# The assignment uses two hand-made files in this folder:
#   category_mapping.csv   supermarket category path (level 1/2/3) -> shared category
#   lidl_label_rules.csv   keyword rules for Lidl's German Open Food Facts labels


# Importing necessary libraries
import os
import re
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text





# Folder with the category definition files (next to this script)
DEFINITIONS_DIR = Path(__file__).resolve().parent
SHARED_CATEGORIES_FILE = DEFINITIONS_DIR / "shared_categories.csv"
MAPPING_FILE = DEFINITIONS_DIR / "category_mapping.csv"
LIDL_RULES_FILE = DEFINITIONS_DIR / "lidl_label_rules.csv"

# Separator between the Lidl web category and its Open Food Facts labels
LIDL_LABEL_SEPARATOR = "&&&"

# Open Food Facts labels that are too broad to say anything about the product type.
# 'Pflanzliche Lebensmittel und Getränke' (plant-based food and drinks) is on almost
# every plant-based product, and its word 'Getränke' would otherwise mark it as a drink.
GENERIC_LIDL_LABELS = {
    "pflanzliche lebensmittel und getränke",
    "pflanzliche lebensmittel",
    "gemüse basierte lebensmittel und getränke",
    "frische nahrungsmittel",
    "frische pflanzliche lebensmittel",
    "en:groceries",
}

# Schema needed by this script. initdb.sql contains the same definitions, but it only
# runs when a new database is created, so existing databases are extended here.
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS categories (
        categoryid SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        isfood BOOLEAN NOT NULL,
        description TEXT
    )
    """,
    """
    ALTER TABLE products
    ADD COLUMN IF NOT EXISTS categoryid INTEGER REFERENCES categories(categoryid)
    """
]





# Function to undo UTF-8 text that was decoded as Latin-1 during the import
# (for example 'oliÃ«n' -> 'oliën' and 'GetrÃ¤nke' -> 'Getränke')
def repair_text(value: str) -> str:
    if not isinstance(value, str) or not any(character in value for character in "ÃÂ"):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value



# Function to clean one category level so small spelling differences do not matter
def normalise(value: str) -> str:
    value = repair_text(value or "")
    value = value.replace("''", "'")
    return re.sub(r"\s+", " ", value).strip()



# Function to split a category path into its levels, using the format of each supermarket
#   AH     Home\Producten\Zuivel, eieren\Yoghurt en skyr\...
#   Plus   Zuivel eieren boter\Verse zuivel\Yoghurt
#   Jumbo  Zuivel, eieren, boter ; Yoghurt en kwark ; ...
#   Lidl   Home/Eten & drinken/Kaas & Zuivel &&& <Open Food Facts labels>
def split_levels(supermarket: str, category: str) -> list[str]:
    category = repair_text(category or "")

    if supermarket == "AH":
        parts = category.split("\\")
        if parts[:2] == ["Home", "Producten"]:
            parts = parts[2:]
    elif supermarket == "Plus":
        parts = category.split("\\")
    elif supermarket == "Jumbo":
        parts = category.split(" ; ")
    elif supermarket == "Lidl":
        path = category.split(LIDL_LABEL_SEPARATOR)[0].strip()
        parts = path.split("/")[1:] if path.startswith("Home/") else []
    else:
        parts = []

    return [normalise(part) for part in parts if normalise(part)]



# Function to read the Open Food Facts labels of a Lidl category, without the labels
# that are too broad to be useful
def lidl_labels(category: str) -> str:
    category = repair_text(category or "")
    if LIDL_LABEL_SEPARATOR not in category:
        return ""
    labels = category.split(LIDL_LABEL_SEPARATOR, 1)[1].split(",")
    useful = [
        label.strip() for label in labels
        if label.strip() and label.strip().lower() not in GENERIC_LIDL_LABELS
    ]
    return ", ".join(useful)



# Function to read and check the three definition files
def load_definitions() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    shared = pd.read_csv(SHARED_CATEGORIES_FILE, encoding="utf-8")
    mapping = pd.read_csv(MAPPING_FILE, encoding="utf-8", dtype=str).fillna("")
    rules = pd.read_csv(LIDL_RULES_FILE, encoding="utf-8").sort_values("priority")

    # Every category used in the mapping and the rules must exist in the shared list
    known = set(shared["name"])
    for file_name, used in [("category_mapping.csv", mapping["shared_category"]),
                            ("lidl_label_rules.csv", rules["shared_category"])]:
        unknown = sorted(set(used) - known)
        if unknown:
            raise ValueError(f"{file_name} uses categories that are not in shared_categories.csv: {unknown}")

    # The same category path may only be mapped once
    for column in ["level_1", "level_2", "level_3"]:
        mapping[column] = mapping[column].map(normalise)
    duplicates = mapping[mapping.duplicated(["supermarket", "level_1", "level_2", "level_3"], keep=False)]
    if not duplicates.empty:
        raise ValueError(f"category_mapping.csv contains duplicate paths:\n{duplicates}")

    rules["regex"] = rules["pattern"].map(lambda pattern: re.compile(pattern, re.IGNORECASE))
    return shared, mapping, rules



# Function to find the shared category of every product.
# The most specific mapping row wins: level 3 before level 2 before level 1.
# For Lidl the Open Food Facts labels are tried first, because Lidl's own web category
# is missing for most products and sometimes wrong; the web category is the fallback.
def assign_categories(products: pd.DataFrame, mapping: pd.DataFrame,
                      rules: pd.DataFrame) -> pd.DataFrame:
    lookup = {
        (row.supermarket, row.level_1.casefold(), row.level_2.casefold(), row.level_3.casefold()): row.shared_category
        for row in mapping.itertuples()
    }

    results = []
    for row in products.itertuples():
        levels = split_levels(row.supermarket, row.category)
        level_1, level_2, level_3 = (levels + ["", "", ""])[:3]
        shared_category, source, key = None, None, None

        # Lidl: keyword rules on the Open Food Facts labels
        if row.supermarket == "Lidl":
            labels = lidl_labels(row.category)
            for rule in rules.itertuples():
                if labels and rule.regex.search(labels):
                    shared_category, source, key = rule.shared_category, "lidl_label", f"rule {rule.priority}"
                    break

        # All supermarkets: the category path, from most to least specific
        if shared_category is None and level_1:
            for candidate in [(level_1, level_2, level_3), (level_1, level_2, ""), (level_1, "", "")]:
                lookup_key = (row.supermarket,) + tuple(level.casefold() for level in candidate)
                if lookup_key in lookup:
                    shared_category, source, key = lookup[lookup_key], "mapping", candidate
                    break

        results.append((level_1, level_2, level_3, shared_category, source, key))

    assigned = products.copy()
    assigned[["level_1", "level_2", "level_3", "shared_category", "source", "matched_on"]] = pd.DataFrame(
        results, index=products.index
    )
    return assigned



# Function to list mapping rows whose category path does not occur in the products
# (usually a spelling mistake in category_mapping.csv)
def unused_mapping_rows(assigned: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    existing = set()
    for row in assigned.itertuples():
        levels = (row.level_1.casefold(), row.level_2.casefold(), row.level_3.casefold())
        existing.update({
            (row.supermarket, levels[0], "", ""),
            (row.supermarket, levels[0], levels[1], ""),
            (row.supermarket,) + levels
        })
    is_known = [
        (row.supermarket, row.level_1.casefold(), row.level_2.casefold(), row.level_3.casefold()) in existing
        for row in mapping.itertuples()
    ]
    return mapping[[not known for known in is_known]]



# Function to print how many products each supermarket has per shared category
def print_report(assigned: pd.DataFrame, mapping: pd.DataFrame):
    print("Category Report:")
    coverage = assigned.groupby("supermarket")["shared_category"].agg(
        products="size", categorised="count"
    )
    coverage["percentage"] = (coverage["categorised"] / coverage["products"] * 100).round(1)
    print(coverage.to_string())
    print()
    print(pd.crosstab(
        assigned["shared_category"].fillna("(no category)"), assigned["supermarket"], margins=True
    ).to_string())

    unused = unused_mapping_rows(assigned, mapping)
    if not unused.empty:
        print("\n[WARNING] Mapping rows that match no product (check the spelling):")
        print(unused.to_string(index=False))

    uncategorised = assigned[assigned["shared_category"].isna()]
    if not uncategorised.empty:
        print("\nMost common category paths without a shared category:")
        print(uncategorised.groupby(["supermarket", "category"]).size()
              .sort_values(ascending=False).head(15).to_string())



# Function to find the project's .env file by walking up from this script
def find_env_file() -> Path | None:
    for folder in Path(__file__).resolve().parents:
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
    return None





# Main execution
if __name__ == "__main__":

    # Locally the settings come from the project's .env; in Docker, compose's env_file sets them
    env_file = find_env_file()
    if env_file:
        load_dotenv(env_file)

    # Read database connection settings
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. Please set them in the .env file.")

    db_conn = create_engine(
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
    )

    # Read and check the definition files before touching the database
    shared, mapping, rules = load_definitions()
    print(f"Loaded {len(shared)} shared categories, {len(mapping)} mapping rows and {len(rules)} Lidl label rules.")

    # Every product belongs to one supermarket, which is known from its price records
    print("Reading products and their supermarkets...")
    with db_conn.connect() as conn:
        products = pd.read_sql(text("""
            WITH product_supermarket AS (
                SELECT DISTINCT supermarketid, productid FROM supermarketsproducts
            )
            SELECT p.productid, s.name AS supermarket, p.category
            FROM products p
            LEFT JOIN product_supermarket ps ON ps.productid = p.productid
            LEFT JOIN supermarkets s ON s.supermarketid = ps.supermarketid
        """), conn)

    if products.empty:
        sys.exit("No products found in the database. Run the product importers first.")

    assigned = assign_categories(products, mapping, rules)
    print_report(assigned, mapping)

    # Write the shared categories and the category of every product in one transaction
    with db_conn.begin() as conn:
        for statement in SCHEMA_STATEMENTS:
            conn.execute(text(statement))

        conn.execute(text("""
            INSERT INTO categories (name, isfood, description)
            VALUES (:name, :is_food, :description)
            ON CONFLICT (name) DO UPDATE SET
                isfood = EXCLUDED.isfood, description = EXCLUDED.description
        """), shared.to_dict("records"))

        # Load the assignments into a temporary table and update products in one statement;
        # only products whose category actually changes are updated
        conn.execute(text("CREATE TEMP TABLE product_category (productid TEXT, name TEXT) ON COMMIT DROP"))
        records = [
            {"productid": productid, "name": name if isinstance(name, str) else None}
            for productid, name in zip(assigned["productid"], assigned["shared_category"])
        ]
        conn.execute(text("INSERT INTO product_category (productid, name) VALUES (:productid, :name)"), records)
        updated = conn.execute(text("""
            UPDATE products p
            SET categoryid = c.categoryid
            FROM product_category pc
            LEFT JOIN categories c ON c.name = pc.name
            WHERE p.productid = pc.productid
              AND p.categoryid IS DISTINCT FROM c.categoryid
        """)).rowcount

    print(f"\n{updated} products received a new or changed shared category.")
