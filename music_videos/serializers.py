# mv_creator/serializers.py
from rest_framework import serializers
from .models import MusicVideo, Genre, Instrument, History, Style
from member.models import Member



class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id', 'name', 'image_url']


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrument
        fields = ['id', 'name', 'image_url']

class StyleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Style
        fields = ['id', 'name', 'image_url']


class MusicVideoSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)
    genres_ids = serializers.PrimaryKeyRelatedField(queryset=Genre.objects.all(), many=True, write_only=True)

    instruments = InstrumentSerializer(many=True, read_only=True)
    instruments_ids = serializers.PrimaryKeyRelatedField(queryset=Instrument.objects.all(), many=True, write_only=True)

    style = StyleSerializer(read_only=True)
    style_id = serializers.PrimaryKeyRelatedField(queryset=Style.objects.all(), write_only=True)

    class Meta:
        model = MusicVideo
        fields = [
            'id', 'username', 'subject', 'language', 'vocal', 'length',
            'cover_image', 'mv_file', 'views', 'created_at', 'updated_at', 'is_deleted',
            'genres', 'genres_ids', 'instruments', 'instruments_ids', 'style', 'style_id', 'tempo', 'lyrics'
        ]

    def create(self, validated_data):
        genres = validated_data.pop('genres_ids')
        instruments = validated_data.pop('instruments_ids')
        style = validated_data.pop('style_id')
        username = validated_data.pop('username')
        user = Member.objects.filter(username=username).first()
        try:
            music_video = MusicVideo.objects.create(**validated_data, style_id=style, username=user)
            music_video.genre_id.set(genres)
            music_video.instrument_id.set(instruments)
        except Exception as e:
            print(str(e))
            return {
                "code": "M005_1",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }
        return music_video

    def update(self, instance, validated_data):
        genres = validated_data.pop('genres', None)
        instruments = validated_data.pop('instruments', None)
        style = validated_data.get('style_id', instance.style_id)

        instance.subject = validated_data.get('subject', instance.subject)
        instance.language = validated_data.get('language', instance.language)
        instance.vocal = validated_data.get('vocal', instance.vocal)
        instance.length = validated_data.get('length', instance.length)
        instance.cover_image = validated_data.get('cover_image', instance.cover_image)
        instance.mv_file = validated_data.get('mv_file', instance.mv_file)
        instance.views = validated_data.get('views', instance.views)
        instance.is_deleted = validated_data.get('is_deleted', instance.is_deleted)
        instance.style_id = style.id
        instance.save()

        if genres is not None:
            instance.genres.set(genres)
        if instruments is not None:
            instance.instruments.set(instruments)

        return instance


class MusicVideoDeleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicVideo
        fields = [
            'id', 'username', 'subject', 'is_deleted'
        ]


class MusicVideoDetailSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()
    instruments = serializers.SerializerMethodField()
    style_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    lyrics = serializers.SerializerMethodField()
    class Meta:
        model = MusicVideo
        fields = [
            'id', 'subject', 'cover_image', 'mv_file', 'lyrics', 'member_name', 'profile_image', 'length', 'views', 'genres', 'instruments', 'style_name', 'language', 'vocal', 'tempo'
        ]
    def get_member_name(self, obj):
        return obj.username.nickname
    def get_style_name(self, obj):
        return obj.style_id.name
    def get_genres(self, obj):
        return [genre.name for genre in obj.genre_id.all()]
    def get_instruments(self, obj):
        if obj.instrument_id.exists():
            return [instrument.name for instrument in obj.instrument_id.all()]
        return []
    def get_profile_image(self, obj):
        return obj.username.profile_image
    def get_lyrics(self, obj):
        lyrics = obj.lyrics
        lyrics = lyrics.replace("[Verse]<br />", "")
        lyrics = lyrics.replace("[Outro]<br />", "")
        lyrics = lyrics.replace("<br />[End]<br /><br />", "")
        return lyrics

class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = History
        fields = '__all__'

class CoverImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = MusicVideo
        fields = ['id', 'cover_image']
