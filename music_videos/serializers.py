# mv_creator/serializers.py

from rest_framework import serializers
from .models import MusicVideo
from django.db import IntegrityError

class CreateLyricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicVideo
        fields = ['subject', 'genre_id', 'language', 'vocal']
        extra_kwargs = {
            'member_id': {'write_only': True}
        }

    def create(self, validated_data):
        try:
            mv = MusicVideo.objects.create(
                subject=validated_data['subject'],
                genre=validated_data['genre'],
                language=validated_data['language'],
                vocal=validated_data['vocal'],
            )
            return mv
        except IntegrityError as e:
            raise serializers.ValidationError({"member_id": "This member_id is not valid."})


class MusicVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicVideo
        fields = ['member_id','subject', 'genre', 'vocal','lyrics']
        extra_kwargs = {
            'member_id': {'write_only': True}
        }