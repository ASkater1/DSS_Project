# Product Link Importer

This importer loads cross-supermarket product clusters from `data/raw/product_linking.csv`.
The input is semicolon-delimited and contains one cluster per row. A supermarket ID cell
may contain several product IDs separated by semicolons.

## Database tables

`ProductClusters` stores the cluster name, package size, declared product/store counts,
and confidence level. `ProductClusterLinks` stores every source membership. Its nullable
`productId` resolves to `Products.productId` when the product currently exists in the
database. The original `sourceProductId` is always retained, so missing products can be
resolved by running the importer again after the product data is updated.

Resolved clusters can be joined to products with:

```sql
SELECT
    pc.clusterId,
    pc.name AS clusterName,
    s.name AS supermarket,
    p.productId,
    p.name AS productName
FROM ProductClusters pc
JOIN ProductClusterLinks pcl ON pcl.clusterId = pc.clusterId
JOIN Supermarkets s ON s.supermarketId = pcl.supermarketId
JOIN Products p ON p.productId = pcl.productId;
```

The importer validates required columns, required values, declared counts, duplicate
clusters, duplicate memberships, and supermarket ownership before changing the database.
All database changes happen in one transaction. The CSV is treated as the complete
snapshot: existing imported clusters and memberships that are absent from a later CSV are
removed, while matching rows are inserted or updated.

## Configuration

Database settings come from the project `.env` file or Docker Compose. The optional
`PRODUCT_LINKING_FILE` environment variable overrides the input path. Its default is:

```text
/project/data/raw/product_linking.csv
```

## Run with Docker

From the project root:

```text
docker compose run --rm --build product_link_importer
```

The PostgreSQL volume is persistent. Do not use `docker compose down -v` unless deleting
all project data is intentional.
