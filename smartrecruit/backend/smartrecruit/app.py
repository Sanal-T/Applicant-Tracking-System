from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import List, Optional
from datetime import datetime, timedelta
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import databases
import sqlalchemy
from sqlalchemy import create_engine
import os
import json
from fastapi.responses import FileResponse
from pathlib import Path

# Database configuration
DATABASE_URL = "sqlite:///./smartrecruit.db"
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Create tables
users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("full_name", sqlalchemy.String),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
    sqlalchemy.Column("user_type", sqlalchemy.String),
    sqlalchemy.Column("phone", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("location", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow)
)

companies = sqlalchemy.Table(
    "companies",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String),
    sqlalchemy.Column("description", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("website", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow)
)

jobs = sqlalchemy.Table(
    "jobs",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("company_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("companies.id")),
    sqlalchemy.Column("title", sqlalchemy.String),
    sqlalchemy.Column("description", sqlalchemy.String),
    sqlalchemy.Column("requirements", sqlalchemy.String),
    sqlalchemy.Column("location", sqlalchemy.String),
    sqlalchemy.Column("type", sqlalchemy.String),
    sqlalchemy.Column("salary_range", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow)
)

applications = sqlalchemy.Table(
    "applications",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("student_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id")),
    sqlalchemy.Column("job_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("jobs.id")),
    sqlalchemy.Column("status", sqlalchemy.String, default="pending"),
    sqlalchemy.Column("resume_path", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("applied_at", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
)

student_profiles = sqlalchemy.Table(
    "student_profiles",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("user_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id")),
    sqlalchemy.Column("skills", sqlalchemy.String, default="[]"),
    sqlalchemy.Column("experience", sqlalchemy.String, default="[]"),
    sqlalchemy.Column("education", sqlalchemy.String, default="[]"),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime, default=datetime.utcnow),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
)

engine = create_engine(DATABASE_URL)
metadata.create_all(engine)

# Security configuration
SECRET_KEY = "your-secret-key"  # Change this in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Models
class User(BaseModel):
    id: int
    email: str
    full_name: str
    user_type: str
    phone: Optional[str] = None
    location: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Security functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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
    
    query = "SELECT * FROM users WHERE email = :email"
    user = await database.fetch_one(query, {"email": token_data.email})
    if user is None:
        raise credentials_exception
    return User(**dict(user))

# FastAPI app
app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Frontend directory configuration
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

# Routes
@app.get("/")
async def read_root():
    return {"message": "Welcome to SmartRecruit API"}

@app.post("/api/signup")
async def signup(user_data: dict):
    try:
        # Check if user already exists
        query = "SELECT * FROM users WHERE email = :email"
        existing_user = await database.fetch_one(query, {"email": user_data["email"]})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create new user
        query = """
            INSERT INTO users (email, full_name, hashed_password, user_type, phone, location)
            VALUES (:email, :full_name, :hashed_password, :user_type, :phone, :location)
        """
        await database.execute(query, {
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "hashed_password": get_password_hash(user_data["password"]),
            "user_type": user_data["user_type"],
            "phone": user_data.get("phone"),
            "location": user_data.get("location")
        })
        
        return {"message": "User created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        query = "SELECT * FROM users WHERE email = :email"
        user = await database.fetch_one(query, {"email": form_data.username})
        
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(data={"sub": user.email})
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    try:
        # Get user profile with additional details
        query = """
            SELECT 
                u.*,
                s.skills,
                s.experience,
                s.education
            FROM users u
            LEFT JOIN student_profiles s ON u.id = s.user_id
            WHERE u.id = :user_id
        """
        
        result = await database.fetch_one(query, {"user_id": current_user.id})
        
        if not result:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        return {
            "id": result.id,
            "email": result.email,
            "full_name": result.full_name,
            "phone": result.phone,
            "location": result.location,
            "user_type": result.user_type,
            "skills": json.loads(result.skills) if result.skills else [],
            "experience": json.loads(result.experience) if result.experience else [],
            "education": json.loads(result.education) if result.education else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/me")
async def update_user_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user)
):
    try:
        # Update user profile
        query = """
            UPDATE users
            SET 
                full_name = :full_name,
                phone = :phone,
                location = :location
            WHERE id = :user_id
        """
        
        await database.execute(query, {
            "user_id": current_user.id,
            "full_name": profile_data.get("full_name"),
            "phone": profile_data.get("phone"),
            "location": profile_data.get("location")
        })
        
        return {"message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/me/skills")
async def update_user_skills(
    skills_data: dict,
    current_user: User = Depends(get_current_user)
):
    try:
        # Check if student profile exists
        check_query = "SELECT id FROM student_profiles WHERE user_id = :user_id"
        profile = await database.fetch_one(check_query, {"user_id": current_user.id})
        
        if not profile:
            # Create student profile if it doesn't exist
            create_query = """
                INSERT INTO student_profiles (user_id, skills, experience, education)
                VALUES (:user_id, :skills, '[]', '[]')
            """
            await database.execute(create_query, {
                "user_id": current_user.id,
                "skills": json.dumps(skills_data.get("skills", []))
            })
        else:
            # Update existing profile
            update_query = """
                UPDATE student_profiles
                SET skills = :skills
                WHERE user_id = :user_id
            """
            await database.execute(update_query, {
                "user_id": current_user.id,
                "skills": json.dumps(skills_data.get("skills", []))
            })
        
        return {"message": "Skills updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/me/experience")
async def update_user_experience(
    experience_data: dict,
    current_user: User = Depends(get_current_user)
):
    try:
        # Check if student profile exists
        check_query = "SELECT id FROM student_profiles WHERE user_id = :user_id"
        profile = await database.fetch_one(check_query, {"user_id": current_user.id})
        
        if not profile:
            # Create student profile if it doesn't exist
            create_query = """
                INSERT INTO student_profiles (user_id, skills, experience, education)
                VALUES (:user_id, '[]', :experience, '[]')
            """
            await database.execute(create_query, {
                "user_id": current_user.id,
                "experience": json.dumps(experience_data.get("experience", []))
            })
        else:
            # Update existing profile
            update_query = """
                UPDATE student_profiles
                SET experience = :experience
                WHERE user_id = :user_id
            """
            await database.execute(update_query, {
                "user_id": current_user.id,
                "experience": json.dumps(experience_data.get("experience", []))
            })
        
        return {"message": "Experience updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/me/education")
async def update_user_education(
    education_data: dict,
    current_user: User = Depends(get_current_user)
):
    try:
        # Check if student profile exists
        check_query = "SELECT id FROM student_profiles WHERE user_id = :user_id"
        profile = await database.fetch_one(check_query, {"user_id": current_user.id})
        
        if not profile:
            # Create student profile if it doesn't exist
            create_query = """
                INSERT INTO student_profiles (user_id, skills, experience, education)
                VALUES (:user_id, '[]', '[]', :education)
            """
            await database.execute(create_query, {
                "user_id": current_user.id,
                "education": json.dumps(education_data.get("education", []))
            })
        else:
            # Update existing profile
            update_query = """
                UPDATE student_profiles
                SET education = :education
                WHERE user_id = :user_id
            """
            await database.execute(update_query, {
                "user_id": current_user.id,
                "education": json.dumps(education_data.get("education", []))
            })
        
        return {"message": "Education updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

@app.get("/profile-portal")
async def profile_portal():
    """
    Serve the profile portal page
    """
    return FileResponse(str(FRONTEND_DIR / "profile-portal.html"))

# Startup and shutdown events
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect() 