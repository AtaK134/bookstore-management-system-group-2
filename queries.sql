-- =========================================================
-- Bookstore Database - Report Queries
-- =========================================================

-- ---------------------------------------------------------
-- Query 1 (JOIN)
-- Sales receipt: customer name, book title, quantity and line total.
-- Follows sale -> sale_item -> book and sale -> customer.
-- ---------------------------------------------------------
SELECT
    s.sale_id,
    s.sale_date,
    c.first_name || ' ' || c.last_name   AS customer_name,
    b.title                              AS book_title,
    si.quantity,
    si.unit_price,
    si.quantity * si.unit_price          AS line_total
FROM sale s
JOIN customer  c  ON c.customer_id = s.customer_id
JOIN sale_item si ON si.sale_id    = s.sale_id
JOIN book      b  ON b.book_id     = si.book_id
ORDER BY s.sale_id, b.title;


-- ---------------------------------------------------------
-- Query 2 (GROUP BY + ORDER BY)
-- Total number of copies sold for each book, best seller first.
-- LEFT JOIN keeps books that were never sold (total_sold = 0).
-- ---------------------------------------------------------
SELECT
    b.book_id,
    b.title,
    COALESCE(SUM(si.quantity), 0) AS total_sold
FROM book b
LEFT JOIN sale_item si ON si.book_id = b.book_id
GROUP BY b.book_id, b.title
ORDER BY total_sold DESC, b.title;


-- ---------------------------------------------------------
-- Query 3 (Subquery)
-- Books whose current price is higher than the average price of all books.
-- ---------------------------------------------------------
SELECT
    b.title,
    b.price,
    ROUND((SELECT AVG(price) FROM book), 2) AS average_price
FROM book b
WHERE b.price > (SELECT AVG(price) FROM book)
ORDER BY b.price DESC;
