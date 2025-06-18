from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: str
    full_name: str
    student_id: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class JobBase(BaseModel):
    title: str
    company: str
    description: str
    requirements: List[str]
    location: str
    salary_range: Optional[str] = None

class JobCreate(JobBase):
    pass

class Job(JobBase):
    id: int
    posted_date: datetime
    is_active: bool

    class Config:
        from_attributes = True 