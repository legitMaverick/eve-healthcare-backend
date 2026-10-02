from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TestCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    price: Decimal = Field(gt=0)

class TestOut(TestCreate):
    id: int
    centre_id: int
    model_config = ConfigDict(from_attributes=True)

class CentreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    location: str = Field(min_length=2, max_length=255)

class CentreOut(CentreCreate):
    id: int
    tests: list[TestOut] = []
    model_config = ConfigDict(from_attributes=True)

class BookingCreate(BaseModel):
    test_id: int
    appointment_at: datetime

class BookingOut(BaseModel):
    id: int
    user_id: int
    test_id: int
    centre_id: int
    appointment_at: datetime
    amount: Decimal
    status: str
    model_config = ConfigDict(from_attributes=True)

class PaymentCreate(BaseModel):
    booking_id: int
    amount: Decimal = Field(gt=0)

class PaymentOut(BaseModel):
    id: int
    booking_id: int
    amount: Decimal
    status: str
    provider_reference: str | None
    model_config = ConfigDict(from_attributes=True)

class WebhookEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    booking_id: int
    status: str = Field(pattern="^(SUCCESS|FAILED)$")
    amount: Decimal = Field(gt=0)
    provider_reference: str | None = None
