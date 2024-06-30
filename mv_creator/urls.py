# mv_creator/urls.py

from django.urls import path
from . import views


urlpatterns = [
    path('', views.hello_rest_api, name='hello_rest_api'),
    path('hello', views.hello_rest_api, name='hello_rest_api'),
    path('bye', views.hello_rest_api, name='hello_rest_api'),
]