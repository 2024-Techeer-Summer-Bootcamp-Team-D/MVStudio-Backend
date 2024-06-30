# app1/api_urls.py

from django.urls import path
from . import views
from .views import hello_rest_api

urlpatterns = [
    path('hello', hello_rest_api, name='hello_rest_api'),
]