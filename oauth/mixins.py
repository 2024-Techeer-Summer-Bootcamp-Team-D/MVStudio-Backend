from rest_framework.permissions import IsAuthenticated
from .authenticate import SafeJWTAuthentication
from rest_framework.permissions import IsAuthenticatedOrReadOnly
class ApiAuthMixin:
    authentication_classes = [SafeJWTAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]

class PublicApiMixin:
    authentication_classes = ()
    permission_classes = ()