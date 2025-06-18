INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'users',
    'jobs',
    'ai'
]

MIDDLEWARE = [
    ...
    'corsheaders.middleware.CorsMiddleware',
]

AUTH_USER_MODEL = 'users.CustomUser'

CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ]
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLES = (
        ('student', 'Student'),
        ('recruiter', 'Recruiter'),
        ('admin', 'Admin'),
    )
    role = models.CharField(max_length=20, choices=ROLES, default='student')
    resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    skills = models.TextField(blank=True)