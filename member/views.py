# views.py

from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import Member
from .serializers import MemberSerializer, MemberDetailSerializer, MemberLoginSerializer

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MemberSignUpView(APIView):
    @swagger_auto_schema(
        operation_summary="회원가입 API",
        operation_description="이 API는 신규 사용자를 등록하는 데 사용됩니다.",
        request_body=MemberSerializer,
        responses={
            201: openapi.Response(
                description="회원가입 완료",
                examples={
                    "application/json": {
                        "code": "M001",
                        "status": 201,
                        "message": "회원가입 완료"
                    }
                }
            ),
            400: openapi.Response(
                description="회원가입 실패",
                examples={
                    "application/json": {
                        "code": "M002",
                        "status": 400,
                        "message": "이미 존재하는 로그인 ID입니다."
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            try:
                serializer.save()
                response_data = {
                    "code": "A001",
                    "status": 201,
                    "message": "회원가입 완료"
                }
                logger.info(f'INFO {client_ip} {current_time} POST /members 201 signup success')
                return Response(response_data, status=201)
            except serializers.ValidationError as e:
                response_data = {
                    "code": "A002",
                    "status": 400,
                    "message": "이미 존재하는 로그인 ID입니다."
                }
                logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 already existing')
                return Response(response_data, status=400)
        logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 signup failed')
        return Response(serializer.errors, status=400)


class MemberDetailView(APIView):
    @swagger_auto_schema(
        operation_summary="회원 정보 수정 API",
        operation_description="이 API는 특정 회원의 정보를 수정하는 데 사용됩니다.",
        request_body=MemberDetailSerializer,
        responses={
            200: openapi.Response(
                description="회원 정보 수정 완료",
                examples={
                    "application/json": {
                        "code": "P003",
                        "status": 200,
                        "message": "회원 정보 수정 완료"
                    }
                }
            ),
            404: openapi.Response(
                description="회원 정보가 없습니다.",
                examples={
                    "application/json": {
                        "code": "P002",
                        "status": 404,
                        "message": "회원 정보가 없습니다."
                    }
                }
            ),
            400: openapi.Response(
                description="유효하지 않은 데이터입니다.",
                examples={
                    "application/json": {
                        "code": "P004",
                        "status": 400,
                        "message": "유효하지 않은 데이터입니다."
                    }
                }
            ),
        }
    )
    def patch(self, request, member_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            response_data = {
                "code": "P002",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} PATCH /members 404 does not existing')
            return Response(response_data, status=404)
        serializer = MemberDetailSerializer(instance=member, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            response_data = {
                "code": "P003",
                "status": 200,
                "message": "회원 정보 수정 완료"
            }
            logger.info(f'INFO {client_ip} {current_time} PATCH /members/{member_id} 200 update success')
            return Response(response_data, status=200)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MemberLoginView(APIView):
    @swagger_auto_schema(
        operation_summary="로그인 API",
        operation_description="이 API는 사용자 로그인을 처리하는 데 사용됩니다.",
        request_body=MemberLoginSerializer,
        responses={
            200: openapi.Response(
                description="로그인 성공",
                examples={
                    "application/json": {
                        "code": "A002",
                        "status": 201,
                        "message": "로그인 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="로그인 실패",
                examples={
                    "application/json": {
                        "code": "L002",
                        "status": 400,
                        "message": "로그인 실패"
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = MemberLoginSerializer(data=request.data)
        if serializer.is_valid():
            login_id = serializer.validated_data['login_id']
            member = Member.objects.get(login_id=login_id)
            response_data = {
                "code": "L001",
                "status": 200,
                "message": "로그인 성공"
            }
            logger.info(f'INFO {client_ip} {current_time} POST /members/login 200 login success')
            return Response(response_data, status=200)
        response_data = {
            "code": "L002",
            "status": 400,
            "message": "로그인 실패"
        }
        logger.warning(f'WARNING {client_ip} {current_time} POST /members/login 400 login failed')
        return Response(response_data, status=400)