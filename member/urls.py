# mv_creator/urls.py

from django.urls import path
from .views import MemberSignUpView,MemberDetailView



urlpatterns = [
    path('', MemberSignUpView.as_view(), name='member-sign-up'),
    path('<int:member_id>/',MemberDetailView.as_view(), name='member-detail')
]