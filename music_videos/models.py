from django.db import models
from member.models import Member


class Genre(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.name
class Instrument(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.name


class MusicVideo(models.Model):
    id = models.AutoField(primary_key=True)
    member_id = models.ForeignKey(Member, on_delete=models.CASCADE, db_column='member_id')
    subject = models.CharField(max_length=200)
    lyrics = models.CharField(max_length=2000)
    genre_id = models.ManyToManyField(Genre)
    instrument_id = models.ManyToManyField(Instrument, null=True)
    tempo = models.CharField(max_length=10)
    language = models.CharField(max_length=100)
    vocal = models.CharField(max_length=100)
    length = models.FloatField()
    cover_image = models.CharField(max_length=1000)
    mv_file = models.CharField(max_length=1000)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.subject

class Verse(models.Model):
    id = models.AutoField(primary_key=True)
    lyrics = models.CharField(max_length=500)
    sequence = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    mv_id = models.ForeignKey(MusicVideo, on_delete=models.CASCADE, db_column='mv_id')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.lyrics
