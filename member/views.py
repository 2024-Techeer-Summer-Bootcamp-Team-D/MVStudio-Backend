from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import logging
from .serializers import MemberSerializer
from datetime import datetime
from drf_yasg.utils import swagger_auto_schema


logger = logging.getLogger(__name__)

class SignUpView(APIView):
    
    @swagger_auto_schema(
        request_body=MemberSerializer,
        responses={
            201: '회원가입 완료',
            400: '회원가입 실패'
        }
    )
    
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        serializer = MemberSerializer(data=request.data)
        if serializer.is_valid():
            response_data = serializer.save()
            if response_data == {
                "code": "M001",
                "status": 201,
                "message": "회원가입 완료"
            }:
                logger.info(f'INFO {client_ip} {current_time} POST /members 201 signup success')
                return Response(response_data, status=201)
            else:
                logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 already existing')
                return Response(response_data, status=400)
        logger.warning(f'WARNING {client_ip} {current_time} POST /members 400 signup failed')
        return Response(serializer.errors, status=400)
