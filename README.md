# EVE Healthcare — Diagnostic Booking Backend

FastAPI + PostgreSQL backend implementing the EVE Healthcare SDE Intern assignment.

## Features
- User signup/login with JWT authentication and request validation.
- Diagnostic centres and tests with prices.
- Authenticated diagnostic test bookings.
- Simulated payment endpoint; no real payment gateway.
- Idempotent payment webhook using a unique `event_id`.
- Authorization checks so users can only access their own bookings.
- Future appointment validation and duplicate-slot protection.
- Swagger/OpenAPI at `/docs`.
- Docker Compose with PostgreSQL.

## Run with Docker
```bash
docker compose up --build
```
Open `http://localhost:8000/docs`.

## Run locally
Install PostgreSQL, create a database, then:
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/macOS
uvicorn app.main:app --reload
```

## API endpoints
| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | No | Create user |
| POST | `/auth/login` | No | Get JWT |
| GET | `/centres` | No | List centres/tests |
| POST | `/centres` | Yes | Create centre |
| GET | `/centres/{id}/tests` | No | List centre tests |
| POST | `/centres/{id}/tests` | Yes | Add test |
| POST | `/bookings` | Yes | Create booking |
| GET | `/bookings` | Yes | List current user's bookings |
| GET | `/bookings/{id}` | Yes | Get own booking |
| POST | `/payments` | Yes | Simulate payment |
| POST | `/payments/webhook/` | Provider | Process payment event idempotently |
| GET | `/health` | No | Health check |

### Signup
```json
{
  "name": "Krish",
  "email": "krish@example.com",
  "password": "password123"
}
```

### Create centre
```json
{"name":"EVE Diagnostics","location":"Greater Noida"}
```

### Add test
```json
{"name":"CBC","price":499.00}
```

### Book test
```json
{"test_id":1,"appointment_at":"2026-10-10T10:30:00"}
```

### Simulated payment
```json
{"booking_id":1,"amount":499.00}
```

### Webhook
```json
{
  "event_id":"evt_001",
  "booking_id":1,
  "status":"SUCCESS",
  "amount":499.00,
  "provider_reference":"provider_123"
}
```
Sending the same `event_id` again returns `already_processed` and does not create another payment.

## Database design
- `users`: authenticated users.
- `diagnostic_centres`: centre name/location.
- `diagnostic_tests`: tests and prices belonging to a centre.
- `bookings`: user, test, centre, appointment, amount and status.
- `payments`: one payment per booking and unique webhook event IDs.

Booking states: `PENDING`, `CONFIRMED`, `FAILED`, `CANCELLED`.
Payment states: `SUCCESS`, `FAILED`.

## Important assumptions
1. A diagnostic test belongs to exactly one centre.
2. The booking amount is copied from the test price at booking time so later price changes do not alter historical bookings.
3. A test cannot have two active bookings for the exact same appointment timestamp.
4. The mock payment succeeds for a valid positive amount matching the booking amount; the webhook can explicitly deliver SUCCESS/FAILED.
5. Webhook authentication/signatures are outside the assignment scope because the provider is simulated.

## Testing
```bash
pytest -q
```
The included test suite can be expanded with full integration coverage for authentication, booking ownership, payment transitions, and duplicate webhook delivery.

## What I would improve with more time
- Alembic migrations instead of startup table creation.
- Full unit/integration test coverage with isolated PostgreSQL/SQLite fixtures.
- Webhook signature verification and an event-processing table.
- Redis caching, Celery jobs, rate limiting and structured JSON logging.
- Pagination/filtering for centres, tests and bookings.
- CI pipeline with linting, type checking, tests and Docker image checks.
