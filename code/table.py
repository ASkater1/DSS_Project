import pandas as pd
from pathlib import Path
import sys

SOURCE = Path(r"data/raw")
OUTPUT = Path(__file__).with_name("data/processed")
FILES = ("Jumbo.csv", "AH.csv", "Lidl.csv", "Plus.csv")

def organize(source_file, output_folder):
    output_folder.mkdir(parents=True, exist_ok=True)
    columns = pd.read_csv(source_file, nrows=0).columns.tolist()
    date_columns = [column for column in columns if column.startswith("D")]
    info_columns = [column for column in columns if not column.startswith("D")]
    first_chunk = True

    for data in pd.read_csv(source_file, dtype=str, keep_default_na=False, chunksize=250):
        data[info_columns].to_csv(
            output_folder / "products.csv",
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
            encoding="utf-8-sig",
        )

        prices = data.melt(
            id_vars="prod_id",
            value_vars=date_columns,
            var_name="date",
            value_name="price",
        )
        prices = prices[prices["price"] != ""]
        prices["date"] = prices["date"].str[1:].str.replace("_", "-", regex=False)
        prices.to_csv(
            output_folder / "prices.csv",
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
            encoding="utf-8-sig",
        )
        first_chunk = False


def main():
    source_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else SOURCE
    output_folder = Path(sys.argv[2]) if len(sys.argv) > 2 else OUTPUT

    for filename in FILES:
        source_file = source_folder / filename
        organize(source_file, output_folder / source_file.stem)
        print(f"Created {output_folder / source_file.stem}")


main()