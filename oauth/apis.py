from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils.translation import gettext_lazy as _

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from oauth.authenticate import generate_access_token, jwt_login
from oauth.mixins import ApiAuthMixin, PublicApiMixin
from member.serializers import RegisterSerializer
import jwt

User = get_user_model()
class UserMeApi(ApiAuthMixin, APIView):
    def delete(self, request, *args, **kwargs):
        """
        현재 로그인 된 유저 삭제
        소셜 로그인 유저는 바로 삭제.
        일반 회원가입 유저는 비밀번호 입력 후 삭제.
        """
        user = request.user
        signup_path = user.profile.signup_path

        if signup_path == "kakao" or signup_path == "google":
            user.delete()
            return Response({
                "message": "Delete user success"
            }, status=status.HTTP_204_NO_CONTENT)

        if not check_password(request.data.get("password"), user.password):
            raise serializers.ValidationError(
                _("passwords do not match")
            )

        user.delete()

        return Response({
            "message": "Delete user success"
        }, status=status.HTTP_204_NO_CONTENT)


class UserCreateApi(PublicApiMixin, APIView):
    def post(self, request, *args, **kwargs):
        """
        회원가입 api

        """
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid(raise_exception=True):
            return Response({
                "message": "Request Body Error"
            }, status=status.HTTP_409_CONFLICT)

        user = serializer.save()

        response = Response(status=status.HTTP_200_OK)
        response = jwt_login(response=response, user=user)
        return response

@method_decorator(ensure_csrf_cookie, name="dispatch")
class LoginApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_description="Log in with username and password",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Password')
            },
            required=['username', 'password']
        ),
        responses={
            200: "Login successful",
            400: "username/password required or wrong password",
            404: "User not found"
        }
    )
    def post(self, request, *args, **kwargs):
        """
        username 과 password를 가지고 login 시도
        key값 : username, password
        """
        username = request.data.get('username')
        password = request.data.get('password')

        if (username is None) or (password is None):
            return Response({
                "message": "username/password required"
            }, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(username=username).first()
        if user is None:
            return Response({
                "message": "유저를 찾을 수 없습니다"
            }, status=status.HTTP_404_NOT_FOUND)
        if not user.check_password(password):
            return Response({
                "message": "wrong password"
            }, status=status.HTTP_400_BAD_REQUEST)

        response = Response(status=status.HTTP_200_OK)
        return jwt_login(response, user)


@method_decorator(csrf_protect, name='dispatch')
class RefreshJWTtoken(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_description="Refresh JWT token",
        responses={
            200: openapi.Response(
                description="New access token",
                examples={
                    'application/json': {
                        'access_token': 'new_access_token'
                    }
                }
            ),
            403: "Authentication credentials were not provided or expired refresh token",
            400: "User not found or inactive"
        }
    )
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refreshtoken')

        if refresh_token is None:
            return Response({
                "message": "Authentication credentials were not provided."
            }, status=status.HTTP_403_FORBIDDEN)

        try:
            payload = jwt.decode(
                refresh_token, settings.REFRESH_TOKEN_SECRET, algorithms=['HS256']
            )
        except:
            return Response({
                "message": "expired refresh token, please login again."
            }, status=status.HTTP_403_FORBIDDEN)

        user = User.objects.filter(id=payload['user_id']).first()

        if user is None:
            return Response({
                "message": "user not found"
            }, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({
                "message": "user is inactive"
            }, status=status.HTTP_400_BAD_REQUEST)

        access_token = generate_access_token(user)

        return Response(
            {
                'access_token': access_token,
            }
        )


@method_decorator(csrf_protect, name='dispatch')
class LogoutApi(PublicApiMixin, APIView):
    @swagger_auto_schema(
        operation_description="Log out and delete refresh token cookie",
        responses={
            202: "Logout success"
        }
    )
    def post(self, request):
        """
        클라이언트 refreshtoken 쿠키를 삭제함으로 로그아웃처리
        """
        response = Response({
            "message": "Logout success"
        }, status=status.HTTP_202_ACCEPTED)
        response.delete_cookie('refreshtoken')

        return response