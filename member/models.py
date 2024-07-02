from django.db import models

class Member(models.Model):
    id = models.AutoField(primary_key=True)
    login_id = models.CharField(max_length=50, unique=True)
    nickname = models.CharField(max_length=50)
    password = models.CharField(max_length=200)
    age = models.IntegerField()
    sex = models.CharField(max_length=1)
    country = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
