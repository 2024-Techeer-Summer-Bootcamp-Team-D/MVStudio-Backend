from django.db import models

class Member(models.Model):
    id = models.AutoField(primary_key=True)
    login_id = models.CharField(max_length=50, unique=True)
    profile_image = models.CharField(max_length=2000, null=True)
    comment = models.CharField(max_length=200, null=True)
    nickname = models.CharField(max_length=50)
    password = models.CharField(max_length=200)
    birthday = models.DateField()
    sex = models.CharField(max_length=1)
    country = models.CharField(max_length=50)
    youtube_account = models.CharField(max_length=200, null=True)
    instagram_account = models.CharField(max_length=200, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
