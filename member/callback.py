from urllib.parse import parse_qs

from .constants import PAY_STATUS_FAIL
from .payment import KakaoPayClient
from rest_framework.views import APIView
from .models import KakaoPaymentRequest
from django.shortcuts import redirect
from django.conf import settings

from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class KakaoPayFailCallbackAPIView(APIView):
    permission_classes = [AllowAny, ]

    def get(self, request, pk):
        try:
            payment_req = KakaoPaymentRequest.objects.get(id=pk)
            payment_req.status = PAY_STATUS_FAIL

            payment_req.save()

            response_data = {
                'message': "결제가 실패하였습니다. 다시 시도해 주세요."
            }
            redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=fail"
            response = redirect(redirect_uri)
            return response

        except KakaoPaymentRequest.DoesNotExist:
            Response("Not Found")


class KakaoPayCancelCallbackAPIView(APIView):
    permission_classes = [AllowAny, ]

    def get(self, request, pk):
        kakao_pay = KakaoPayClient()

        try:
            payment_req = KakaoPaymentRequest.objects.get(id=pk)

            success, status = kakao_pay.cancel(payment_req)

            if success:
                redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=fail"
                response = redirect(redirect_uri)
                return response
            else:
                redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=fail"
                response = redirect(redirect_uri)
                return response
        except KakaoPaymentRequest.DoesNotExist:
            return Response("Not Found")


class KakaoPaySuccessCallbackAPIView(APIView):
    permission_classes = [AllowAny, ]

    def get(self, request, pk):
        kakao_pay = KakaoPayClient()
        query_params = request.META['QUERY_STRING']
        params = parse_qs(query_params)
        pg_token = params["pg_token"][0]


        try:
            payment_req = KakaoPaymentRequest.objects.get(id=pk)

            success, status = kakao_pay.approve(pg_token, payment_req)

            if success:
                redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=success"
                response = redirect(redirect_uri)
                return response
            else:
                redirect_uri = settings.BASE_FRONTEND_URL + f"payment?status=fail"
                response = redirect(redirect_uri)
                return response

        except KakaoPaymentRequest.DoesNotExist:
            return Response("Not Found")