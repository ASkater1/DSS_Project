-- Any changes to the schema will not be executed as docker only uses this file when it cannot find any existing database.
-- To apply any changes first delete the database.

CREATE TABLE Supermarkets (
  supermarketId SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  marketshare NUMERIC(3,2)
);

CREATE TABLE Products (
  productId BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  isBasketProduct BOOLEAN,
  brand TEXT NOT NULL,
  category TEXT NOT NULL,
  weight NUMERIC(10,2),
  unit NUMERIC(10,2),
  description TEXT
);

CREATE TABLE SupermarketsProducts (
  supermarketId SERIAL REFERENCES Supermarkets(supermarketId),
  productId BIGSERIAL REFERENCES Products(productId),
  date DATE NOT NULL,
  price DECIMAL(10,2),
  PRIMARY KEY (supermarketId, productId)
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
  incomeParticularHousehold DECIMAL(10,1),
  averageDisposableIncome DECIMAL(10,1),
  averageStandardizedIncome DECIMAL(10,1),
  yearlyWageIncrease DECIMAL(4,1)
);