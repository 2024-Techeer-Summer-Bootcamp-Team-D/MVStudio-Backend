from django.db import models
from member.models import Member


class AbstractBaseModel(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        abstract = True


class Genre(AbstractBaseModel):
    name = models.CharField(max_length=100, unique=True)
    image_url = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


class Instrument(AbstractBaseModel):
    name = models.CharField(max_length=100, unique=True)
    image_url = models.CharField(max_length=1000)

    def __str__(self):
        return self.name


class MusicVideoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class MusicVideo(AbstractBaseModel):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, db_column='member_id')
    subject = models.CharField(max_length=200)
    lyrics = models.CharField(max_length=2000)
    genres = models.ManyToManyField(Genre, through='MusicVideoGenre')
    instruments = models.ManyToManyField(Instrument, through='MusicVideoInstrument', blank=True)
    tempo = models.CharField(max_length=10)
    language = models.CharField(max_length=100)
    vocal = models.CharField(max_length=100)
    length = models.FloatField()
    cover_image = models.CharField(max_length=1000)
    mv_file = models.CharField(max_length=1000)
    recently_viewed = models.IntegerField(default=0)
    views = models.IntegerField(default=0)

    objects = MusicVideoManager()
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


class History(AbstractBaseModel):
    mv = models.ForeignKey(MusicVideo, on_delete=models.CASCADE, db_column='mv_id')
    member = models.ForeignKey(Member, on_delete=models.CASCADE, db_column='member_id')
    current_play_time = models.IntegerField(default=0)