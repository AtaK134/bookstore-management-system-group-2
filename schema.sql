-- =========================================================
-- Bookstore Database - Schema (PostgreSQL)
-- =========================================================
-- The script can be re-run: existing tables are dropped first,
-- in reverse dependency order.

SET client_min_messages = warning;  -- hide "table does not exist, skipping" notices

-- pgcrypto provides crypt()/gen_salt() used to bcrypt-hash the seed passwords
CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS app_user;
DROP TABLE IF EXISTS sale_item;
DROP TABLE IF EXISTS sale;
DROP TABLE IF EXISTS book_author;
DROP TABLE IF EXISTS book;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS author;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS publisher;

-- ---------------------------------------------------------
-- 1) Independent (parent) tables
-- ---------------------------------------------------------

CREATE TABLE publisher (
    publisher_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(100) NOT NULL UNIQUE,
    city          VARCHAR(50),
    phone         VARCHAR(20)
);

CREATE TABLE category (
    category_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE author (
    author_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name    VARCHAR(50) NOT NULL,
    last_name     VARCHAR(50) NOT NULL,
    nationality   VARCHAR(50)
);

CREATE TABLE customer (
    customer_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    phone         VARCHAR(20),
    registered_at DATE NOT NULL DEFAULT CURRENT_DATE
);

-- ---------------------------------------------------------
-- 2) Tables that reference the parent tables
-- ---------------------------------------------------------

CREATE TABLE book (
    book_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn             VARCHAR(17)   NOT NULL UNIQUE,
    title            VARCHAR(200)  NOT NULL,
    price            NUMERIC(10,2) NOT NULL CHECK (price >= 0),   -- current price
    stock            INTEGER       NOT NULL DEFAULT 0 CHECK (stock >= 0),
    publication_year SMALLINT,
    publisher_id     INTEGER NOT NULL REFERENCES publisher (publisher_id),
    category_id      INTEGER NOT NULL REFERENCES category (category_id)
);

-- Book <-> Author (many-to-many) junction table
CREATE TABLE book_author (
    book_id    INTEGER NOT NULL REFERENCES book (book_id)     ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES author (author_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

-- Sale header (receipt)
CREATE TABLE sale (
    sale_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    customer_id  INTEGER   NOT NULL REFERENCES customer (customer_id)
);

-- Sale lines: one sale can contain several different books
CREATE TABLE sale_item (
    sale_id     INTEGER       NOT NULL REFERENCES sale (sale_id) ON DELETE CASCADE,
    book_id     INTEGER       NOT NULL REFERENCES book (book_id),
    quantity    INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),  -- price at the time of sale
    PRIMARY KEY (sale_id, book_id)
);

-- Web application accounts.
-- role = 'admin'    : manages the catalog, customers and all sales
-- role = 'customer' : browses books, places and cancels own orders
-- A customer account is linked to exactly one customer row; an admin has none.
CREATE TABLE app_user (
    user_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(100) NOT NULL,                 -- bcrypt hash, never plain text
    role           VARCHAR(20)  NOT NULL CHECK (role IN ('admin', 'customer')),
    customer_id    INTEGER UNIQUE REFERENCES customer (customer_id) ON DELETE CASCADE,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (role = 'admin'    AND customer_id IS NULL) OR
        (role = 'customer' AND customer_id IS NOT NULL)
    )
);
