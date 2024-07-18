from django.db import models
from member.models import Member


class Genre(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    image_url = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return self.name


class Instrument(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    image_url = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return self.name

class Style(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    image_url = models.CharField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    def __str__(self):
        return self.name

class MusicVideoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class MusicVideo(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.ForeignKey(Member, to_field='username', on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    lyrics = models.CharField(max_length=2000)
    genre_id = models.ManyToManyField(Genre, through='MusicVideoGenre')
    instrument_id = models.ManyToManyField(Instrument, through='MusicVideoInstrument', blank=True)
    style_id = models.ForeignKey(Style, on_delete=models.SET_NULL, db_column='style_id', null=True, blank=True)
    tempo = models.CharField(max_length=10)
    language = models.CharField(max_length=100)
    vocal = models.CharField(max_length=100)
    length = models.FloatField()
    cover_image = models.CharField(max_length=1000)
    mv_file = models.CharField(max_length=1000)
    recently_viewed = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    objects = MusicVideoManager()  # is_deleted = False 만 조회
    all_objects = models.Manager()

    def __str__(self):
        return self.subject


class MusicVideoGenre(models.Model):
    music_video = models.ForeignKey(MusicVideo, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('music_video', 'genre')


class MusicVideoInstrument(models.Model):
    music_video = models.ForeignKey(MusicVideo, on_delete=models.CASCADE)
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        unique_together = ('music_video', 'instrument')

class History(models.Model):
    id = models.AutoField(primary_key=True)
    mv_id = models.ForeignKey(MusicVideo, on_delete=models.CASCADE, db_column='mv_id')
    username = models.ForeignKey(Member, to_field='username', on_delete=models.CASCADE)
    current_play_time = models.IntegerField(default=0)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)