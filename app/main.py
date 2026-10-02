from datetime import datetime, timezone
from decimal import Decimal
from fastapi import FastAPI, Depends, HTTPException, status
from .schemas import (
    UserCreate,
    LoginRequest,
    Token,
    CentreCreate,
    CentreOut,
    TestCreate,
    TestOut,
    BookingCreate,
    BookingOut,
    PaymentCreate,
    PaymentOut,
    WebhookEvent,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import Base, engine, get_db
from .models import User, DiagnosticCentre, DiagnosticTest, Booking, Payment
from .schemas import *
from .auth import hash_password, verify_password, create_token, get_current_user

app = FastAPI(title="EVE Healthcare Diagnostic Booking API", version="1.0.0")

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/signup", response_model=UserOut, status_code=201)
def signup(data: UserCreate, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == data.email.lower())):
        raise HTTPException(409, "Email already registered")
    user = User(name=data.name, email=data.email.lower(), password_hash=hash_password(data.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/auth/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")

    return {"access_token": create_token(user.id), "token_type": "bearer"}

@app.post("/centres", response_model=CentreOut, status_code=201)
def create_centre(data: CentreCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    centre = DiagnosticCentre(name=data.name, location=data.location)
    db.add(centre); db.commit(); db.refresh(centre)
    return centre

@app.get("/centres", response_model=list[CentreOut])
def list_centres(db: Session = Depends(get_db)):
    return db.scalars(select(DiagnosticCentre)).unique().all()

@app.post("/centres/{centre_id}/tests", response_model=TestOut, status_code=201)
def create_test(centre_id: int, data: TestCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    if not db.get(DiagnosticCentre, centre_id):
        raise HTTPException(404, "Diagnostic centre not found")
    test = DiagnosticTest(centre_id=centre_id, name=data.name, price=data.price)
    db.add(test); db.commit(); db.refresh(test)
    return test

@app.get("/centres/{centre_id}/tests", response_model=list[TestOut])
def list_tests(centre_id: int, db: Session = Depends(get_db)):
    if not db.get(DiagnosticCentre, centre_id):
        raise HTTPException(404, "Diagnostic centre not found")
    return db.scalars(select(DiagnosticTest).where(DiagnosticTest.centre_id == centre_id)).all()

@app.post("/bookings", response_model=BookingOut, status_code=201)
def create_booking(data: BookingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if data.appointment_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(400, "Appointment must be in the future")
    test = db.get(DiagnosticTest, data.test_id)
    if not test:
        raise HTTPException(404, "Diagnostic test not found")
    conflict = db.scalar(select(Booking).where(Booking.test_id == test.id, Booking.appointment_at == data.appointment_at, Booking.status.in_(["PENDING", "CONFIRMED"])))
    if conflict:
        raise HTTPException(409, "This appointment slot is already booked")
    booking = Booking(user_id=user.id, test_id=test.id, centre_id=test.centre_id, appointment_at=data.appointment_at, amount=test.price, status="PENDING")
    db.add(booking); db.commit(); db.refresh(booking)
    return booking

@app.get("/bookings", response_model=list[BookingOut])
def list_bookings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Booking).where(Booking.user_id == user.id).order_by(Booking.created_at.desc())).all()

@app.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.get(Booking, booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    return booking

@app.post("/payments", response_model=PaymentOut, status_code=201)
def pay(data: PaymentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    booking = db.get(Booking, data.booking_id)
    if not booking or booking.user_id != user.id:
        raise HTTPException(404, "Booking not found")
    if booking.status in ["CANCELLED", "FAILED"]:
        raise HTTPException(400, "Booking cannot be paid")
    if data.amount != booking.amount:
        raise HTTPException(400, "Payment amount does not match booking amount")
    existing = db.scalar(select(Payment).where(Payment.booking_id == booking.id))
    if existing:
        return existing
    payment_status = "SUCCESS" if data.amount > 0 else "FAILED"
    payment = Payment(booking_id=booking.id, amount=data.amount, status=payment_status, provider_reference=f"SIM-{booking.id}")
    booking.status = "CONFIRMED" if payment_status == "SUCCESS" else "FAILED"
    db.add(payment); db.commit(); db.refresh(payment)
    return payment

@app.post("/payments/webhook/")
def payment_webhook(event: WebhookEvent, db: Session = Depends(get_db)):
    # Idempotency: same event should not be processed twice
    existing_event = db.scalar(
        select(Payment).where(Payment.event_id == event.event_id)
    )

    if existing_event:
        return {
            "status": "already_processed",
            "payment_id": existing_event.id
        }

    # Check booking exists
    booking = db.get(Booking, event.booking_id)

    if not booking:
        raise HTTPException(404, "Booking not found")

    # Verify amount
    if event.amount != booking.amount:
        raise HTTPException(
            400,
            "Webhook amount does not match booking amount"
        )

    # Check if a payment already exists for this booking
    existing_payment = db.scalar(
        select(Payment).where(Payment.booking_id == booking.id)
    )

    if existing_payment:
        # Update existing payment instead of creating a duplicate
        existing_payment.event_id = event.event_id
        existing_payment.status = event.status
        existing_payment.provider_reference = event.provider_reference

        booking.status = (
            "CONFIRMED"
            if event.status == "SUCCESS"
            else "FAILED"
        )

        db.commit()

        return {
            "status": "processed",
            "payment_id": existing_payment.id,
            "booking_status": booking.status
        }

    # No payment exists yet, so create one
    payment = Payment(
        booking_id=booking.id,
        event_id=event.event_id,
        amount=event.amount,
        status=event.status,
        provider_reference=event.provider_reference
    )

    booking.status = (
        "CONFIRMED"
        if event.status == "SUCCESS"
        else "FAILED"
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "status": "processed",
        "payment_id": payment.id,
        "booking_status": booking.status
    }
