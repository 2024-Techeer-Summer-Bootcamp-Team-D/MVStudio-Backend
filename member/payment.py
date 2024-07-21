from .models import KakaoPaymentApprovalResult, KakaoPaymentRequest
import requests
from django.conf import settings
from django.db import transaction, DatabaseError
from member.constants import PAY_STATUS_CANCEL, PAY_STATUS_ERROR, PAY_STATUS_SUCCESS, PAY_TYPE
import json
from django.contrib.auth import get_user_model

User = get_user_model()


class KakaoPayClient(object):
    # BASE_URL = "http://mvstudio.pro:8000/api/v1/members/"
    BASE_URL = "http://localhost:8000/api/v1/members/"

    ADMIN_KEY = settings.KAKAO_APP_ADMIN_KEY
    READY_URL = 'https://open-api.kakaopay.com/online/v1/payment/ready'
    APPROVE_URL = 'https://open-api.kakaopay.com/online/v1/payment/approve'
    CANCEL_URL = 'https://open-api.kakaopay.com/online/v1/payment/cancel'
    cid = settings.CID

    headers = {
        "Authorization": "SECRET_KEY " + f"{ADMIN_KEY}",
        "Content-type": "application/json",
    }

    def ready(self, user, credits, price):
        try:
            with transaction.atomic():
                payment_req = KakaoPaymentRequest.objects.create(
                    username=user, credits=credits, price=price)

                req_obj_id = payment_req.id

                params = {
                    "cid": f"{self.cid}",    # 테스트용 코드
                    "partner_order_id": f"{payment_req.pk}",     # 주문번호
                    "partner_user_id": f"{user.pk}",    # 유저 아이디
                    "item_name": "credits",        # 구매 물품 이름
                    "quantity": f"{credits}",                # 구매 물품 수량
                    "total_amount": f"{price}",  # 구매 물품 가격
                    "tax_free_amount": "100",         # 구매 물품 비과세
                    "approval_url": self.BASE_URL + f"payments/callback/{req_obj_id}/success",
                    "cancel_url": self.BASE_URL + f"payments/callback/{req_obj_id}/cancel",
                    "fail_url": self.BASE_URL + f"payments/callback/{req_obj_id}/fail",
                }
                params = json.dumps(params)

                res = requests.post(
                    self.READY_URL, headers=self.headers, data=params)
                if res.status_code == 200:
                    res_json = res.json()
                    tid = res_json.pop('tid')
                    created_at = res_json.pop('created_at')

                    res_json.pop("next_redirect_mobile_url")
                    res_json.pop("ios_app_scheme")

                    payment_req.tid = tid
                    payment_req.ready_requested_at = created_at

                    payment_req.save()

                    return True, res_json
                else:
                    return False, "fail"

        except DatabaseError as e:
            success = False
            return success, str(e)

    def cancel(self, payment_req):
        params = {
            "cid": f"{self.cid}",
            "tid": f"{payment_req.tid}"
        }
        params = json.dumps(params)

        res = requests.post(
            self.CANCEL_URL, headers=self.headers, data=params)

        if res.status_code == 200:
            res_json = res.json()

            status = res_json.get('status')
            if status == "QUIT_PAYMENT":
                payment_req.status = PAY_STATUS_CANCEL
                payment_req.save()

                return True, "결제가 취소되었습니다."
            else:
                payment_req.status = PAY_STATUS_ERROR
                payment_req.save()

                return False, status

    def approve(self, pg_token, payment_req):
        params = {
            "cid": f"{self.cid}",
            "tid": f"{payment_req.tid}",
            "partner_order_id": f"{payment_req.pk}",     # 주문번호
            "partner_user_id": f"{payment_req.username.pk}",    # 유저 아이디
            "pg_token": f"{pg_token}"
        }
        params = json.dumps(params)

        res = requests.post(
            self.APPROVE_URL, headers=self.headers, data=params)

        res_json = res.json()

        if res.status_code == 200:

            aid = res_json.get('aid')
            payment_type = res_json.get('payment_method_type')
            item_name = res_json.get('item_name')
            quantity = res_json.get('quantity')

            amount = res_json.get('amount')
            total_amount = amount.get('total')
            tax_free_amount = amount.get('tax_free')
            vat_amount = amount.get('vat')

            card_info = amount.get('card_info')

            if not card_info == None:
                card_info = str(card_info)

            ready_requested_at = res_json.get('created_at')
            approved_at = res_json.get('approved_at')

            with transaction.atomic():
                KakaoPaymentApprovalResult.objects.create(aid=aid, quantity=quantity , payment_type=PAY_TYPE[payment_type], total_amount=total_amount, tax_free_amount=tax_free_amount,
                                                             vat_amount=vat_amount, card_info=card_info, item_name=item_name, ready_requested_at=ready_requested_at, approved_at=approved_at, payment_request=payment_req)

                request_user = payment_req.username
                user = User.objects.filter(username=request_user).first()
                user.credits += quantity

                payment_req.status = PAY_STATUS_SUCCESS
                payment_req.save()

                return True, "결제가 완료되었습니다."

        else:
            extras = res_json.get('extras')
            message = extras.get('method_result_message')

            payment_req.status = PAY_STATUS_ERROR
            payment_req.save()

            return False, message