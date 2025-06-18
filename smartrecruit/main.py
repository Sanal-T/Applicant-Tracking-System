from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
import os
from pathlib import Path

# Security
SECRET_KEY = "your-secret-key-here"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Models
class User(BaseModel):
    id: Optional[int] = None
    email: str
    full_name: str
    user_type: str
    resume_path: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    student_id: Optional[str] = None
    major: Optional[str] = None
    graduation_year: Optional[str] = None
    gpa: Optional[str] = None

class TokenData(BaseModel):
    email: Optional[str] = None

# Database (mock for now)
users_db = {}

# Security functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except jwt.JWTError:
        raise credentials_exception
    user = users_db.get(token_data.email)
    if user is None:
        raise credentials_exception
    return user

# FastAPI app
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartRecruit API"}

@app.get("/api/applications")
async def get_student_applications(current_user: User = Depends(get_current_user)):
    if current_user.user_type != "student":
        raise HTTPException(status_code=403, detail="Only students can access applications")
    
    try:
        # Query to get applications with job details
        query = """
            SELECT 
                a.id,
                a.status,
                a.applied_at,
                a.resume_path,
                j.title as job_title,
                j.location,
                j.type,
                c.name as company_name
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN companies c ON j.company_id = c.id
            WHERE a.student_id = :student_id
            ORDER BY a.applied_at DESC
        """
        
        result = await database.fetch_all(query, {"student_id": current_user.id})
        
        applications = []
        for row in result:
            applications.append({
                "id": row.id,
                "status": row.status,
                "applied_at": row.applied_at,
                "resume_path": row.resume_path,
                "job_title": row.job_title,
                "location": row.location,
                "type": row.type,
                "company_name": row.company_name
            })
        
        return applications
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/applications/{application_id}/resume-analysis")
async def analyze_resume(application_id: int, current_user: User = Depends(get_current_user)):
    if current_user.user_type != "student":
        raise HTTPException(status_code=403, detail="Only students can analyze resumes")
    
    try:
        # Verify the application belongs to the current user
        query = "SELECT * FROM applications WHERE id = :application_id AND student_id = :student_id"
        application = await database.fetch_one(query, {
            "application_id": application_id,
            "student_id": current_user.id
        })
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        if not application.resume_path:
            raise HTTPException(status_code=400, detail="No resume uploaded for this application")
        
        # TODO: Implement actual resume analysis logic
        # For now, return mock data
        return {
            "match_percentage": 85.5,
            "skills": ["Python", "FastAPI", "SQL", "Git", "Docker"],
            "experience_years": 2,
            "education_level": "Bachelor's Degree",
            "recommendations": [
                "Consider adding more cloud computing experience",
                "Highlight your project management skills",
                "Add certifications in relevant technologies"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 