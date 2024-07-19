# member/urls.py

from django.urls import path
from .views import *


urlpatterns = [
    path('/sign-up', UserCreateApi.as_view(), name='member-create'),
    path('/login', LoginApi.as_view(), name='login'),
    path('/logout', LogoutApi.as_view(), name='login'),
    path('/countries', CountryListView.as_view(), name='countries-list'),
    path('/refresh', RefreshJWTtoken.as_view(), name='member-refresh'),
    path('/details/<str:username>', MemberDetailView.as_view(), name='member-detail'),
    path('/<str:username>/graphs/daily', MemberDailyGraphView.as_view(),
         name='member-graph-daily'),
    path('/<str:username>/graphs/genders', MemberGenderGraphView.as_view(),
         name='member-graph-genders'),
    path('/<str:username>/graphs/countries', MemberCountryGraphView.as_view(),
         name='member-graph-countries'),
    path('/<str:username>/graphs/ages', MemberAgeGraphView.as_view(), name='member-graph-ages'),
]