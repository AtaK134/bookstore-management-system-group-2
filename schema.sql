-- =========================================================
-- Kitapçı Veritabanı - Şema (PostgreSQL)
-- =========================================================
-- Tekrar çalıştırılabilir olması için önce tablolar,
-- bağımlılık sırasının tersine silinir.

SET client_min_messages = warning;  -- "tablo yok, atlanıyor" uyarılarını gizle

DROP TABLE IF EXISTS sale_item;
DROP TABLE IF EXISTS sale;
DROP TABLE IF EXISTS book_author;
DROP TABLE IF EXISTS book;
DROP TABLE IF EXISTS customer;
DROP TABLE IF EXISTS author;
DROP TABLE IF EXISTS category;
DROP TABLE IF EXISTS publisher;

-- ---------------------------------------------------------
-- 1) Bağımsız (ana) tablolar
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
-- 2) Ana tablolara bağlanan tablolar
-- ---------------------------------------------------------

CREATE TABLE book (
    book_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    isbn             VARCHAR(17)   NOT NULL UNIQUE,
    title            VARCHAR(200)  NOT NULL,
    price            NUMERIC(10,2) NOT NULL CHECK (price >= 0),   -- güncel fiyat
    stock            INTEGER       NOT NULL DEFAULT 0 CHECK (stock >= 0),
    publication_year SMALLINT,
    publisher_id     INTEGER NOT NULL REFERENCES publisher (publisher_id),
    category_id      INTEGER NOT NULL REFERENCES category (category_id)
);

-- Kitap <-> Yazar (çoka-çok) ara tablosu
CREATE TABLE book_author (
    book_id    INTEGER NOT NULL REFERENCES book (book_id)     ON DELETE CASCADE,
    author_id  INTEGER NOT NULL REFERENCES author (author_id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, author_id)
);

-- Satış başlığı (fiş)
CREATE TABLE sale (
    sale_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sale_date    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    customer_id  INTEGER   NOT NULL REFERENCES customer (customer_id)
);

-- Satış satırları: bir satışta birden fazla kitap olabilir
CREATE TABLE sale_item (
    sale_id     INTEGER       NOT NULL REFERENCES sale (sale_id) ON DELETE CASCADE,
    book_id     INTEGER       NOT NULL REFERENCES book (book_id),
    quantity    INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price  NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),  -- satış anındaki fiyat
    PRIMARY KEY (sale_id, book_id)
);
