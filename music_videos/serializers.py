# mv_creator/serializers.py

from rest_framework import serializers
from .models import MusicVideo, Genre, Verse
from django.db import IntegrityError

from rest_framework import serializers
from .models import MusicVideo, Genre, Instrument


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name']


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ['id', 'name']

class VerseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Verse
        fields = ['id', 'lyrics', 'start_time', 'end_time', 'sequence']


class MusicVideoSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    genre_ids = serializers.PrimaryKeyRelatedField(queryset=Genre.objects.all(), many=True, write_only=True,
                                                   source='genres')

    instruments = InstrumentSerializer(many=True, read_only=True)
    instrument_ids = serializers.PrimaryKeyRelatedField(queryset=Instrument.objects.all(), many=True, write_only=True,
                                                        source='instruments')

    class Meta:
        model = MusicVideo
        fields = [
            'id', 'member_id', 'subject', 'language', 'vocal', 'length',
            'cover_image', 'mv_file', 'views', 'created_at', 'updated_at', 'is_deleted',
            'genres', 'genre_ids', 'instruments', 'instrument_ids', 'tempo'
        ]

    def create(self, validated_data):
        genres = validated_data.pop('genres_ids')
        instruments = validated_data.pop('instruments_ids')
        music_video = MusicVideo.objects.create(**validated_data)
        music_video.genres.set(genres)
        music_video.instruments.set(instruments)
        return music_video

    def update(self, instance, validated_data):
        genres = validated_data.pop('genres', None)
        instruments = validated_data.pop('instruments', None)

        instance.subject = validated_data.get('subject', instance.subject)
        instance.language = validated_data.get('language', instance.language)
        instance.vocal = validated_data.get('vocal', instance.vocal)
        instance.length = validated_data.get('length', instance.length)
        instance.cover_image = validated_data.get('cover_image', instance.cover_image)
        instance.mv_file = validated_data.get('mv_file', instance.mv_file)
        instance.views = validated_data.get('views', instance.views)
        instance.is_deleted = validated_data.get('is_deleted', instance.is_deleted)
        instance.save()

        if genres is not None:
            instance.genres.set(genres)
        if instruments is not None:
            instance.instruments.set(instruments)

        return instance