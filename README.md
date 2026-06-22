# Retail App

![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/flask-%3E%3D1.1-brightgreen.svg)
![Demo](https://img.shields.io/badge/demo-ready-brightgreen.svg)

A lightweight, demo-grade Flask retail management app: inventory, B2B/B2C orders, restocking and analytics backed by MySQL.

--

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Seeded Accounts](#seeded-accounts)
- [Contributing](#contributing)
- [License & Notes](#license--notes)


## Features
- Simple MVC structure using Flask controllers and domain models
- MySQL-backed schema with demo seed data created automatically
- Inventory CRUD, low-stock reports and restock workflow
- B2B (bulk) and B2C (retail) order flows with basic validation
- Sales analytics endpoints for charts and dashboards


## Quick Start

1. Clone the repo and enter the folder:

```bash
git clone <repo-url>
cd retail_app
```

2. Create and activate a virtual environment (Windows example):

```bash
python -m venv venv
venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Configure your DB connection in `models/db.py` (edit `DB_CONFIG`).

5. Run the app (development):

```bash
python app.py
```

6. Open http://127.0.0.1:5000 and sign in.


## Configuration
- Database configuration: edit `models/db.py` -> `DB_CONFIG` (host, user, password, database, port).
- Secret key: change `app.secret_key` in `app.py` for any non-demo use.
- If you prefer `.env` files, add `python-dotenv` and load variables in `app.py`.


## Architecture

```mermaid
flowchart LR
	Browser -->|HTTP| Flask[Flask App - app.py]
	Flask --> Controllers[Controllers]
	Controllers --> Models[Domain Models]
	Models --> MySQL[(MySQL DB)]
	Controllers --> Templates[Templates (Jinja2)]
```

Routes are defined in `app.py`, controllers live in `controllers/` and interact with `models/` which use `models/db.py` for SQL access.


## Seeded Accounts
- admin / admin (admin)
- mgr_west / pass (manager)
- mgr_east / pass (manager)

These are seeded for demo convenience — change before publishing or use proper password hashing.


## Contributing
- Add reproducible screenshots or an animated demo in `assets/`.
- Consider adding a `docker-compose.yml` and GitHub Actions CI for automated tests and badges.


## License & Notes
This is a demo project and not production hardened. Do not expose the seeded credentials or the DB credentials in public repositories. Recommended improvements before production:

- Use secure password hashing (Werkzeug or bcrypt)
- Move DB config and secret keys to environment variables
- Add input sanitization and CSRF protection

---

If you'd like, I can also:

- generate a `requirements.txt` (I will add it now),
- add a `docker-compose.yml` for easy local runs, or
- create a small GitHub Actions workflow and badges. Reply which you want next.
