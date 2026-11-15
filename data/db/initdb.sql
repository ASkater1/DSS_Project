-- Any changes to the schema will not be executed as docker only uses this file when it cannot find any existing database.
-- To apply any changes first delete the database.

CREATE TABLE Supermarkets (
  supermarketId INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  marketshare NUMERIC(3,2)
);

-- Shared product categories, filled by code/importer/categories/category_importer.py
CREATE TABLE Categories (
  categoryId SERIAL PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  isFood BOOLEAN NOT NULL,
  description TEXT
);

  CREATE TABLE Products (
    productId TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    isBasketProduct BOOLEAN,
    brand TEXT NOT NULL,
    category TEXT NOT NULL,
    categoryId INTEGER REFERENCES Categories(categoryId),
    description TEXT,
    quantity_value NUMERIC,
    quantity_units TEXT,
    basketcode TEXT
  );

CREATE TABLE SupermarketsProducts (
  supermarketId INTEGER REFERENCES Supermarkets(supermarketId),
  productId TEXT REFERENCES Products(productId),
  date DATE NOT NULL,
  price DECIMAL(10,2),
  PRIMARY KEY (supermarketId, productId, date)
);

CREATE TABLE Municipalities (
  municipalityId SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  population BIGINT,
  year DATE NOT NULL,
  distanceClosestSupermarket INTEGER,
  supermarketsWithin1KM INTEGER,
  supermarketsWithin3KM INTEGER,
  supermarketsWithin5KM INTEGER
);

CREATE TABLE EconomyStatistics (
  date DATE PRIMARY KEY,                    
  CPI DECIMAL(5,2),                         
  CPIYearlyRateOfChange DECIMAL(4,1),
  CPIMonthlyRateOfChange DECIMAL(4,1),
  averageGrossIncome DECIMAL(10,1),         
  averageDisposableIncome DECIMAL(10,1),    
  averageStandardizedIncome DECIMAL(10,1),
  yearlyWageIncrease DECIMAL(4,1),
  foodCPI DECIMAL(5,2),
  foodCPIYearlyRateOfChange DECIMAL(4,1)
);

CREATE TABLE ProductClusters (
  clusterId TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  size TEXT NOT NULL,
  declaredProductCount INTEGER NOT NULL CHECK (declaredProductCount > 0),
  declaredStoreCount SMALLINT NOT NULL CHECK (declaredStoreCount > 0),
  confidence TEXT NOT NULL
);

CREATE TABLE ProductClusterLinks (
  clusterId TEXT NOT NULL REFERENCES ProductClusters(clusterId) ON DELETE CASCADE,
  supermarketId INTEGER NOT NULL REFERENCES Supermarkets(supermarketId),
  sourceProductId TEXT NOT NULL,
  productId TEXT REFERENCES Products(productId) ON DELETE SET NULL,
  PRIMARY KEY (supermarketId, sourceProductId),
  UNIQUE (productId)
);

CREATE INDEX productClusterLinks_clusterId_idx ON ProductClusterLinks(clusterId);

-- Annual market shares of the four supermarkets (%)
CREATE TABLE MarketShares (
    supermarketId INTEGER REFERENCES Supermarkets(supermarketId),
    year INTEGER NOT NULL,
    marketShare NUMERIC(4,1) NOT NULL,
    PRIMARY KEY (supermarketId, year)
);
