# Digital Wallet & Transaction Processing Platform

A REST API backend built with **FastAPI and PostgreSQL** for managing digital wallets, financial transactions, transaction history, refunds, and administrative controls.

## Overview

The Digital Wallet & Transaction Processing Platform provides backend APIs for customers to manage wallets and perform financial operations securely. It uses JWT authentication, role-based authorization, SQLAlchemy ORM, and Alembic database migrations.

## Technology Stack

- **Backend:** Python, FastAPI
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy
- **Database Migrations:** Alembic
- **Authentication:** JWT access and refresh tokens
- **Validation:** Pydantic
- **Testing:** Pytest, HTTPX
- **API Documentation:** Swagger UI / OpenAPI

## Key Modules

- **Authentication:** Registration, login, current-user profile, password change, refresh tokens, and logout.
- **Wallet Management:** Create and view wallets, check balances, and manage wallet status.
- **Transactions:** Deposits, withdrawals, transfers, and transaction history.
- **Refunds:** Refund requests and administrative review.
- **Transaction Controls:** Configurable transaction limits and suspicious-transaction checks.
- **Notifications:** User notifications and read status.
- **Audit Logs:** Records of important system operations.
- **Admin Dashboard:** Administrative metrics and management APIs.
- **Idempotency:** Support for preventing duplicate financial operations using idempotency keys; verify endpoint integration before claiming it is fully enabled.

## Project Structure

```text
Digital-Wallet-Platform/
├── app/
│   ├── core/
│   ├── db/
│   ├── dependencies/
│   ├── models/
│   ├── repositories/
│   ├── routers/
│   ├── schemas/
│   ├── services/
│   ├── tasks/
│   └── main.py
├── docs/
├── postman/
├── tests/
├── alembic/
├── .env.example
├── .gitignore
├── alembic.ini
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.12 or a compatible Python version
- PostgreSQL
- Git

## Installation and Setup

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd Digital-Wallet-Platform
```

### 2. Create a virtual environment

**Windows PowerShell:**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and update the values for your local environment.

Example configuration:

```env
APP_NAME=Digital Wallet Platform
DEBUG=True
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/digital_wallet_db
JWT_SECRET_KEY=YOUR_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**Security:** Never commit `.env`, database passwords, or real JWT secrets to GitHub.

### 5. Create the PostgreSQL database

Create a database named `digital_wallet_db` in PostgreSQL, or update `DATABASE_URL` to use your existing database.

### 6. Apply database migrations

```powershell
alembic upgrade head
```

If the project has model changes that are not yet included in a migration, generate and review a migration before applying it:

```powershell
alembic revision --autogenerate -m "update wallet platform models"
alembic upgrade head
```

### 7. Run the application

```powershell
uvicorn app.main:app --reload
```

The development server normally runs at `http://127.0.0.1:8000`.

## API Documentation

Once the application is running, open:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Use the documentation to inspect available endpoints and test requests with valid authentication.

## Running Tests

```powershell
pytest -v
```

Configure tests to use a dedicated test database or test dependency overrides. Do not run test cases that create, modify, or delete data in a production database.

## Security and Reliability

- Password hashing and JWT-based authentication
- Role-based access checks
- Database transactions for financial operations
- Wallet balance validation
- Transaction limits and suspicious-activity checks
- Environment-based configuration
- Idempotency support, subject to complete endpoint integration and testing

## Development Status

This project is developed as a backend engineering assignment. Run database migrations and the test suite in the target environment before treating it as ready for deployment. Production deployment additionally requires security review, monitoring, logging, and verified concurrency and recovery behavior.

## Author

**Kishore Varma**

GitHub: https://github.com/kishoregithub0601
