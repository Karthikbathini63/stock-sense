# StockSense - Inventory Management System

StockSense is a centralized web-based inventory management system built with Django and Bootstrap.
It tracks products, categories, warehouses, storage locations and every stock movement (receipts,
deliveries, transfers and adjustments) with a full, stats-driven dashboard and product-aware stock ledger.

## Features

- **Authentication** - registration with email OTP verification (5-minute expiry + 45s resend cooldown), secure login (username, email or case-insensitive username), session logout.
- **Dashboard** - live totals calculated from the database: total stock units, products, categories, warehouses, locations, low-stock and out-of-stock records, delivered units and recent activity.
- **Product management** - create, edit, delete, case-insensitive duplicate-SKU protection, search by name / SKU / category, pagination.
- **Stock receipts** - increase stock at a product + location, with automatic stock-record creation.
- **Stock deliveries** - decrease stock and block insufficient stock before any write.
- **Stock transfers** - move stock between locations atomically, log both `TRANSFER_OUT` and `TRANSFER_IN` legs.
- **Stock adjustments** - correct quantities with positive/negative adjustments; negative stock is impossible by design.
- **Stock ledger** - full, timestamped movement history with product, location, reference and acting-user details.
- **Data integrity** - database-level guarantees: one stock record per product+location, quantity can never go negative, unique location codes per warehouse.
- **Atomic operations** - stock movements run inside `transaction.atomic()` with row locking so failed operations never leave partial writes.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, Django 5.2 |
| Frontend | HTML5, CSS3, Bootstrap 5, Chart.js, JS |
| Database | SQLite (development), PostgreSQL (production-ready via `DATABASE_URL`) |
| Email | Gmail SMTP with App Password |
| Production server | Gunicorn + WhiteNoise (static files) |
| Hosting target | Render / Railway (see Deployment) |

## Project Architecture

```
StockSense/
|-- config/            # Django project: settings, urls, wsgi/asgi
|-- inventory/         # The app: models, views, urls, tests, migrations
|   |-- models.py      # Category, Warehouse, Location, Product, Stock, StockTransaction
|   |-- views.py       # All application views (auth + inventory modules)
|   |-- tests.py       # Automated test suite (44 tests)
|   `-- migrations/
|-- templates/         # HTML templates (dashboard, products, stock ops, ledger, auth)
|-- static/            # Local static assets
|-- manage.py
|-- requirements.txt
|-- Procfile / build.sh # Deployment entrypoints
`-- .env.example       # Environment variable template
```

### Database Model Overview

- **Category** - product groups (unique name, PROTECT on delete).
- **Warehouse** - physical stores (unique name + unique code).
- **Location** - racks/bins inside a warehouse (unique code *per warehouse*).
- **Product** - SKU (unique, case-insensitive), unit of measure, reorder level.
- **Stock** - current quantity per product + location (unique pair, quantity >= 0 enforced in the database).
- **StockTransaction** - immutable movement history: `RECEIPT`, `DELIVERY`, `TRANSFER_IN`, `TRANSFER_OUT`, `ADJUSTMENT`.

## Environment Variables

Copy `.env.example` to `.env` and fill in the values. `.env` is git-ignored and never committed.

| Variable | Purpose |
|---|---|
| `EMAIL_HOST_USER` | Gmail address used to send OTP mails |
| `EMAIL_HOST_PASSWORD` | **Gmail App Password** (16 characters, no spaces) - never log this |
| `DJANGO_SECRET_KEY` | Production secret; leave unset in dev to use the dev fallback |
| `DJANGO_DEBUG` | `True` locally, `False` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated production hosts |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | e.g. `https://stocksense.onrender.com` |
| `DJANGO_HTTPS_ONLY` | `True` behind HTTPS to force secure cookies and POST to HTTPS |
| `DATABASE_URL` | Postgres connection string; absent -> local SQLite |

## Installation (Windows PowerShell)

```powershell
# 1. Clone and enter the project
git clone https://github.com/Karthikbathini63/stock-sense.git
cd stock-sense

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
Copy-Item .env.example .env
# Edit .env with your Gmail App Password (Google Account -> Security,
# enable 2-Step Verification -> App Passwords)
notepad .env

# 5. Apply migrations
python manage.py migrate

# 6. (Optional) create an admin account
python manage.py createsuperuser

# 7. Start the development server
python manage.py runserver
```

Open http://127.0.0.1:8000/ - you will be redirected to the login page.
Create an account via `/register/` (the OTP email is sent to the address you enter).

## Running the Tests

```powershell
python manage.py test inventory
```

The suite covers registration + OTP (including expiry, reuse and cooldown), login/logout,
route protection, product CRUD with duplicate-SKU validation, receipts, deliveries,
insufficient-stock rejection, transfers (same-location and atomicity), adjustments,
dashboard calculations and transaction-history consistency - all on an isolated test database.

## Deployment (Render)

1. Push this repository to GitHub (`.env` and `db.sqlite3` are git-ignored).
2. Create a free Render **PostgreSQL** database; copy its *External Database URL*.
3. Create a **Web Service** from the repo:
   - **Build command:** `bash build.sh`
   - **Start command:** `gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 3`
   - **Worker** is pre-configured in `Procfile` / `build.sh`.
4. Set the environment variables on the service:
   - `DJANGO_SECRET_KEY` - new random value
   - `DJANGO_DEBUG=False`
   - `DJANGO_ALLOWED_HOSTS=stocksense.onrender.com` (your assigned domain)
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://stocksense.onrender.com`
   - `DJANGO_HTTPS_ONLY=True`
   - `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
   - `DATABASE_URL` - the Postgres URL from step 2
5. Deploy, then create the production superuser from the Render shell:
   `python manage.py createsuperuser`.
6. Verify: register + OTP + login, receipts / deliveries / transfers / adjustments and the ledger.

## Security Notes

- Passwords are hashed with Django's PBKDF2-SHA256 password hasher.
- CSRF protection is active on every state-changing form and JSON endpoint.
- All inventory routes require authentication; anonymous users are redirected to `/login/`.
- CORS is not needed; `X-Frame-Options` is on by default.
- Email App Passwords are read from environment variables only - they are never hardcoded.
- If a Gmail App Password or `SECRET_KEY` was ever exposed, revoke and rotate it.

## License

Educational / hackathon project - free to use and modify.
