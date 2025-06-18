from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserRegistrationAPI, UserLoginAPI # type: ignore
from django.contrib import admin

INSTALLED_APPS = [
    # other apps
    'users',  # Ensure the 'users' app is listed here
]

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/register/', UserRegistrationAPI.as_view()),
    path('api/login/', UserLoginAPI.as_view()),
    path('api-auth/', include('rest_framework.urls')),
]