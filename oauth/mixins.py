<<<<<<< Updated upstream
from rest_framework.permissions import IsAuthenticated
from .authenticate import SafeJWTAuthentication
class ApiAuthMixin:
    authentication_classes = [SafeJWTAuthentication]
    permission_classes = [IsAuthenticated]
=======
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from .authenticate import SafeJWTAuthentication
class ApiAuthMixin:
    authentication_classes = [SafeJWTAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]
>>>>>>> Stashed changes

class PublicApiMixin:
    authentication_classes = ()
    permission_classes = ()