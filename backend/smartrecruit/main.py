from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import jwt
from datetime import datetime, timedelta
import os
import shutil
from PIL import Image
import pytesseract
import PyPDF2
import io
import re
from pathlib import Path
import random
from fastapi.routing import APIRoute
from starlette.routing import Route
from starlette.responses import Response, JSONResponse
import sys
import traceback

# Set DEBUG_MODE to True for development, False for production
DEBUG_MODE = True
print(f"DEBUG_MODE: {DEBUG_MODE}")

# Authentication settings for development only (NEVER use these values in production)
# In DEBUG_MODE, we'll use a simplified key for easier testing
SECRET_KEY = "demoTokenSignatureForTestingOnly12345" if DEBUG_MODE else "secure-production-key-should-be-used-here"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 if not DEBUG_MODE else 1440  # 1 day in debug mode

# Initialize FastAPI app
app = FastAPI(title="SmartRecruit API")

# Define allowed origins based on mode
ALLOWED_ORIGINS = [
    "http://localhost:5501",
    "http://127.0.0.1:5501",
    "http://localhost:5000",
    "http://127.0.0.1:5000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    # Add production origins here
]

# Configure CORS middleware settings
app.add_middleware(
    CORSMiddleware,
    # In debug mode, allow all origins with "*" for easier development
    allow_origins=["*"] if DEBUG_MODE else ALLOWED_ORIGINS,
    allow_credentials=False,  # Must be False when using "*"
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "Authorization", "Content-Length"],
    max_age=86400,  # Cache preflight requests for 24 hours
)

# Add exception handlers to ensure CORS headers are included in error responses
@app.exception_handler(500)
async def internal_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"message": f"Internal server error: {str(exc)}"},
        headers={"Access-Control-Allow-Origin": "*" if DEBUG_MODE else request.headers.get("origin")}
    )

@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"message": "Resource not found"},
        headers={"Access-Control-Allow-Origin": "*" if DEBUG_MODE else request.headers.get("origin")}
    )

# Override the default exception handler for all other exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    status_code = 500
    if hasattr(exc, "status_code"):
        status_code = exc.status_code
        
    return JSONResponse(
        status_code=status_code,
        content={"message": str(exc)},
        headers={"Access-Control-Allow-Origin": "*" if DEBUG_MODE else request.headers.get("origin")}
    )

# Add OPTIONS route handler for preflight requests
@app.options("/api/me/resume/upload")
async def options_resume_upload():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
    )

# Add OPTIONS route handler for resume analysis
@app.options("/api/me/resume/analyze")
async def options_resume_analyze():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
    )

# Add OPTIONS route handler for job match
@app.options("/api/me/resume/job-match")
async def options_job_match():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
    )

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# User models
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    user_type: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool = True

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Mock database (replace with real database in production)
fake_users_db = {}

# Initialize with a test user for development
if DEBUG_MODE:
    # Add a demo user that will always work for testing
    demo_user = {
        "id": 1,
        "email": "demo@example.com",
        "full_name": "Demo User",
        "user_type": "student",
        "password": "demo123",
        "is_active": True
    }
    fake_users_db["demo@example.com"] = demo_user
    print("Initialized fake database with demo user: demo@example.com / demo123")
    
    # Create uploads directory structure
    uploads_dir = Path("uploads/resumes/1")  # Demo user ID is 1
    uploads_dir.mkdir(parents=True, exist_ok=True)
    print(f"Created upload directory: {uploads_dir}")
    
    # Set proper permissions for the uploads directory
    try:
        os.chmod(uploads_dir, 0o777)  # Giving full permissions in dev mode
        print(f"Set permissions for upload directory: {uploads_dir}")
    except Exception as e:
        print(f"Warning: Could not set permissions on upload directory: {str(e)}")

def get_user(email: str):
    if email in fake_users_db:
        user_dict = fake_users_db[email]
        return User(**user_dict)
    # Special handling for demo user in case token is using this email
    if email == "demo@example.com" and "demo@example.com" not in fake_users_db:
        demo_user = {
            "id": 1,
            "email": "demo@example.com",
            "full_name": "Demo User",
            "user_type": "student",
            "is_active": True
        }
        return User(**demo_user)
    return None

def authenticate_user(email: str, password: str):
    user_data = fake_users_db.get(email)
    if not user_data:
        return False
    # In production, use proper password hashing
    return user_data.get("password") == password

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
    except jwt.InvalidTokenError:
        raise credentials_exception
    user = get_user(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

# Add these new models
class ResumeAnalysis(BaseModel):
    ats_score: float
    parse_status: Optional[dict] = None
    contact_info: dict
    education: List[dict]
    experience: List[dict]
    skills: List[str]
    mistakes: Optional[List[dict]] = None
    improvement_suggestions: Optional[List[dict]] = None
    keyword_analysis: Optional[dict] = None

class JobMatch(BaseModel):
    job_title: Optional[str] = None
    job_description: Optional[str] = None

class JobMatchResult(BaseModel):
    match_percentage: float
    matching_keywords: List[dict]
    missing_keywords: List[dict]
    improvement_suggestions: List[str]

# Add these new endpoints
@app.post("/api/me/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Form(None),
    extracted_text: Optional[str] = Form(None)
):
    """Upload a resume file for analysis"""
    
    # CORS headers
    headers = {
        "Access-Control-Allow-Origin": "*" if DEBUG_MODE else None,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    
    try:
        # Token validation logic
        if token and not authorization:
            authorization = f"Bearer {token}"
            
        if not authorization:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing authorization header"},
                headers=headers
            )
        
        # Extract token
        try:
            scheme, token = authorization.split()
            if scheme.lower() != 'bearer':
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid authorization scheme"},
                    headers=headers
                )
        except Exception:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid authorization format"},
                headers=headers
            )
            
        # Validate token
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            if not email:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"},
                    headers=headers
                )
            current_user = get_user(email)
            if not current_user:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "User not found"},
                    headers=headers
                )
        except Exception as e:
            return JSONResponse(
                status_code=401,
                content={"detail": f"Token validation failed: {str(e)}"},
                headers=headers
            )
        
        # Basic validation
        if not file:
            return JSONResponse(
                status_code=400,
                content={"detail": "No file provided"},
                headers=headers
            )
            
        if not file.filename:
            return JSONResponse(
                status_code=400,
                content={"detail": "Missing filename"},
                headers=headers
            )
        
        # File type validation
        valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in valid_extensions:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Unsupported file type. Please upload one of: {', '.join(valid_extensions)}"},
                headers=headers
            )
        
        # Create uploads directory with explicit permission checks
        try:
            uploads_dir = "uploads"
            # Check if directory exists or can be created
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
                
            # Check if we have write permissions by testing write
            test_file = os.path.join(uploads_dir, ".test_write_permission")
            try:
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as perm_error:
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Cannot write to uploads directory. Permission error: {str(perm_error)}"},
                    headers=headers
                )
                
            resumes_dir = os.path.join(uploads_dir, "resumes")
            if not os.path.exists(resumes_dir):
                os.makedirs(resumes_dir)
                
            user_dir = os.path.join(resumes_dir, str(current_user.id))
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
                
            print(f"Directories created/verified: {user_dir}")
                
        except Exception as dir_error:
            print(f"Error creating directories: {str(dir_error)}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Failed to create upload directories: {str(dir_error)}"},
                headers=headers
            )
        
        # Create a secure filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Remove potentially unsafe characters
        safe_filename = re.sub(r'[^\w.-]', '_', file.filename)
        filename = f"resume_{timestamp}_{safe_filename}"
        file_path = os.path.join(user_dir, filename)
        
        # File size check
        MAX_SIZE = 10 * 1024 * 1024  # 10MB limit
        content = await file.read(MAX_SIZE + 1)
        
        if len(content) > MAX_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": "File too large. Maximum size is 10MB."},
                headers=headers
            )
        
        # Save file with explicit error handling
        try:
            with open(file_path, "wb") as f:
                f.write(content)
        except PermissionError:
            return JSONResponse(
                status_code=500,
                content={"detail": "Permission denied when writing file. Check directory permissions."},
                headers=headers
            )
        except Exception as write_error:
            return JSONResponse(
                status_code=500,
                content={"detail": f"Failed to write file: {str(write_error)}"},
                headers=headers
            )
        
        # If extracted text was provided, save it too
        if extracted_text:
            try:
                text_path = os.path.join(user_dir, f"text_{timestamp}.txt")
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(extracted_text)
            except Exception as text_error:
                print(f"Note: Failed to save extracted text: {str(text_error)}")
                # Don't fail the whole upload if just the text part fails
        
        # Return success
        return JSONResponse(
            content={
                "message": "Resume uploaded successfully",
                "filename": filename,
                "user_id": current_user.id
            },
            headers=headers
        )
        
    except Exception as e:
        # Log error but don't expose details to client
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={"detail": f"An error occurred while processing your upload: {str(e)}"},
            headers=headers
        )

def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Extract text from PDF files with robust error handling and fallbacks
    """
    text = ""
    
    # Method 1: Try using PyPDF2
    try:
        print(f"Attempting to extract text from {pdf_path} using PyPDF2")
        with open(pdf_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num in range(len(pdf_reader.pages)):
                try:
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    text += page_text + "\n"
                except Exception as page_error:
                    print(f"Error extracting text from page {page_num}: {str(page_error)}")
                    continue
        
        if len(text.strip()) > 50:
            print(f"Successfully extracted {len(text)} characters with PyPDF2")
            return text
        else:
            print("PyPDF2 extraction yielded insufficient text, trying alternative methods")
    except Exception as e:
        print(f"PyPDF2 extraction failed: {str(e)}")
    
    # Method 2: Try using external tools if available
    try:
        # Check if pdftotext is available (from poppler-utils)
        import subprocess
        import platform
        
        # Determine if pdftotext is likely available based on platform
        if platform.system() == "Linux":
            cmd = ["pdftotext", "-v"]
        elif platform.system() == "Windows":
            cmd = ["where", "pdftotext"]
        else:  # macOS
            cmd = ["which", "pdftotext"]
            
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if result.returncode == 0 or "pdftotext" in str(result.stdout) + str(result.stderr):
            print("pdftotext appears to be available, attempting to use it")
            output_path = str(pdf_path) + ".txt"
            subprocess.run(["pdftotext", str(pdf_path), output_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if os.path.exists(output_path):
                with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                
                # Clean up temporary file
                try:
                    os.remove(output_path)
                except Exception as rm_error:
                    print(f"Warning: Could not remove temp file: {str(rm_error)}")
                
                if len(text.strip()) > 50:
                    print(f"Successfully extracted {len(text)} characters using pdftotext")
                    return text
    except Exception as ext_error:
        print(f"External tool extraction failed: {str(ext_error)}")
    
    # Method 3: Super basic fallback - just try to read as text
    try:
        print("Attempting basic text extraction as last resort")
        with open(pdf_path, "rb") as f:
            content = f.read()
            
        # Try to decode as UTF-8 with error handling
        try:
            raw_text = content.decode('utf-8', errors='ignore')
            
            # Remove non-printable characters
            import string
            printable = set(string.printable)
            clean_text = ''.join(c for c in raw_text if c in printable)
            
            if len(clean_text.strip()) > 50:
                print(f"Basic text extraction yielded {len(clean_text)} characters")
                return clean_text
        except Exception as decode_error:
            print(f"Text decoding failed: {str(decode_error)}")
    except Exception as basic_error:
        print(f"Basic extraction attempt failed: {str(basic_error)}")
    
    # If all methods fail, return placeholder with instructions
    return "PDF text extraction failed. This PDF may be image-based or secured. Please try uploading a different file format or a text-based PDF."

def extract_text_from_image(image_path: Path) -> str:
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)
    return text

def parse_resume_text(text: str) -> ResumeAnalysis:
    # Extract contact information
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
    
    emails = re.findall(email_pattern, text)
    phones = re.findall(phone_pattern, text)
    
    # Extract education (simple pattern matching)
    education = []
    edu_sections = re.finditer(r'Education(.*?)(?=Experience|$)', text, re.DOTALL | re.IGNORECASE)
    for section in edu_sections:
        edu_text = section.group(1).strip()
        education.append({
            "degree": extract_degree(edu_text),
            "institution": extract_institution(edu_text),
            "date_range": extract_date_range(edu_text)
        })
    
    # Extract experience
    experience = []
    exp_sections = re.finditer(r'Experience(.*?)(?=Education|$)', text, re.DOTALL | re.IGNORECASE)
    for section in exp_sections:
        exp_text = section.group(1).strip()
        experience.append({
            "title": extract_job_title(exp_text),
            "company": extract_company(exp_text),
            "date_range": extract_date_range(exp_text),
            "description": extract_job_description(exp_text)
        })
    
    # Extract skills (common technical skills)
    common_skills = [
        "Python", "Java", "JavaScript", "SQL", "HTML", "CSS", "React", "Node.js",
        "AWS", "Docker", "Kubernetes", "Git", "Agile", "Machine Learning",
        "Data Analysis", "Project Management", "Communication", "Leadership"
    ]
    skills = [skill for skill in common_skills if skill.lower() in text.lower()]
    
    # Generate recommendations
    recommendations = generate_recommendations(text, skills)
    
    # Identify mistakes
    mistakes = identify_mistakes(text, skills)
    
    # Generate improvement suggestions
    suggestions = generate_improvement_suggestions(text, skills)
    
    # Analyze keywords
    keyword_analysis = analyze_keywords(text, skills)
    
    return ResumeAnalysis(
        ats_score=calculate_ats_score(text, skills),
        parse_status={
            "success": True,
            "confidence": 0.85,
            "message": "Resume parsed successfully"
        },
        contact_info={
            "name": extract_name(text),
            "email": emails[0] if emails else None,
            "phone": phones[0] if phones else None,
            "location": extract_location(text)
        },
        education=education,
        experience=experience,
        skills=skills,
        mistakes=mistakes,
        improvement_suggestions=suggestions,
        keyword_analysis=keyword_analysis
    )

def extract_name(text: str) -> str:
    # Simple heuristic: first line might be the name
    lines = text.split('\n')
    if lines and len(lines[0].split()) <= 3:
        return lines[0].strip()
    return "Not detected"

def extract_location(text: str) -> str:
    # Common US city/state pattern
    location_pattern = r'\b[A-Z][a-z]+(?:[\s,]+[A-Z]{2})?\b'
    locations = re.findall(location_pattern, text)
    return locations[0] if locations else "Not detected"

def extract_date_range(text: str) -> str:
    # Look for date ranges like "2019-2021" or "Jan 2019 - Present"
    date_pattern = r'\b\d{4}\s*[-–—]\s*(?:\d{4}|Present|Current)\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[-–—]\s*Present\b'
    matches = re.findall(date_pattern, text, re.IGNORECASE)
    return matches[0] if matches else ""

def extract_job_description(text: str) -> str:
    # Extract job description from experience section
    lines = text.split('\n')
    if len(lines) > 2:
        return " ".join(lines[2:]).strip()
    return ""

def extract_degree(text: str) -> str:
    degrees = ["Bachelor", "Master", "PhD", "B.S.", "M.S.", "B.A.", "M.A."]
    for degree in degrees:
        if degree in text:
            return degree
    return "Not specified"

def extract_institution(text: str) -> str:
    # Simple pattern matching for institution names
    lines = text.split('\n')
    for line in lines:
        if any(degree in line for degree in ["Bachelor", "Master", "PhD", "B.S.", "M.S.", "B.A.", "M.A."]):
            return line.strip()
    return "Not specified"

def extract_job_title(text: str) -> str:
    # Extract first line as job title
    lines = text.split('\n')
    return lines[0].strip() if lines else "Not specified"

def extract_company(text: str) -> str:
    # Extract second line as company name
    lines = text.split('\n')
    return lines[1].strip() if len(lines) > 1 else "Not specified"

def calculate_ats_score(text: str, skills: List[str]) -> float:
    # Simple scoring based on keyword matches
    base_score = 0.5
    skill_score = min(len(skills) / 10, 0.5)  # Max 0.5 points for skills
    return round(base_score + skill_score, 2)

def identify_mistakes(text: str, skills: List[str]) -> List[dict]:
    mistakes = []
    
    # Check for missing metrics
    if not re.search(r'\b\d+%|\d+ percent|increased|decreased|improved|reduced\b', text, re.IGNORECASE):
        mistakes.append({
            "type": "missing_metrics",
            "description": "Your resume lacks specific metrics that demonstrate your impact",
            "suggestion": "Add quantifiable achievements (e.g., 'improved performance by 40%')"
        })
    
    # Check for weak action verbs
    weak_verbs = ["worked", "helped", "assisted", "involved"]
    if any(verb in text.lower() for verb in weak_verbs):
        mistakes.append({
            "type": "weak_action_verbs",
            "description": "Some sections use weak action verbs",
            "suggestion": "Replace 'worked on' with stronger verbs like 'spearheaded' or 'implemented'"
        })
    
    # Check for inconsistent date formatting
    date_formats = re.findall(r'\b\d{2}/\d{4}\b|\b\d{4}-\d{2}\b|\b\d{2}-\d{4}\b|\b\w{3} \d{4}\b', text)
    unique_formats = set(re.sub(r'\d', 'X', date) for date in date_formats)
    if len(unique_formats) > 1:
        mistakes.append({
            "type": "inconsistent_formatting",
            "description": "Date formats are inconsistent across the resume",
            "suggestion": "Standardize all dates to the same format (MM/YYYY or Month YYYY)"
        })
    
    return mistakes

def generate_improvement_suggestions(text: str, skills: List[str]) -> List[dict]:
    suggestions = []
    
    # Check for missing summary
    if not re.search(r'summary|profile|objective', text, re.IGNORECASE):
        suggestions.append({
            "category": "content",
            "title": "Add a professional summary",
            "description": "Including a concise professional summary at the top of your resume can quickly highlight your expertise and career focus."
        })
    
    # Check for keyword density
    if len(skills) < 7:
        suggestions.append({
            "category": "keywords",
            "title": "Incorporate more industry keywords",
            "description": "Your resume could benefit from more industry-specific terminology to pass ATS filters."
        })
    
    # Check for section organization
    if not re.search(r'experience.*?education|skills.*?experience', text, re.IGNORECASE | re.DOTALL):
        suggestions.append({
            "category": "format",
            "title": "Improve section organization",
            "description": "Consider reorganizing sections to highlight your most impressive achievements first."
        })
    
    return suggestions

def analyze_keywords(text: str, skills: List[str]) -> dict:
    # Generate keyword analysis with presence count and relevance
    present_keywords = []
    for skill in skills:
        count = len(re.findall(rf'\b{re.escape(skill)}\b', text, re.IGNORECASE))
        relevance = "high" if count > 1 else "medium"
        present_keywords.append({
            "keyword": skill,
            "relevance": relevance,
            "count": count
        })
    
    # Generate missing keywords based on common industry terms
    missing_keywords = []
    common_keywords = ["TypeScript", "CI/CD", "Kubernetes", "REST API", "GraphQL", "Scrum"]
    for keyword in common_keywords:
        if keyword not in skills and keyword.lower() not in text.lower():
            missing_keywords.append({
                "keyword": keyword,
                "relevance": "high" if keyword in ["TypeScript", "CI/CD"] else "medium"
            })
    
    return {
        "present": present_keywords,
        "missing": missing_keywords
    }

def generate_recommendations(text: str, skills: List[str]) -> List[str]:
    recommendations = []
    
    # Check for common resume issues
    if len(text.split()) < 100:
        recommendations.append("Your resume seems too short. Consider adding more details about your experience.")
    
    if len(skills) < 5:
        recommendations.append("Consider adding more technical skills to your resume.")
    
    if not re.search(r'\b\d{4}\b', text):
        recommendations.append("Add dates to your work experience and education sections.")
    
    return recommendations

def generate_demo_analysis() -> ResumeAnalysis:
    """Generate demo resume analysis data"""
    demo = ResumeAnalysis(
        ats_score=0.82,
        parse_status={
            "success": True,
            "confidence": 0.95,
            "message": "Demo resume parsed successfully"
        },
        contact_info={
            "name": "John Developer",
            "email": "john.dev@example.com",
            "phone": "(555) 987-6543",
            "location": "Seattle, WA"
        },
        education=[
            {
                "degree": "Master of Computer Science",
                "institution": "University of Washington", 
                "date_range": "2018-2020"
            },
            {
                "degree": "Bachelor of Software Engineering",
                "institution": "California Institute of Technology",
                "date_range": "2014-2018"
            }
        ],
        experience=[
            {
                "title": "Senior Full Stack Developer",
                "company": "Tech Solutions Inc.",
                "date_range": "2020-Present",
                "description": "Led development of enterprise SaaS application. Improved system performance by 60% and reduced cloud costs by 35%."
            },
            {
                "title": "Frontend Developer",
                "company": "Innovative Solutions",
                "date_range": "2018-2020",
                "description": "Developed modern web applications using React, TypeScript and GraphQL. Implemented automated testing reducing bugs by 40%."
            }
        ],
        skills=["JavaScript", "TypeScript", "React", "Node.js", "Python", "AWS", "Docker", "GraphQL", "CI/CD", "Agile"],
        mistakes=[
            {
                "type": "missing_metrics",
                "description": "Consider adding more quantifiable achievements",
                "suggestion": "Include specific metrics like percentages of improvement, cost savings, or revenue generated"
            },
            {
                "type": "technical_skills",
                "description": "Technical skills could be organized better",
                "suggestion": "Group skills by category (frontend, backend, cloud, etc.) for better readability"
            }
        ],
        improvement_suggestions=[
            {
                "category": "content",
                "title": "Enhance your professional summary", 
                "description": "Add a compelling professional summary that highlights your unique value proposition"
            },
            {
                "category": "keywords",
                "title": "Add more industry-specific terms",
                "description": "Include buzzwords relevant to your target roles like 'microservices', 'serverless', or 'cloud-native'"
            }
        ],
        keyword_analysis={
            "present": [
                {"keyword": "JavaScript", "relevance": "high", "count": 3},
                {"keyword": "React", "relevance": "high", "count": 2},
                {"keyword": "Node.js", "relevance": "high", "count": 2},
                {"keyword": "TypeScript", "relevance": "medium", "count": 1}
            ],
            "missing": [
                {"keyword": "REST API", "relevance": "high"},
                {"keyword": "Unit Testing", "relevance": "medium"}
            ]
        }
    )
    
    # Add is_demo flag in the dict conversion
    demo_dict = demo.dict()
    demo_dict["is_demo"] = True
    demo_dict["filename"] = "demo_resume.pdf"
    
    # Convert back to model
    return ResumeAnalysis(**demo_dict)

@app.get("/api/me/resume/analyze")
async def analyze_resume(
    current_user: User = Depends(get_current_user)
):
    # CORS headers for all responses
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    
    try:
        print(f"Analyzing resume for user: {current_user.id} ({current_user.email})")
        
        # Find the most recent resume for this user
        user_dir = Path("uploads/resumes") / str(current_user.id)
        
        if not user_dir.exists():
            print(f"No resume directory found at: {user_dir}")
            return JSONResponse(
                status_code=404, 
                content={"detail": "No resume found. Please upload a resume first."},
                headers=headers
            )
        
        # Get the most recent file
        files = list(user_dir.glob("*"))
        if not files:
            print(f"No resume files found in directory: {user_dir}")
            return JSONResponse(
                status_code=404, 
                content={"detail": "No resume found. Please upload a resume first."},
                headers=headers
            )
        
        # Filter out non-resume files (e.g., extracted text files)
        resume_files = [f for f in files if not f.name.startswith("text_")]
        if not resume_files:
            print(f"No valid resume files found in directory: {user_dir}")
            return JSONResponse(
                status_code=404, 
                content={"detail": "No resume found. Please upload a resume first."},
                headers=headers
            )
        
        most_recent = max(resume_files, key=os.path.getctime)
        print(f"Found most recent resume file: {most_recent}")
        
        # Extract text based on file type
        file_ext = most_recent.suffix.lower()
        print(f"File extension: {file_ext}")
        
        if file_ext in ['.pdf']:
            print("Processing PDF file")
            text = extract_text_from_pdf(most_recent)
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            print("Processing image file")
            text = extract_text_from_image(most_recent)
        elif file_ext in ['.doc', '.docx']:
            print("Processing Word document")
            text = "Word document content placeholder"  # Implement document processing if needed
        else:
            # Look for corresponding text file
            print(f"Unsupported file type: {file_ext}, looking for text extraction")
            text_files = list(user_dir.glob(f"text_*"))
            if text_files:
                most_recent_text = max(text_files, key=os.path.getctime)
                print(f"Found extracted text file: {most_recent_text}")
                with open(most_recent_text, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            else:
                return JSONResponse(
                    status_code=400, 
                    content={"detail": f"Unsupported file type: {file_ext}. Please upload a PDF or image file."},
                    headers=headers
                )
        
        # Check if we got valid text
        if not text or len(text.strip()) < 50:
            print(f"Insufficient text extracted from file, length: {len(text) if text else 0}")
            return JSONResponse(
                status_code=400, 
                content={"detail": "Could not extract sufficient text from the resume. Please upload a text-based file."},
                headers=headers
            )
        
        print(f"Successfully extracted {len(text)} characters of text")
        
        # Parse resume text
        print("Parsing resume text")
        analysis = parse_resume_text(text)
        
        # Add the original filename to the response
        analysis_dict = analysis.dict()
        analysis_dict["filename"] = most_recent.name
        analysis_dict["file_size"] = os.path.getsize(most_recent)
        analysis_dict["file_type"] = file_ext
        analysis_dict["is_demo"] = False
        
        print("Analysis complete, returning results")
        # Return response with CORS headers
        return JSONResponse(
            content=analysis_dict,
            headers=headers
        )
    except Exception as e:
        print(f"ERROR in analyze_resume: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500, 
            content={"detail": f"Error analyzing resume: {str(e)}"},
            headers=headers
        )

@app.post("/api/me/resume/job-match")
async def match_job(
    job_data: JobMatch,
    current_user: User = Depends(get_current_user)
):
    """Match resume to job description"""
    # CORS headers for all responses
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    
    try:
        # Find the most recent resume for this user
        user_dir = Path("uploads/resumes") / str(current_user.id)
        
        if not user_dir.exists():
            raise HTTPException(
                status_code=404, 
                detail="No resume found. Please upload a resume first.",
                headers=headers
            )
        
        # Get the most recent file
        files = list(user_dir.glob("*"))
        if not files:
            raise HTTPException(
                status_code=404, 
                detail="No resume found. Please upload a resume first.",
                headers=headers
            )
        
        most_recent = max(files, key=os.path.getctime)
        
        # Extract text from resume
        file_ext = most_recent.suffix.lower()
        if file_ext in ['.pdf']:
            resume_text = extract_text_from_pdf(most_recent)
        elif file_ext in ['.jpg', '.jpeg', '.png']:
            resume_text = extract_text_from_image(most_recent)
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file_ext}",
                headers=headers
            )
        
        # Extract job description text
        job_text = job_data.job_description or ""
        if job_data.job_title:
            job_text = job_data.job_title + " " + job_text
        
        # Extract keywords from resume
        resume_analysis = parse_resume_text(resume_text)
        resume_skills = resume_analysis.skills
        
        # Extract keywords from job description
        job_keywords = extract_job_keywords(job_text)
        
        # Calculate matching and missing keywords
        matching_keywords = []
        for skill in resume_skills:
            if any(keyword.lower() in skill.lower() or skill.lower() in keyword.lower() for keyword in job_keywords):
                importance = "high" if any(keyword.lower() == skill.lower() for keyword in job_keywords) else "medium"
                matching_keywords.append({"keyword": skill, "importance": importance})
        
        missing_keywords = []
        for keyword in job_keywords:
            if not any(keyword.lower() in skill.lower() or skill.lower() in keyword.lower() for skill in resume_skills):
                importance = "high" if keyword.lower() in job_text.lower().split() else "medium"
                missing_keywords.append({"keyword": keyword, "importance": importance})
        
        # Calculate match percentage
        total_keywords = len(job_keywords)
        matched_count = len(matching_keywords)
        match_percentage = matched_count / total_keywords if total_keywords > 0 else 0.5
        
        # Generate improvement suggestions
        suggestions = generate_job_match_suggestions(job_text, resume_text, missing_keywords)
        
        result = JobMatchResult(
            match_percentage=max(0.4, min(0.95, match_percentage)),  # Constrain between 40-95%
            matching_keywords=matching_keywords,
            missing_keywords=missing_keywords[:5],  # Limit to top 5 missing keywords
            improvement_suggestions=suggestions
        )
        
        # Return response with CORS headers
        return JSONResponse(
            content=result.dict(),
            headers=headers
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error matching job: {str(e)}",
            headers=headers
        )

def extract_job_keywords(job_text: str) -> List[str]:
    """Extract important keywords from job description"""
    # Common technical skills to look for
    common_skills = [
        "Python", "Java", "JavaScript", "TypeScript", "React", "Angular", "Vue", 
        "Node.js", "Express", "Django", "Flask", "Spring", "SQL", "NoSQL", 
        "MongoDB", "AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD",
        "Jenkins", "Git", "REST API", "GraphQL", "Microservices", "Agile", 
        "Scrum", "DevOps", "Machine Learning", "AI", "Data Science", "Analytics",
        "ETL", "Big Data", "Cloud", "Security", "Testing", "UI/UX", "Mobile",
        "Android", "iOS", "Swift", "Kotlin", "C#", "C++", "Go", ".NET"
    ]
    
    # Extract skills mentioned in the job description
    found_skills = []
    for skill in common_skills:
        if skill.lower() in job_text.lower():
            found_skills.append(skill)
    
    # Common soft skills and keywords
    soft_skills = [
        "Communication", "Teamwork", "Problem-solving", "Leadership", 
        "Project management", "Critical thinking", "Attention to detail",
        "Creativity", "Time management", "Adaptability", "Collaboration"
    ]
    
    for skill in soft_skills:
        if skill.lower() in job_text.lower():
            found_skills.append(skill)
    
    # If we found less than 5 skills, add some generic important ones
    if len(found_skills) < 5:
        additional_skills = ["Communication", "Problem-solving", "Teamwork", 
                             "Attention to detail", "Project management"]
        for skill in additional_skills:
            if skill not in found_skills:
                found_skills.append(skill)
                if len(found_skills) >= 10:
                    break
    
    return found_skills

def generate_job_match_suggestions(job_text: str, resume_text: str, missing_keywords: List[dict]) -> List[str]:
    """Generate suggestions to improve job match"""
    suggestions = []
    
    # Suggest adding missing keywords
    if missing_keywords:
        high_importance = [kw["keyword"] for kw in missing_keywords if kw["importance"] == "high"]
        if high_importance:
            suggestions.append(f"Add these critical keywords to your resume: {', '.join(high_importance)}")
        else:
            suggestions.append(f"Consider adding these keywords to your resume: {', '.join([kw['keyword'] for kw in missing_keywords[:3]])}")
    
    # Check for quantifiable achievements
    if not re.search(r'\b\d+%|\d+ percent|increased|decreased|improved|reduced\b', resume_text, re.IGNORECASE):
        suggestions.append("Add quantifiable achievements to demonstrate your impact (e.g., 'improved performance by 40%')")
    
    # Check for education/certification mentions in job
    edu_cert_keywords = ["degree", "bachelor", "master", "certification", "certified", "license"]
    if any(keyword in job_text.lower() for keyword in edu_cert_keywords) and not any(keyword in resume_text.lower() for keyword in edu_cert_keywords):
        suggestions.append("Highlight relevant education or certifications that match job requirements")
    
    # Generic suggestions
    if len(suggestions) < 3:
        additional_suggestions = [
            "Tailor your professional summary to highlight experience relevant to this position",
            "Reorganize your experience section to prioritize skills mentioned in this job description",
            "Use industry-specific terminology that appears in the job description"
        ]
        
        for suggestion in additional_suggestions:
            if suggestion not in suggestions:
                suggestions.append(suggestion)
                if len(suggestions) >= 3:
                    break
    
    return suggestions

@app.post("/api/signup/student", response_model=User)
async def signup_student(user: UserCreate):
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # In production, hash the password
    user_dict = user.dict()
    user_dict["id"] = len(fake_users_db) + 1
    fake_users_db[user.email] = user_dict
    return User(**user_dict)

@app.post("/api/signup/recruiter", response_model=User)
async def signup_recruiter(user: UserCreate):
    if user.email in fake_users_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # In production, hash the password
    user_dict = user.dict()
    user_dict["id"] = len(fake_users_db) + 1
    fake_users_db[user.email] = user_dict
    return User(**user_dict)

@app.post("/api/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        print(f"Login attempt for email: {form_data.username}")  # Debug log
        
        user_data = fake_users_db.get(form_data.username)
        if not user_data:
            print(f"User not found: {form_data.username}")  # Debug log
            raise HTTPException(
                status_code=401,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if user_data.get("password") != form_data.password:
            print(f"Invalid password for user: {form_data.username}")  # Debug log
            raise HTTPException(
                status_code=401,
                detail="Incorrect password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": form_data.username}, expires_delta=access_token_expires
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "full_name": user_data.get("full_name"),
                "user_type": user_data.get("user_type")
            }
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Login error: {str(e)}")  # Debug log
        raise HTTPException(
            status_code=500,
            detail=f"Login failed: {str(e)}"
        )

@app.get("/api/database")
async def view_database():
    """Endpoint to view the current state of the fake database"""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Authorization, Content-Type",
    }
    
    return JSONResponse(
        content={
            "users": fake_users_db,
            "total_users": len(fake_users_db)
        },
        headers=headers
    )

# Add OPTIONS handler for database endpoint
@app.options("/api/database")
async def options_database():
    return Response(
        content="",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type",
            "Access-Control-Max-Age": "86400",
        },
    )

# Create a special route for testing CORS
@app.options("/api/test-cors")
async def test_cors_options():
    return {}

@app.get("/api/test-cors")
async def test_cors():
    return {"message": "CORS is working correctly"}

# Only enable test upload endpoint in debug mode
if DEBUG_MODE:
    @app.post("/api/test-upload")
    async def test_upload(file: UploadFile = File(...)):
        """
        Test endpoint that allows file upload without authentication.
        For development use only.
        """
        # Add CORS headers to response
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        
        try:
            # Create test directory
            test_dir = Path("uploads/test")
            test_dir.mkdir(parents=True, exist_ok=True)
            
            # Validate file type
            if not file.filename:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Missing filename"},
                    headers=headers
                )
                
            file_ext = file.filename.lower().split('.')[-1]
            if file_ext not in ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'txt']:
                return JSONResponse(
                    status_code=400, 
                    content={"detail": "Unsupported file type"},
                    headers=headers
                )
            
            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_{timestamp}.{file_ext}"
            file_path = test_dir / filename
            
            # File size check
            MAX_SIZE = 5 * 1024 * 1024  # 5MB limit for test
            content = await file.read(MAX_SIZE + 1)
            
            if len(content) > MAX_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "File too large (max 5MB)"},
                    headers=headers
                )
            
            # Save file
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            
            # Success response
            return JSONResponse(
                content={
                    "message": "Test upload successful", 
                    "filename": filename,
                    "size": len(content),
                    "content_type": file.content_type
                },
                headers=headers
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"detail": "Server error processing the upload"},
                headers=headers
            )
else:
    # In production, disable the test upload endpoint
    @app.post("/api/test-upload")
    async def test_upload_disabled():
        return JSONResponse(
            status_code=403,
            content={"detail": "This endpoint is disabled in production"}
        )

# Demo applications data
DEMO_APPLICATIONS = [
    {
        "id": 1,
        "job_id": 1,
        "student_id": 1,
        "job_title": "Senior Software Engineer",
        "candidate_name": "Jennifer Anderson",
        "candidate_email": "jennifer.a@example.com",
        "status": "pending",
        "applied_date": "2024-03-29T10:00:00Z",
        "company": "TechCorp Solutions",
        "location": "San Francisco, CA",
        "job_type": "full-time",
        "experience": "5+ years"
    },
    {
        "id": 2,
        "job_id": 2,
        "student_id": 2,
        "job_title": "UX/UI Designer",
        "candidate_name": "Michael Johnson",
        "candidate_email": "michael.j@example.com",
        "status": "accepted",
        "applied_date": "2024-03-28T15:30:00Z",
        "company": "DesignHub Inc",
        "location": "New York, NY",
        "job_type": "full-time",
        "experience": "3+ years"
    },
    {
        "id": 3,
        "job_id": 3,
        "student_id": 3,
        "job_title": "Data Science Intern",
        "candidate_name": "Sarah Chen",
        "candidate_email": "sarah.c@example.com",
        "status": "rejected",
        "applied_date": "2024-03-27T09:15:00Z",
        "company": "DataFlow Analytics",
        "location": "Remote",
        "job_type": "internship",
        "experience": "Student"
    },
    {
        "id": 4,
        "job_id": 1,
        "student_id": 4,
        "job_title": "Senior Software Engineer",
        "candidate_name": "David Wilson",
        "candidate_email": "david.w@example.com",
        "status": "pending",
        "applied_date": "2024-03-29T14:20:00Z",
        "company": "TechCorp Solutions",
        "location": "San Francisco, CA",
        "job_type": "full-time",
        "experience": "7+ years"
    },
    {
        "id": 5,
        "job_id": 2,
        "student_id": 5,
        "job_title": "UX/UI Designer",
        "candidate_name": "Emily Rodriguez",
        "candidate_email": "emily.r@example.com",
        "status": "pending",
        "applied_date": "2024-03-29T16:45:00Z",
        "company": "DesignHub Inc",
        "location": "New York, NY",
        "job_type": "full-time",
        "experience": "4+ years"
    }
]

@app.get("/api/applications/recruiter")
async def get_recruiter_applications():
    """Get all applications for the recruiter"""
    if DEBUG_MODE:
        return DEMO_APPLICATIONS
    # In production, this would fetch from the database
    return []

@app.get("/api/applications")
async def get_student_applications():
    """Get all applications for the current student"""
    if DEBUG_MODE:
        # Return only applications for the current student
        return [app for app in DEMO_APPLICATIONS if app["student_id"] == 2]
    # In production, this would fetch from the database
    return []

# ... rest of the existing code ... 