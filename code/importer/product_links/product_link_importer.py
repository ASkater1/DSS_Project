#************************************************************************************
#-------------------------- PRODUCT LINKING DATA LOADER-----------------------------*
#************************************************************************************


# Importing necessary libraries

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


# Get the project root directory from this script (inside Docker this resolves to /project)
PROJECT_DIR = Path(__file__).resolve().parents[3]

# Default location of the semicolon-delimited product linking CSV file
DEFAULT_INPUT_FILE = PROJECT_DIR / "data" / "raw" / "product_linking.csv"

# CSV columns containing product IDs and their matching supermarket database IDs
STORE_COLUMNS = {
    "AH_id": ("AH", 1),
    "Jumbo_id": ("Jumbo", 2),
    "Lidl_id": ("Lidl", 3),
    "Plus_id": ("Plus", 4),
}

# Columns that must be present in the source CSV file
REQUIRED_COLUMNS = [
    "cluster_id",
    "cluster_name",
    "size",
    "n_products",
    "n_stores",
    *STORE_COLUMNS,
    "confidence",
]

# Database tables and index required to store the product clusters and their members
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS productclusters (
        clusterid TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        size TEXT NOT NULL,
        declaredproductcount INTEGER NOT NULL CHECK (declaredproductcount > 0),
        declaredstorecount SMALLINT NOT NULL CHECK (declaredstorecount > 0),
        confidence TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS productclusterlinks (
        clusterid TEXT NOT NULL REFERENCES productclusters(clusterid) ON DELETE CASCADE,
        supermarketid INTEGER NOT NULL REFERENCES supermarkets(supermarketid),
        sourceproductid TEXT NOT NULL,
        productid TEXT REFERENCES products(productid) ON DELETE SET NULL,
        PRIMARY KEY (supermarketid, sourceproductid),
        UNIQUE (productid)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS productclusterlinks_clusterid_idx
    ON productclusterlinks(clusterid)
    """,
]


# Function to find the nearest .env file by searching upwards from this script
def find_env_file() -> Path | None:
    for folder in Path(__file__).resolve().parents:
        candidate = folder / ".env"
        if candidate.is_file():
            return candidate
    return None


# Function to read, validate and split the CSV into clusters and product memberships
def load_source(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:

    # Check whether the configured source file exists
    if not path.is_file():
        raise FileNotFoundError(f"Product-linking CSV not found: {path}")

    # Read all values as text so product IDs keep their exact original format
    source = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False)

    # Check that the CSV has exactly the expected columns
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in source.columns]
    unexpected_columns = [column for column in source.columns if column not in REQUIRED_COLUMNS]
    if missing_columns or unexpected_columns:
        raise ValueError(
            f"Invalid CSV columns. Missing: {missing_columns or 'none'}; "
            f"unexpected: {unexpected_columns or 'none'}"
        )

    # Clean whitespace from all textual fields
    source = source[REQUIRED_COLUMNS].copy()
    text_columns = ["cluster_id", "cluster_name", "size", "confidence", *STORE_COLUMNS]
    for column in text_columns:
        source[column] = source[column].astype(str).str.strip()

    # Reject clusters that are missing required descriptive information
    required_text = ["cluster_id", "cluster_name", "size", "confidence"]
    empty_required = source[required_text].eq("").any(axis=1)
    if empty_required.any():
        raise ValueError(
            "Rows with empty required cluster fields: "
            + ", ".join(source.loc[empty_required, "cluster_id"].replace("", "(missing)").head(10))
        )

    # Convert the declared counts and require positive whole numbers
    for column in ["n_products", "n_stores"]:
        numeric = pd.to_numeric(source[column], errors="coerce")
        if numeric.isna().any() or (numeric <= 0).any() or (numeric % 1 != 0).any():
            raise ValueError(f"{column} must contain positive whole numbers")
        source[column] = numeric.astype(int)

    # Each cluster ID may occur only once in the CSV
    duplicate_clusters = source[source["cluster_id"].duplicated(keep=False)]
    if not duplicate_clusters.empty:
        raise ValueError(
            "Duplicate cluster IDs: "
            + ", ".join(sorted(duplicate_clusters["cluster_id"].unique())[:10])
        )

    # Convert the supermarket-specific ID columns into one membership row per product
    member_records = []
    for row in source.itertuples(index=False):
        product_count = 0
        store_count = 0
        for column, (store_name, supermarket_id) in STORE_COLUMNS.items():
            cell = getattr(row, column)
            product_ids = [value.strip() for value in cell.split(";") if value.strip()]
            if product_ids:
                store_count += 1
            product_count += len(product_ids)
            member_records.extend(
                {
                    "clusterid": row.cluster_id,
                    "supermarketid": supermarket_id,
                    "supermarket": store_name,
                    "sourceproductid": product_id,
                }
                for product_id in product_ids
            )

        # Compare the parsed products and stores with the counts declared by the source
        if product_count != row.n_products or store_count != row.n_stores:
            raise ValueError(
                f"Declared counts do not match cluster {row.cluster_id}: "
                f"products {row.n_products}/{product_count}, stores {row.n_stores}/{store_count}"
            )

    # Validate the resulting membership table
    members = pd.DataFrame(member_records)
    if members.empty:
        raise ValueError("The CSV contains no product memberships")

    # A source product may belong to only one cluster
    duplicates = members[
        members.duplicated(["supermarketid", "sourceproductid"], keep=False)
    ]
    if not duplicates.empty:
        examples = duplicates[["supermarket", "sourceproductid"]].drop_duplicates().head(10)
        raise ValueError(
            "Products assigned more than once: "
            + ", ".join(f"{row.supermarket}:{row.sourceproductid}" for row in examples.itertuples())
        )

    # Rename the cluster columns so they match the database table
    clusters = source.rename(columns={
        "cluster_id": "clusterid",
        "cluster_name": "name",
        "n_products": "declaredproductcount",
        "n_stores": "declaredstorecount",
    })[[
        "clusterid",
        "name",
        "size",
        "declaredproductcount",
        "declaredstorecount",
        "confidence",
    ]]
    return clusters, members


# Function to connect source product IDs to products that currently exist in the database
def resolve_products(connection, members: pd.DataFrame) -> pd.DataFrame:

    # Read every known product and supermarket combination
    existing = pd.read_sql(text("""
        SELECT DISTINCT sp.productid, sp.supermarketid
        FROM supermarketsproducts sp
    """), connection)

    # Reject source IDs that exist in the database but are assigned to another supermarket
    known_stores = existing.groupby("productid")["supermarketid"].agg(set).to_dict()
    wrong_store = members[
        members["sourceproductid"].isin(known_stores)
        & members.apply(
            lambda row: row["supermarketid"]
            not in known_stores.get(row["sourceproductid"], set()),
            axis=1,
        )
    ]
    if not wrong_store.empty:
        row = wrong_store.iloc[0]
        raise ValueError(
            f"Product {row.sourceproductid!r} is assigned to {row.supermarket}, "
            "but the database associates it with another supermarket"
        )

    # Keep unresolved IDs as empty product references so a later rerun can resolve them
    existing_pairs = set(zip(existing["supermarketid"], existing["productid"]))
    resolved = members.copy()
    resolved["productid"] = [
        source_id if (supermarket_id, source_id) in existing_pairs else None
        for supermarket_id, source_id in zip(
            resolved["supermarketid"], resolved["sourceproductid"]
        )
    ]
    return resolved


# Function to print a data quality summary before writing to the database
def print_report(clusters: pd.DataFrame, members: pd.DataFrame) -> None:
    resolved = members["productid"].notna()
    print("Product Linking Data Quality Report:")
    print("Clusters:", len(clusters))
    print("Memberships:", len(members))
    print("Resolved products:", int(resolved.sum()))
    print("Unresolved source product IDs:", int((~resolved).sum()))
    print("Confidence levels:")
    print(clusters["confidence"].value_counts().sort_index().to_string())
    print("Memberships per supermarket:")
    print(members.groupby("supermarket").size().sort_index().to_string())

    # Show a small sample of products that are not yet present in the database
    unresolved = members[~resolved]
    if not unresolved.empty:
        print("\n[WARNING] Unresolved memberships are retained for a later rerun:")
        print(unresolved.groupby("supermarket").size().sort_index().to_string())
        print("Examples:")
        print(
            unresolved[["clusterid", "supermarket", "sourceproductid"]]
            .head(10)
            .to_string(index=False)
        )


# Function to synchronize the validated CSV snapshot with the database
def import_links(connection, clusters: pd.DataFrame, members: pd.DataFrame) -> None:

    # Create the required schema when importing into an existing database
    for statement in SCHEMA_STATEMENTS:
        connection.execute(text(statement))

    # Temporary staging tables keep the complete snapshot inside one transaction
    connection.execute(text("""
        CREATE TEMP TABLE staged_productclusters (
            clusterid TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            size TEXT NOT NULL,
            declaredproductcount INTEGER NOT NULL,
            declaredstorecount SMALLINT NOT NULL,
            confidence TEXT NOT NULL
        ) ON COMMIT DROP
    """))
    connection.execute(text("""
        CREATE TEMP TABLE staged_productclusterlinks (
            clusterid TEXT NOT NULL,
            supermarketid INTEGER NOT NULL,
            sourceproductid TEXT NOT NULL,
            productid TEXT
        ) ON COMMIT DROP
    """))

    # Insert the validated cluster data into the staging table
    connection.execute(
        text("""
            INSERT INTO staged_productclusters
                (clusterid, name, size, declaredproductcount, declaredstorecount, confidence)
            VALUES
                (:clusterid, :name, :size, :declaredproductcount, :declaredstorecount, :confidence)
        """),
        clusters.to_dict("records"),
    )
    # Prepare and insert the product memberships into the staging table
    link_frame = members[
        ["clusterid", "supermarketid", "sourceproductid", "productid"]
    ].copy()
    link_frame["productid"] = link_frame["productid"].where(
        link_frame["productid"].notna(), None
    )
    link_records = link_frame.to_dict("records")
    connection.execute(
        text("""
            INSERT INTO staged_productclusterlinks
                (clusterid, supermarketid, sourceproductid, productid)
            VALUES
                (:clusterid, :supermarketid, :sourceproductid, :productid)
        """),
        link_records,
    )

    # Insert new clusters and update clusters that already exist
    connection.execute(text("""
        INSERT INTO productclusters
            (clusterid, name, size, declaredproductcount, declaredstorecount, confidence)
        SELECT clusterid, name, size, declaredproductcount, declaredstorecount, confidence
        FROM staged_productclusters
        ON CONFLICT (clusterid) DO UPDATE SET
            name = EXCLUDED.name,
            size = EXCLUDED.size,
            declaredproductcount = EXCLUDED.declaredproductcount,
            declaredstorecount = EXCLUDED.declaredstorecount,
            confidence = EXCLUDED.confidence
    """))

    # Remove product links that are no longer present in the source snapshot
    connection.execute(text("""
        DELETE FROM productclusterlinks target
        WHERE NOT EXISTS (
            SELECT 1
            FROM staged_productclusterlinks source
            WHERE source.supermarketid = target.supermarketid
              AND source.sourceproductid = target.sourceproductid
        )
    """))
    # Insert new product links and update changed cluster assignments
    connection.execute(text("""
        INSERT INTO productclusterlinks
            (clusterid, supermarketid, sourceproductid, productid)
        SELECT clusterid, supermarketid, sourceproductid, productid
        FROM staged_productclusterlinks
        ON CONFLICT (supermarketid, sourceproductid) DO UPDATE SET
            clusterid = EXCLUDED.clusterid,
            productid = EXCLUDED.productid
    """))
    # Remove clusters that are no longer present after their links are synchronized
    connection.execute(text("""
        DELETE FROM productclusters target
        WHERE NOT EXISTS (
            SELECT 1 FROM staged_productclusters source
            WHERE source.clusterid = target.clusterid
        )
    """))


# Function containing the complete product linking import process
def main() -> None:

    # Find and load database settings from the project .env file
    env_file = find_env_file()
    if env_file:
        load_dotenv(env_file)

    # Check whether all required database environment variables are available
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}")

    # Read and validate the source CSV before opening a database connection
    input_path = Path(os.environ.get("PRODUCT_LINKING_FILE", DEFAULT_INPUT_FILE))
    try:
        clusters, members = load_source(input_path)
    except (FileNotFoundError, ValueError) as error:
        sys.exit(str(error))

    # Create the PostgreSQL database engine
    engine = create_engine(
        f"postgresql+psycopg2://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
        f"@{os.environ['DB_HOST']}:{os.environ.get('DB_PORT', '5432')}/{os.environ['DB_NAME']}"
    )

    # Resolve known products, report data quality and import everything transactionally
    try:
        with engine.connect() as connection:
            members = resolve_products(connection, members)
        print_report(clusters, members)
        with engine.begin() as connection:
            import_links(connection, clusters, members)
    except Exception as error:
        sys.exit(f"Product-link import failed: {error}")

    print(
        f"Imported {len(clusters)} product clusters and {len(members)} memberships successfully."
    )


# Main execution
if __name__ == "__main__":
    main()
