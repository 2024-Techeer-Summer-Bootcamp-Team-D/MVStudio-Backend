from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager

from .constants import *


class Country(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    @transaction.atomic
    def create_user(self, username, email, password=None, **extra_fields):
        print("Create User by manager")
        if not username:
            raise ValueError('아이디는 필수 항목입니다.')
        if not email:
            raise ValueError('이메일은 필수 항목입니다.')
        if not password:
            raise ValueError('패드워드는 필수 항목입니다.')
        user = self.model(
            username=username,
            email=self.normalize_email(email)
        )
        user.set_password(password)
        user.full_clean()
        user.save()

        return user


class Member(AbstractUser):
    username = models.CharField('username', max_length=150, unique=True)
    email = models.EmailField('email address', unique=True, blank=True)
    name = models.CharField(max_length=50, null=True, blank=True)
    nickname = models.CharField(max_length=50, null=True, blank=True)
    profile_image = models.CharField(max_length=2000, null=True, blank=True)
    comment = models.CharField(max_length=200, null=True, blank=True)
    birthday = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, db_column='country_id', null=True, blank=True)
    youtube_account = models.CharField(max_length=200, null=True, blank=True)
    instagram_account = models.CharField(max_length=200, null=True, blank=True)
    credits = models.IntegerField(null=True, blank=True, default=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    objects = UserManager()

    class Meta:
        swappable = 'AUTH_USER_MODEL'

    def __str__(self):
        return self.username

class KakaoPaymentRequest(models.Model):
    username = models.ForeignKey(Member, to_field='username', on_delete=models.CASCADE)
    credits = models.IntegerField()
    price = models.IntegerField()
    tid = models.CharField(max_length=50, null=True, blank=True)
    status = models.IntegerField(default=0,  choices=PAY_STATUS_CHOICES)
    ready_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
class KakaoPaymentApprovalResult(models.Model):
    payment_request = models.ForeignKey(KakaoPaymentRequest, on_delete=models.PROTECT)
    aid = models.CharField(max_length=50)
    quantity = models.IntegerField()
    payment_type = models.IntegerField(choices=PAY_TYPE_CHOICES)
    # amount
    total_amount = models.IntegerField()
    tax_free_amount = models.IntegerField()
    vat_amount = models.IntegerField(default=0)
    # card_info
    card_info = models.TextField(null=True, blank=True)
    item_name = models.CharField(max_length=100)
    ready_requested_at = models.DateTimeField()
    approved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
