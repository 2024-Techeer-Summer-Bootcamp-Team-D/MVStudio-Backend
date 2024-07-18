# member/urls.py

from django.urls import path
from .views import *


urlpatterns = [
    path('sign-up', UserCreateApi.as_view(), name='memeber-create'),
    path('login', LoginApi.as_view(), name='login'),
    path('logout', LogoutApi.as_view(), name='login'),
    path('<int:member_id>', MemberDetailView.as_view(), name='member-detail'),
    path('countries', CountryListView.as_view(), name='countries-list'),
    path('refresh', RefreshJWTtoken.as_view(), name='memeber-refresh'),
]