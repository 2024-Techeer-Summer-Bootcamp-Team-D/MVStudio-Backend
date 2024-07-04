# mv_creator/serializers.py

from rest_framework import serializers
from .models import MusicVideo
from django.db import IntegrityError

class CreateLyricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicVideo
        fields = ['member_id', 'subject', 'length', 'cover_image', 'mv_file', 'views']
        extra_kwargs = {
            'member_id': {'write_only': True}
        }

    def create(self, validated_data):
        try:
            mv = MusicVideo.objects.create(
                member_id=validated_data['member_id'],
                subject=validated_data['subject'],
                length=validated_data['length'],
                cover_image=validated_data['cover_image'],
                mv_file=validated_data['mv_file'],
                views=validated_data['views']
            )
            return mv
        except IntegrityError as e:
            raise serializers.ValidationError({"member_id": "This member_id is not valid."})