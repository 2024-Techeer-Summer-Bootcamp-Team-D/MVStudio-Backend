from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import BaseUserManager
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
    username = models.CharField(_('username'), max_length=150, unique=True)
    email = models.EmailField(_('email address'), unique=True, blank=True)
    name = models.CharField(max_length=50, null=True, blank=True)
    nickname = models.CharField(max_length=50, null=True, blank=True)
    profile_image = models.CharField(max_length=2000, null=True, blank=True)
    comment = models.CharField(max_length=200, null=True, blank=True)
    birthday = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=1, null=True, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, db_column='country_id', null=True, blank=True)
    youtube_account = models.CharField(max_length=200, null=True, blank=True)
    instagram_account = models.CharField(max_length=200, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    objects = UserManager()

    class Meta:
        swappable = 'AUTH_USER_MODEL'

    def __str__(self):
        return self.username
