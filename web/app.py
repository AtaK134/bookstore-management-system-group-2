"""Bookstore web application (Flask + PostgreSQL).

Roles
-----
admin    : manages books, authors, publishers, categories, customers and all sales,
           and can run the report queries.
customer : browses the catalog, places orders (cart -> checkout) and can cancel
           their own orders.
"""

import os
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps
from itertools import groupby

import bcrypt
import psycopg
from psycopg import errors, sql
from psycopg.rows import dict_row
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from markupsafe import Markup

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "bookstore"),
    "user": os.environ.get("DB_USER", "bookstore_user"),
    "password": os.environ.get("DB_PASSWORD", "bookstore_pass"),
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    """One connection per request. Autocommit is on; multi-statement writes
    use `with db.transaction():` so they commit or roll back as a unit."""
    if "db" not in g:
        g.db = psycopg.connect(**DB_CONFIG, row_factory=dict_row, autocommit=True)
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def fetch_all(query, params=()):
    return get_db().execute(query, params).fetchall()


def fetch_one(query, params=()):
    return get_db().execute(query, params).fetchone()


def db_error_message(exc):
    """Turn a constraint error into a short message for the user."""
    if isinstance(exc, errors.UniqueViolation):
        return "This value already exists (it must be unique)."
    if isinstance(exc, errors.ForeignKeyViolation):
        return "This record is still used by other records, so it cannot be deleted."
    if isinstance(exc, errors.CheckViolation):
        return "A value is not allowed (for example a negative price or stock)."
    if isinstance(exc, errors.NotNullViolation):
        return "A required field is empty."
    return "The database rejected the data: " + (exc.diag.message_primary or str(exc))


# ---------------------------------------------------------------------------
# CSRF protection, current user and template helpers
# ---------------------------------------------------------------------------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.template_global()
def csrf_field():
    return Markup('<input type="hidden" name="_csrf" value="%s">' % csrf_token())


@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400)


@app.context_processor
def inject_globals():
    cart = session.get("cart", {})
    return {"current_user": session.get("user"), "cart_count": sum(cart.values())}


@app.template_filter("money")
def money(value):
    return "₺{:,.2f}".format(value or 0)


def login_required(role=None):
    """Require a logged-in user; optionally a specific role."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please log in first.", "error")
                return redirect(url_for("login", next=request.path))
            if role and user["role"] != role:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        row = fetch_one(
            "SELECT user_id, username, password_hash, role, customer_id "
            "FROM app_user WHERE username = %s", (username,))
        if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            session.clear()
            session["user"] = {
                "user_id": row["user_id"], "username": row["username"],
                "role": row["role"], "customer_id": row["customer_id"],
            }
            flash(f"Welcome, {row['username']}!", "success")
            default = url_for("admin_dashboard") if row["role"] == "admin" else url_for("catalog")
            return redirect(safe_next(request.args.get("next")) or default)
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("catalog"))


@app.route("/register", methods=["GET", "POST"])
def register():
    form = request.form
    if request.method == "POST":
        fields = {k: form.get(k, "").strip() for k in
                  ("first_name", "last_name", "email", "phone", "username")}
        password = form.get("password", "")
        if not all(fields[k] for k in ("first_name", "last_name", "email", "username")):
            flash("Please fill in all required fields.", "error")
        elif len(password) < 8:
            flash("The password must be at least 8 characters.", "error")
        else:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            db = get_db()
            try:
                with db.transaction():
                    customer = db.execute(
                        "INSERT INTO customer (first_name, last_name, email, phone) "
                        "VALUES (%s, %s, %s, %s) RETURNING customer_id",
                        (fields["first_name"], fields["last_name"], fields["email"],
                         fields["phone"] or None)).fetchone()
                    db.execute(
                        "INSERT INTO app_user (username, password_hash, role, customer_id) "
                        "VALUES (%s, %s, 'customer', %s)",
                        (fields["username"], pw_hash, customer["customer_id"]))
            except psycopg.IntegrityError:
                flash("This username or e-mail is already registered.", "error")
            else:
                flash("Account created. You can log in now.", "success")
                return redirect(url_for("login"))
    return render_template("register.html", form=form)


# ---------------------------------------------------------------------------
# Catalog (everyone)
# ---------------------------------------------------------------------------

@app.route("/")
def catalog():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int) or 0
    books = fetch_all(
        """
        SELECT b.book_id, b.isbn, b.title, b.price, b.stock, b.publication_year,
               p.name AS publisher, c.name AS category,
               COALESCE(string_agg(a.first_name || ' ' || a.last_name, ', '
                                   ORDER BY a.last_name), '') AS authors
        FROM book b
        JOIN publisher p ON p.publisher_id = b.publisher_id
        JOIN category  c ON c.category_id  = b.category_id
        LEFT JOIN book_author ba ON ba.book_id  = b.book_id
        LEFT JOIN author      a  ON a.author_id = ba.author_id
        WHERE (%(q)s = '' OR b.title ILIKE %(pattern)s OR b.isbn ILIKE %(pattern)s)
          AND (%(cat)s = 0 OR b.category_id = %(cat)s)
        GROUP BY b.book_id, p.name, c.name
        ORDER BY b.title
        """,
        {"q": q, "pattern": f"%{q}%", "cat": category_id})
    categories = fetch_all("SELECT category_id, name FROM category ORDER BY name")
    return render_template("catalog.html", books=books, categories=categories,
                           q=q, category_id=category_id)


# ---------------------------------------------------------------------------
# Customer: cart, checkout and own orders
# ---------------------------------------------------------------------------

class OutOfStock(Exception):
    pass


@app.route("/cart/add/<int:book_id>", methods=["POST"])
@login_required("customer")
def cart_add(book_id):
    qty = request.form.get("quantity", type=int) or 1
    book = fetch_one("SELECT title, stock FROM book WHERE book_id = %s", (book_id,))
    if not book:
        abort(404)
    cart = session.setdefault("cart", {})
    new_qty = cart.get(str(book_id), 0) + max(qty, 1)
    if new_qty > book["stock"]:
        flash(f"Only {book['stock']} copies of \"{book['title']}\" are in stock.", "error")
    else:
        cart[str(book_id)] = new_qty
        session.modified = True
        flash(f"\"{book['title']}\" added to your cart.", "success")
    return redirect(request.referrer or url_for("catalog"))


@app.route("/cart")
@login_required("customer")
def cart():
    cart_data = session.get("cart", {})
    items, total = [], Decimal("0")
    if cart_data:
        rows = fetch_all("SELECT book_id, title, price, stock FROM book WHERE book_id = ANY(%s)",
                         ([int(k) for k in cart_data],))
        for row in rows:
            qty = cart_data[str(row["book_id"])]
            line = row["price"] * qty
            items.append({**row, "quantity": qty, "line_total": line})
            total += line
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/update", methods=["POST"])
@login_required("customer")
def cart_update():
    cart = session.get("cart", {})
    for key in list(cart):
        qty = request.form.get(f"qty_{key}", type=int)
        if qty is None:
            continue
        if qty <= 0:
            cart.pop(key)
        else:
            cart[key] = qty
    session.modified = True
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/cart/remove/<int:book_id>", methods=["POST"])
@login_required("customer")
def cart_remove(book_id):
    session.get("cart", {}).pop(str(book_id), None)
    session.modified = True
    return redirect(url_for("cart"))


@app.route("/cart/checkout", methods=["POST"])
@login_required("customer")
def checkout():
    cart_data = session.get("cart", {})
    if not cart_data:
        flash("Your cart is empty.", "error")
        return redirect(url_for("cart"))
    db = get_db()
    try:
        with db.transaction():
            sale = db.execute("INSERT INTO sale (customer_id) VALUES (%s) RETURNING sale_id",
                              (session["user"]["customer_id"],)).fetchone()
            for book_id, qty in cart_data.items():
                # Decrease stock only if enough copies exist; the price at this
                # moment is stored in sale_item.unit_price.
                book = db.execute(
                    "UPDATE book SET stock = stock - %s "
                    "WHERE book_id = %s AND stock >= %s RETURNING title, price",
                    (qty, int(book_id), qty)).fetchone()
                if book is None:
                    raise OutOfStock(book_id)
                db.execute(
                    "INSERT INTO sale_item (sale_id, book_id, quantity, unit_price) "
                    "VALUES (%s, %s, %s, %s)",
                    (sale["sale_id"], int(book_id), qty, book["price"]))
    except OutOfStock:
        flash("Not enough stock for one of the books. Please check your cart.", "error")
        return redirect(url_for("cart"))
    session["cart"] = {}
    flash(f"Order #{sale['sale_id']} has been placed. Thank you!", "success")
    return redirect(url_for("my_orders"))


def load_sales(customer_id=None):
    """Sales with their lines, grouped as [{sale_id, sale_date, customer_name, lines, total}]."""
    rows = fetch_all(
        """
        SELECT s.sale_id, s.sale_date, s.customer_id,
               c.first_name || ' ' || c.last_name AS customer_name,
               b.title, si.quantity, si.unit_price,
               si.quantity * si.unit_price AS line_total
        FROM sale s
        JOIN customer  c  ON c.customer_id = s.customer_id
        JOIN sale_item si ON si.sale_id    = s.sale_id
        JOIN book      b  ON b.book_id     = si.book_id
        WHERE (%(cid)s::int IS NULL OR s.customer_id = %(cid)s::int)
        ORDER BY s.sale_date DESC, s.sale_id DESC, b.title
        """,
        {"cid": customer_id})
    sales = []
    for sale_id, lines in groupby(rows, key=lambda r: r["sale_id"]):
        lines = list(lines)
        sales.append({
            "sale_id": sale_id,
            "sale_date": lines[0]["sale_date"],
            "customer_name": lines[0]["customer_name"],
            "lines": lines,
            "total": sum(line["line_total"] for line in lines),
        })
    return sales


def delete_sale(sale_id, customer_id=None):
    """Delete a sale and put its books back in stock. When customer_id is
    given, the sale must belong to that customer."""
    db = get_db()
    with db.transaction():
        sale = db.execute("SELECT customer_id FROM sale WHERE sale_id = %s FOR UPDATE",
                          (sale_id,)).fetchone()
        if not sale or (customer_id is not None and sale["customer_id"] != customer_id):
            return False
        db.execute("UPDATE book b SET stock = b.stock + si.quantity "
                   "FROM sale_item si WHERE si.sale_id = %s AND si.book_id = b.book_id",
                   (sale_id,))
        db.execute("DELETE FROM sale WHERE sale_id = %s", (sale_id,))  # sale_item cascades
    return True


@app.route("/orders")
@login_required("customer")
def my_orders():
    return render_template("orders.html", sales=load_sales(session["user"]["customer_id"]))


@app.route("/orders/<int:sale_id>/cancel", methods=["POST"])
@login_required("customer")
def cancel_order(sale_id):
    if delete_sale(sale_id, session["user"]["customer_id"]):
        flash(f"Order #{sale_id} was cancelled and the books were returned to stock.", "success")
    else:
        abort(404)
    return redirect(url_for("my_orders"))


# ---------------------------------------------------------------------------
# Admin: dashboard
# ---------------------------------------------------------------------------

@app.route("/admin")
@login_required("admin")
def admin_dashboard():
    stats = fetch_one(
        """
        SELECT (SELECT COUNT(*) FROM book)     AS books,
               (SELECT COUNT(*) FROM author)   AS authors,
               (SELECT COUNT(*) FROM customer) AS customers,
               (SELECT COUNT(*) FROM sale)     AS sales,
               (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM sale_item) AS revenue
        """)
    low_stock = fetch_all("SELECT book_id, title, stock FROM book WHERE stock < 5 ORDER BY stock, title")
    return render_template("admin/dashboard.html", stats=stats, low_stock=low_stock)


# ---------------------------------------------------------------------------
# Admin: books (with publisher, category and authors)
# ---------------------------------------------------------------------------

BOOK_FIELDS = ("isbn", "title", "price", "stock", "publication_year", "publisher_id", "category_id")


def book_form_options():
    return {
        "publishers": fetch_all("SELECT publisher_id, name FROM publisher ORDER BY name"),
        "categories": fetch_all("SELECT category_id, name FROM category ORDER BY name"),
        "authors": fetch_all("SELECT author_id, first_name || ' ' || last_name AS name "
                             "FROM author ORDER BY last_name, first_name"),
    }


def parse_book_form(form):
    """Returns (values, author_ids, error)."""
    raw = {k: form.get(k, "").strip() for k in BOOK_FIELDS}
    author_ids = [int(a) for a in form.getlist("author_ids") if a.isdigit()]
    if not raw["isbn"] or not raw["title"]:
        return raw, author_ids, "ISBN and title are required."
    try:
        values = {
            "isbn": raw["isbn"],
            "title": raw["title"],
            "price": Decimal(raw["price"]),
            "stock": int(raw["stock"]),
            "publication_year": int(raw["publication_year"]) if raw["publication_year"] else None,
            "publisher_id": int(raw["publisher_id"]),
            "category_id": int(raw["category_id"]),
        }
    except (ValueError, InvalidOperation):
        return raw, author_ids, "Price, stock, year, publisher and category must be valid values."
    if not author_ids:
        return raw, author_ids, "Select at least one author."
    return values, author_ids, None


def save_book_authors(db, book_id, author_ids):
    db.execute("DELETE FROM book_author WHERE book_id = %s", (book_id,))
    for author_id in author_ids:
        db.execute("INSERT INTO book_author (book_id, author_id) VALUES (%s, %s)", (book_id, author_id))


@app.route("/admin/books")
@login_required("admin")
def admin_books():
    books = fetch_all(
        """
        SELECT b.book_id, b.isbn, b.title, b.price, b.stock,
               p.name AS publisher, c.name AS category,
               COALESCE(string_agg(a.first_name || ' ' || a.last_name, ', '
                                   ORDER BY a.last_name), '') AS authors
        FROM book b
        JOIN publisher p ON p.publisher_id = b.publisher_id
        JOIN category  c ON c.category_id  = b.category_id
        LEFT JOIN book_author ba ON ba.book_id  = b.book_id
        LEFT JOIN author      a  ON a.author_id = ba.author_id
        GROUP BY b.book_id, p.name, c.name
        ORDER BY b.title
        """)
    return render_template("admin/books.html", books=books)


@app.route("/admin/books/new", methods=["GET", "POST"])
@login_required("admin")
def admin_book_new():
    book, selected = {}, []
    if request.method == "POST":
        book, selected, error = parse_book_form(request.form)
        if not error:
            db = get_db()
            try:
                with db.transaction():
                    row = db.execute(
                        "INSERT INTO book (isbn, title, price, stock, publication_year, publisher_id, category_id) "
                        "VALUES (%(isbn)s, %(title)s, %(price)s, %(stock)s, %(publication_year)s, "
                        "%(publisher_id)s, %(category_id)s) RETURNING book_id", book).fetchone()
                    save_book_authors(db, row["book_id"], selected)
            except (psycopg.IntegrityError, psycopg.DataError) as exc:
                error = db_error_message(exc)
            else:
                flash(f"Book \"{book['title']}\" was added.", "success")
                return redirect(url_for("admin_books"))
        flash(error, "error")
    return render_template("admin/book_form.html", book=book, selected=selected,
                           is_new=True, **book_form_options())


@app.route("/admin/books/<int:book_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def admin_book_edit(book_id):
    book = fetch_one("SELECT * FROM book WHERE book_id = %s", (book_id,))
    if not book:
        abort(404)
    selected = [r["author_id"] for r in
                fetch_all("SELECT author_id FROM book_author WHERE book_id = %s", (book_id,))]
    if request.method == "POST":
        values, selected, error = parse_book_form(request.form)
        if not error:
            db = get_db()
            try:
                with db.transaction():
                    db.execute(
                        "UPDATE book SET isbn = %(isbn)s, title = %(title)s, price = %(price)s, "
                        "stock = %(stock)s, publication_year = %(publication_year)s, "
                        "publisher_id = %(publisher_id)s, category_id = %(category_id)s "
                        "WHERE book_id = %(book_id)s", {**values, "book_id": book_id})
                    save_book_authors(db, book_id, selected)
            except (psycopg.IntegrityError, psycopg.DataError) as exc:
                error = db_error_message(exc)
            else:
                flash(f"Book \"{values['title']}\" was updated.", "success")
                return redirect(url_for("admin_books"))
        flash(error, "error")
        book = {**values, "book_id": book_id}
    return render_template("admin/book_form.html", book=book, selected=selected,
                           is_new=False, **book_form_options())


@app.route("/admin/books/<int:book_id>/delete", methods=["POST"])
@login_required("admin")
def admin_book_delete(book_id):
    try:
        get_db().execute("DELETE FROM book WHERE book_id = %s", (book_id,))
    except errors.ForeignKeyViolation:
        flash("This book appears in sales, so it cannot be deleted. "
              "You can set its stock to 0 instead.", "error")
    else:
        flash("Book deleted.", "success")
    return redirect(url_for("admin_books"))


# ---------------------------------------------------------------------------
# Admin: simple tables (authors, publishers, categories, customers)
# ---------------------------------------------------------------------------

# field = (column, label, required, input type)
ENTITIES = {
    "authors": {
        "table": "author", "pk": "author_id", "label": "Author", "plural": "Authors",
        "order": "last_name, first_name",
        "fields": [("first_name", "First name", True, "text"),
                   ("last_name", "Last name", True, "text"),
                   ("nationality", "Nationality", False, "text")],
    },
    "publishers": {
        "table": "publisher", "pk": "publisher_id", "label": "Publisher", "plural": "Publishers",
        "order": "name",
        "fields": [("name", "Name", True, "text"),
                   ("city", "City", False, "text"),
                   ("phone", "Phone", False, "text")],
    },
    "categories": {
        "table": "category", "pk": "category_id", "label": "Category", "plural": "Categories",
        "order": "name",
        "fields": [("name", "Name", True, "text")],
    },
    "customers": {
        "table": "customer", "pk": "customer_id", "label": "Customer", "plural": "Customers",
        "order": "last_name, first_name",
        "fields": [("first_name", "First name", True, "text"),
                   ("last_name", "Last name", True, "text"),
                   ("email", "E-mail", True, "email"),
                   ("phone", "Phone", False, "text")],
    },
}
ENTITY_NAMES = "any(" + ", ".join(ENTITIES) + ")"


def entity_or_404(entity):
    cfg = ENTITIES.get(entity)
    if not cfg:
        abort(404)
    return cfg


def read_entity_form(cfg, form):
    values = {column: form.get(column, "").strip() or None for column, *_ in cfg["fields"]}
    missing = [label for column, label, required, _type in cfg["fields"]
               if required and not values[column]]
    return values, (f"{', '.join(missing)} is required." if missing else None)


@app.route(f"/admin/<{ENTITY_NAMES}:entity>")
@login_required("admin")
def admin_entity_list(entity):
    cfg = entity_or_404(entity)
    columns = [f[0] for f in cfg["fields"]]
    query = sql.SQL("SELECT {pk} AS id, {cols} FROM {table} ORDER BY {order}").format(
        pk=sql.Identifier(cfg["pk"]),
        cols=sql.SQL(", ").join(map(sql.Identifier, columns)),
        table=sql.Identifier(cfg["table"]),
        order=sql.SQL(cfg["order"]))
    return render_template("admin/entity_list.html", entity=entity, cfg=cfg, rows=fetch_all(query))


@app.route(f"/admin/<{ENTITY_NAMES}:entity>/new", methods=["GET", "POST"])
@login_required("admin")
def admin_entity_new(entity):
    cfg = entity_or_404(entity)
    values = {}
    if request.method == "POST":
        values, error = read_entity_form(cfg, request.form)
        if not error:
            query = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
                table=sql.Identifier(cfg["table"]),
                cols=sql.SQL(", ").join(map(sql.Identifier, values)),
                vals=sql.SQL(", ").join(sql.Placeholder() * len(values)))
            try:
                get_db().execute(query, list(values.values()))
            except (psycopg.IntegrityError, psycopg.DataError) as exc:
                error = db_error_message(exc)
            else:
                flash(f"{cfg['label']} added.", "success")
                return redirect(url_for("admin_entity_list", entity=entity))
        flash(error, "error")
    return render_template("admin/entity_form.html", entity=entity, cfg=cfg, values=values, is_new=True)


@app.route(f"/admin/<{ENTITY_NAMES}:entity>/<int:item_id>/edit", methods=["GET", "POST"])
@login_required("admin")
def admin_entity_edit(entity, item_id):
    cfg = entity_or_404(entity)
    query = sql.SQL("SELECT * FROM {table} WHERE {pk} = %s").format(
        table=sql.Identifier(cfg["table"]), pk=sql.Identifier(cfg["pk"]))
    values = fetch_one(query, (item_id,))
    if not values:
        abort(404)
    if request.method == "POST":
        values, error = read_entity_form(cfg, request.form)
        if not error:
            update = sql.SQL("UPDATE {table} SET {assignments} WHERE {pk} = %s").format(
                table=sql.Identifier(cfg["table"]),
                assignments=sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(c)) for c in values),
                pk=sql.Identifier(cfg["pk"]))
            try:
                get_db().execute(update, [*values.values(), item_id])
            except (psycopg.IntegrityError, psycopg.DataError) as exc:
                error = db_error_message(exc)
            else:
                flash(f"{cfg['label']} updated.", "success")
                return redirect(url_for("admin_entity_list", entity=entity))
        flash(error, "error")
    return render_template("admin/entity_form.html", entity=entity, cfg=cfg, values=values,
                           is_new=False, item_id=item_id)


@app.route(f"/admin/<{ENTITY_NAMES}:entity>/<int:item_id>/delete", methods=["POST"])
@login_required("admin")
def admin_entity_delete(entity, item_id):
    cfg = entity_or_404(entity)
    query = sql.SQL("DELETE FROM {table} WHERE {pk} = %s").format(
        table=sql.Identifier(cfg["table"]), pk=sql.Identifier(cfg["pk"]))
    try:
        get_db().execute(query, (item_id,))
    except psycopg.IntegrityError as exc:
        flash(db_error_message(exc), "error")
    else:
        flash(f"{cfg['label']} deleted.", "success")
    return redirect(url_for("admin_entity_list", entity=entity))


# ---------------------------------------------------------------------------
# Admin: sales and reports
# ---------------------------------------------------------------------------

@app.route("/admin/sales")
@login_required("admin")
def admin_sales():
    return render_template("admin/sales.html", sales=load_sales(), show_customer=True)


@app.route("/admin/sales/<int:sale_id>/delete", methods=["POST"])
@login_required("admin")
def admin_sale_delete(sale_id):
    if delete_sale(sale_id):
        flash(f"Sale #{sale_id} deleted and its books returned to stock.", "success")
    else:
        flash("Sale not found.", "error")
    return redirect(url_for("admin_sales"))


# The three report queries from queries.sql
REPORTS = [
    ("Query 1 - JOIN: sales receipts", """\
SELECT s.sale_id, s.sale_date,
       c.first_name || ' ' || c.last_name AS customer_name,
       b.title AS book_title, si.quantity, si.unit_price,
       si.quantity * si.unit_price AS line_total
FROM sale s
JOIN customer  c  ON c.customer_id = s.customer_id
JOIN sale_item si ON si.sale_id    = s.sale_id
JOIN book      b  ON b.book_id     = si.book_id
ORDER BY s.sale_id, b.title;"""),
    ("Query 2 - GROUP BY + ORDER BY: copies sold per book", """\
SELECT b.book_id, b.title,
       COALESCE(SUM(si.quantity), 0) AS total_sold
FROM book b
LEFT JOIN sale_item si ON si.book_id = b.book_id
GROUP BY b.book_id, b.title
ORDER BY total_sold DESC, b.title;"""),
    ("Query 3 - Subquery: books priced above the average", """\
SELECT b.title, b.price,
       ROUND((SELECT AVG(price) FROM book), 2) AS average_price
FROM book b
WHERE b.price > (SELECT AVG(price) FROM book)
ORDER BY b.price DESC;"""),
]


@app.route("/admin/reports")
@login_required("admin")
def admin_reports():
    results = []
    for title, query in REPORTS:
        cur = get_db().execute(query)
        results.append({"title": title, "sql": query,
                        "columns": [d.name for d in cur.description], "rows": cur.fetchall()})
    return render_template("admin/reports.html", results=results)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

@app.errorhandler(400)
def bad_request(_e):
    return render_template("error.html", code=400,
                           message="The form expired or is invalid. Please try again."), 400


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403,
                           message="You do not have permission to open this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="Page not found."), 404


if __name__ == "__main__":
    app.run(debug=True, port=8000)
