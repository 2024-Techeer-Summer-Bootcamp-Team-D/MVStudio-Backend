from django.urls import path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf.urls.static import static
from django.conf import settings

schema_view = get_schema_view(
    openapi.Info(
        title="MVStudio API",
        default_version='v1',
        description="MVStudio API 문서",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('swagger.<format>', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path("api/v1", include([
        path("/music-videos", include('music_videos.urls')),
        path("/members", include('member.urls')),
        path("/charts", include('charts.urls')),
        path("/oauth", include('oauth.urls')),
    ])),

]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)