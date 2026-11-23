-- =========================================================
-- Bookstore Database - Sample Data
-- =========================================================
-- Run after schema.sql.
-- Test scenarios covered:
--   * Multi-author book     : "Database System Concepts" (3 authors),
--                             "The Pragmatic Programmer" (2 authors)
--   * Sale with many books  : sales 1, 2, 3 and 5
--   * Book never sold       : "Kar" (book_id = 8)
--   * Sale price != current : sales 2 and 4
--
-- Web application test accounts (passwords are bcrypt-hashed below):
--   admin  / Admin123!     -> role admin
--   ayse   / Customer123!  -> role customer (customer 1)
--   mehmet / Customer123!  -> role customer (customer 2)
--   zeynep / Customer123!  -> role customer (customer 3)

SET client_encoding = 'UTF8';

-- Empty all tables and restart the identity counters at 1 (re-runnable)
TRUNCATE app_user, sale_item, sale, book_author, book, customer, author, category, publisher
    RESTART IDENTITY CASCADE;

-- ---------------------------------------------------------
-- publisher (id 1-6)
-- ---------------------------------------------------------
INSERT INTO publisher (name, city, phone) VALUES
    ('Yapı Kredi Yayınları',  'Istanbul', '0212 252 47 00'),  -- 1
    ('İletişim Yayınları',    'Istanbul', '0212 516 22 60'),  -- 2
    ('İthaki Yayınları',      'Istanbul', '0216 348 36 97'),  -- 3
    ('Kolektif Kitap',        'Istanbul', '0212 243 01 77'),  -- 4
    ('McGraw-Hill Education', 'New York', '+1 800 338 3987'), -- 5
    ('Addison-Wesley',        'Boston',   '+1 617 848 6000'); -- 6

-- ---------------------------------------------------------
-- category (id 1-4)
-- ---------------------------------------------------------
INSERT INTO category (name) VALUES
    ('Novel'),             -- 1
    ('Science Fiction'),   -- 2
    ('History'),           -- 3
    ('Computer Science');  -- 4

-- ---------------------------------------------------------
-- author (id 1-10)
-- ---------------------------------------------------------
INSERT INTO author (first_name, last_name, nationality) VALUES
    ('Sabahattin', 'Ali',          'Turkish'),   -- 1
    ('Oğuz',       'Atay',         'Turkish'),   -- 2
    ('Orhan',      'Pamuk',        'Turkish'),   -- 3
    ('Isaac',      'Asimov',       'American'),  -- 4
    ('Yuval Noah', 'Harari',       'Israeli'),   -- 5
    ('Abraham',    'Silberschatz', 'American'),  -- 6
    ('Henry F.',   'Korth',        'American'),  -- 7
    ('S.',         'Sudarshan',    'Indian'),    -- 8
    ('Andrew',     'Hunt',         'American'),  -- 9
    ('David',      'Thomas',       'British');   -- 10

-- ---------------------------------------------------------
-- customer (id 1-4)
-- ---------------------------------------------------------
INSERT INTO customer (first_name, last_name, email, phone, registered_at) VALUES
    ('Ayşe',   'Yılmaz', 'ayse.yilmaz@example.com',  '0532 111 22 33', '2026-09-01'), -- 1
    ('Mehmet', 'Kaya',   'mehmet.kaya@example.com',  '0533 222 33 44', '2026-09-05'), -- 2
    ('Zeynep', 'Demir',  'zeynep.demir@example.com', '0534 333 44 55', '2026-09-12'), -- 3
    ('Can',    'Öztürk', 'can.ozturk@example.com',   '0535 444 55 66', '2026-09-20'); -- 4

-- ---------------------------------------------------------
-- book (id 1-8)
-- ---------------------------------------------------------
INSERT INTO book (isbn, title, price, stock, publication_year, publisher_id, category_id) VALUES
    ('978-975-08-0607-2', 'Kürk Mantolu Madonna',             85.00, 40, 1943, 1, 1), -- 1
    ('978-975-470-001-6', 'Tutunamayanlar',                  360.00, 15, 1972, 2, 1), -- 2
    ('978-975-08-1515-9', 'Masumiyet Müzesi',                290.00, 12, 2008, 1, 1), -- 3
    ('978-605-375-302-8', 'Vakıf',                           180.00, 20, 1951, 3, 2), -- 4
    ('978-605-5029-33-2', 'Sapiens: Hayvanlardan Tanrılara', 260.00, 25, 2011, 4, 3), -- 5
    ('978-0-07-802215-9', 'Database System Concepts',        780.00,  5, 2019, 5, 4), -- 6
    ('978-0-13-595705-9', 'The Pragmatic Programmer',        620.00,  8, 2019, 6, 4), -- 7
    ('978-975-08-0428-3', 'Kar',                             275.00, 10, 2002, 1, 1); -- 8 (never sold)

-- ---------------------------------------------------------
-- book_author
-- ---------------------------------------------------------
INSERT INTO book_author (book_id, author_id) VALUES
    (1, 1),                   -- Kürk Mantolu Madonna     - Sabahattin Ali
    (2, 2),                   -- Tutunamayanlar           - Oğuz Atay
    (3, 3),                   -- Masumiyet Müzesi         - Orhan Pamuk
    (4, 4),                   -- Vakıf                    - Isaac Asimov
    (5, 5),                   -- Sapiens                  - Yuval Noah Harari
    (6, 6), (6, 7), (6, 8),   -- Database System Concepts - 3 authors
    (7, 9), (7, 10),          -- The Pragmatic Programmer - 2 authors
    (8, 3);                   -- Kar                      - Orhan Pamuk

-- ---------------------------------------------------------
-- sale (id 1-5)
-- ---------------------------------------------------------
INSERT INTO sale (sale_date, customer_id) VALUES
    ('2026-10-01 10:15', 1),  -- 1  Ayşe
    ('2026-10-03 14:40', 2),  -- 2  Mehmet
    ('2026-10-05 11:05', 3),  -- 3  Zeynep
    ('2026-10-10 16:30', 1),  -- 4  Ayşe (second purchase)
    ('2026-10-12 18:20', 4);  -- 5  Can

-- ---------------------------------------------------------
-- sale_item
-- ---------------------------------------------------------
INSERT INTO sale_item (sale_id, book_id, quantity, unit_price) VALUES
    (1, 1, 2,  85.00),   -- Sale 1: two different books
    (1, 5, 1, 260.00),
    (2, 6, 1, 750.00),   -- Sale 2: discounted (current price is 780)
    (2, 7, 1, 620.00),
    (3, 1, 1,  85.00),   -- Sale 3: two different books
    (3, 4, 2, 180.00),
    (4, 2, 1, 340.00),   -- Sale 4: single book at an older price (current price is 360)
    (5, 3, 1, 290.00),   -- Sale 5: two different books
    (5, 1, 3,  85.00);

-- ---------------------------------------------------------
-- app_user (id 1-4) - passwords hashed with bcrypt via pgcrypto
-- ---------------------------------------------------------
INSERT INTO app_user (username, password_hash, role, customer_id) VALUES
    ('admin',  crypt('Admin123!',    gen_salt('bf', 10)), 'admin',    NULL), -- 1
    ('ayse',   crypt('Customer123!', gen_salt('bf', 10)), 'customer', 1),    -- 2
    ('mehmet', crypt('Customer123!', gen_salt('bf', 10)), 'customer', 2),    -- 3
    ('zeynep', crypt('Customer123!', gen_salt('bf', 10)), 'customer', 3);    -- 4
