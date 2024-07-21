from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .authenticate import SafeJWTAuthentication
class ApiAuthMixin:
    authentication_classes = [SafeJWTAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
class PublicApiMixin:
    authentication_classes = ()
    permission_classes = ()