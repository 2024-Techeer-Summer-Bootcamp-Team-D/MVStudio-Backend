from django.urls import path
from .views import *


urlpatterns = [
    path('/<str:username>/daily', DailyChartView.as_view(),
         name='chart-daily'),
    path('/<str:username>/genders', GenderChartView.as_view(),
         name='chart-genders'),
    path('/<str:username>/countries', CountryChartView.as_view(),
         name='chart-countries'),
    path('/<str:username>/ages', AgeChartView.as_view(), name='chart-ages'),
]