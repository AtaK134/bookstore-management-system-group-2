# Bookstore Management System

CMPE341 Database Design and Management project. A PostgreSQL database for a bookstore
(publishers, categories, authors, books, customers, sales) with a Flask web application
that has login, two roles and insert / update / delete operations.

## Quick start

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Docker Engine with the compose plugin).

```bash
git clone <repository-url>
cd <repository-folder>
docker compose up
```

The first start builds the web image and creates the database from `schema.sql` and
`data.sql`. When the logs show `Listening at: http://0.0.0.0:8000`, open:

**http://localhost:8080**

No `.env` file is needed; all settings have defaults (see `.env.example` to change them).

## Test accounts

| Role     | Username | Password       | Linked customer |
|----------|----------|----------------|-----------------|
| admin    | `admin`  | `Admin123!`    | -               |
| customer | `ayse`   | `Customer123!` | Ayşe Yılmaz     |
| customer | `mehmet` | `Customer123!` | Mehmet Kaya     |
| customer | `zeynep` | `Customer123!` | Zeynep Demir    |

New customer accounts can be created from the **Register** page.
Passwords are stored as bcrypt hashes in the `app_user` table, never as plain text.

## Roles and permissions

| Action                                                    | Guest | Customer | Admin |
|-----------------------------------------------------------|:-----:|:--------:|:-----:|
| Browse and search the book catalog                         |  ✓    |    ✓     |   ✓   |
| Register a customer account                                |  ✓    |          |       |
| Add books to the cart and place an order (insert)          |       |    ✓     |       |
| See own orders, cancel own order (delete)                  |       |    ✓     |       |
| Add / edit / delete books, authors, publishers, categories |       |          |   ✓   |
| Add / edit / delete customers                              |       |          |   ✓   |
| See and delete all sales                                   |       |          |   ✓   |
| Dashboard and report queries                               |       |          |   ✓   |

Placing an order inserts one `sale` row and one `sale_item` row per book, stores the
price at the moment of sale and decreases the stock in a single transaction. Cancelling
or deleting a sale puts the books back in stock.

## Database

| Table         | Description                                   | Keys |
|---------------|-----------------------------------------------|------|
| `publisher`   | Publishers                                    | PK `publisher_id` |
| `category`    | Book categories                               | PK `category_id` |
| `author`      | Authors                                       | PK `author_id` |
| `customer`    | Registered customers                          | PK `customer_id` |
| `book`        | ISBN, title, current price, stock             | PK `book_id`, FK `publisher_id`, `category_id` |
| `book_author` | Which author wrote which book (M:N)           | PK (`book_id`, `author_id`), both FK |
| `sale`        | Sale date and customer                        | PK `sale_id`, FK `customer_id` |
| `sale_item`   | Book, quantity and price at the time of sale  | PK (`sale_id`, `book_id`), both FK |
| `app_user`    | Web app accounts (username, bcrypt hash, role)| PK `user_id`, FK `customer_id` |

Files:

- `schema.sql` - tables and constraints (`UNIQUE` ISBN, `CHECK (stock >= 0)`, `CHECK (quantity > 0)`, ...)
- `data.sql` - sample data (at least 3 rows per table, a multi-author book, a sale with several books, a book that was never sold)
- `queries.sql` - the three report queries (JOIN, GROUP BY + ORDER BY, subquery). They can also be run from the **Reports** page as admin.

### Connecting with DBeaver

While the containers are running: New Connection → PostgreSQL

| Field    | Value |
|----------|-------|
| Host     | `localhost` |
| Port     | `5434` |
| Database | `bookstore` |
| Username | `bookstore_user` |
| Password | `bookstore_pass` (or `DB_PASSWORD` from your `.env`) |

## Useful commands

```bash
docker compose up -d        # start in the background
docker compose ps           # status
docker compose logs -f web  # web app logs
docker compose down         # stop (data is kept)
docker compose down -v      # stop and DELETE the data; next start reloads schema.sql + data.sql
```

`schema.sql` and `data.sql` only run when the database volume is empty. After changing
them, run `docker compose down -v` and then `docker compose up` again.

## Deployment (Linux VM)

1. Create an Ubuntu virtual machine at a cloud provider (Azure for Students, Oracle Cloud
   Free Tier, AWS Free Tier, ...) and note its public IP address.
2. Allow inbound TCP port **80** (and 22 for SSH) in the provider's firewall / network security group.
3. Connect and install Docker:
   ```bash
   ssh <user>@<server-ip>
   curl -fsSL https://get.docker.com | sudo sh
   ```
4. Clone the project and create a `.env` with production values:
   ```bash
   git clone <repository-url> bookstore && cd bookstore
   cat > .env <<EOF
   WEB_PORT=80
   DB_PASSWORD=$(openssl rand -hex 16)
   SECRET_KEY=$(openssl rand -hex 32)
   EOF
   sudo docker compose up -d --build
   ```
5. Open `http://<server-ip>` in a browser. Change the test passwords on a public server.

## Project structure

```
├── docker-compose.yml   # db + web services
├── schema.sql           # tables and constraints
├── data.sql             # sample data and test accounts
├── queries.sql          # report queries
├── .env.example         # optional settings
├── setup.ps1            # optional: install into a local PostgreSQL without Docker
├── create_db.sql        # used by setup.ps1
└── web/
    ├── Dockerfile
    ├── requirements.txt
    ├── app.py           # Flask application
    ├── templates/       # HTML pages
    └── static/style.css
```
