from rest_framework.permissions import IsAuthenticated
from .authenticate import SafeJWTAuthentication
class ApiAuthMixin:
    authentication_classes = [SafeJWTAuthentication]
    permission_classes = [IsAuthenticated]

class PublicApiMixin:
    authentication_classes = ()
    permission_classes = ()