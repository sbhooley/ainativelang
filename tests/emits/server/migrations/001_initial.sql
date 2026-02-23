-- AINL SQL migration from D types
-- dialect: postgres

CREATE TABLE IF NOT EXISTS Product (
  id INTEGER,
  name VARCHAR(255),
  price DOUBLE PRECISION,
  sku VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS Order (
  id INTEGER,
  uid INTEGER,
  total DOUBLE PRECISION,
  status VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Customer (
  id INTEGER,
  email VARCHAR(255),
  name VARCHAR(255)
);
