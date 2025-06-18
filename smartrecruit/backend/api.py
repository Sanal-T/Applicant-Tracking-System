from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext

app = FastAPI(title="SmartRecruit API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
SECRET_KEY = "your-secret-key-here"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Models
class UserBase(BaseModel):
    email: str
    full_name: str
    student_id: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

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

# In-memory storage (replace with database in production)
users_db = {}
jobs_db = {}

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# User Routes
@app.post("/register", response_model=User)
def register_user(user: UserCreate):
    if user.email in users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_password
    user_dict["id"] = len(users_db) + 1
    user_dict["is_active"] = True
    
    users_db[user.email] = user_dict
    return user_dict

@app.post("/login", response_model=Token)
def login(login_data: LoginRequest):
    user = users_db.get(login_data.email)
    if not user or not pwd_context.verify(login_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

# Job Routes
@app.post("/jobs", response_model=Job)
def create_job(job: JobCreate):
    job_dict = job.dict()
    job_dict["id"] = len(jobs_db) + 1
    job_dict["posted_date"] = datetime.utcnow()
    job_dict["is_active"] = True
    
    jobs_db[job_dict["id"]] = job_dict
    return job_dict

@app.get("/jobs", response_model=List[Job])
def get_jobs():
    return list(jobs_db.values())

@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: int):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_db[job_id]

@app.put("/jobs/{job_id}", response_model=Job)
def update_job(job_id: int, job: JobCreate):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dict = job.dict()
    job_dict["id"] = job_id
    job_dict["posted_date"] = jobs_db[job_id]["posted_date"]
    job_dict["is_active"] = jobs_db[job_id]["is_active"]
    
    jobs_db[job_id] = job_dict
    return job_dict

@app.delete("/jobs/{job_id}")
def delete_job(job_id: int):
    if job_id not in jobs_db:
        raise HTTPException(status_code=404, detail="Job not found")
    
    del jobs_db[job_id]
    return {"message": "Job deleted successfully"}

@app.get("/")
def read_root():
    return {"message": "Welcome to SmartRecruit API"} 