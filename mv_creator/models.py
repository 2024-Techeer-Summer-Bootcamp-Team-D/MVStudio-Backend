from django.db import models
from member.models import Member

class MusicVideo(models.Model):
    id = models.AutoField(primary_key=True)
    member_id = models.ForeignKey(Member, on_delete=models.CASCADE, db_column='member_id')
    subject = models.CharField(max_length=200)
    length = models.IntegerField()
    cover_image = models.CharField(max_length=1000)
    mv_file = models.CharField(max_length=1000)
    views = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)