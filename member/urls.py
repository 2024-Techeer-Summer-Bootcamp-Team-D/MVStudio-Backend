# member/urls.py

from django.urls import path
from .views import *
from .callback import *


urlpatterns = [
    path('/sign-up', UserCreateApi.as_view(), name='member-create'),
    path('/login', LoginApi.as_view(), name='login'),
    path('/logout', LogoutApi.as_view(), name='login'),
    path('/countries', CountryListView.as_view(), name='countries-list'),
    path('/refresh', RefreshJWTtoken.as_view(), name='member-refresh'),
    path('/details/<str:username>', MemberDetailView.as_view(), name='member-detail'),
    path('/payments', KakaoPayment.as_view(), name='kakao-pay-req'),
    path('/payments/callback/<int:pk>/cancel', KakaoPayCancelCallbackAPIView.as_view(), name='kakao-pay-cancel'),
    path('/payments/callback/<int:pk>/fail', KakaoPayFailCallbackAPIView.as_view(), name='kakao-pay-fail'),
    path('/payments/callback/<int:pk>/success', KakaoPaySuccessCallbackAPIView.as_view(), name='kakao-pay-success'),

]