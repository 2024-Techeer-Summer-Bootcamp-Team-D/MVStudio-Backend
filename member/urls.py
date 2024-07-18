# member/urls.py

from django.urls import path
from .views import MemberSignUpView,MemberDetailView, MemberLoginView, CountryListView



urlpatterns = [
    path('', MemberSignUpView.as_view(), name='member-sign-up'),
    path('/<int:member_id>',MemberDetailView.as_view(), name='member-detail'),
    path('/login', MemberLoginView.as_view(), name='member-login'),
    path('/countries', CountryListView.as_view(), name='countries-list'),
]