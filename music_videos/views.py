
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import environ
from member.models import Member
from .models import Genre, Verse
from .serializers import MusicVideoSerializer, VerseSerializer

from datetime import datetime
import re
import logging
import openai

env = environ.Env()
environ.Env.read_env()

OPENAI_API_KEY = env('OPENAI_API_KEY')

class CreateLyricsView(APIView):
    @swagger_auto_schema(
        operation_summary="가사 생성 API",
        operation_description="이 API는 가사를 생성하는 데 사용됩니다.",
        responses={
            201: openapi.Response(
                description="가사 생성 완료",
                examples={
                    "application/json": {
                        "code": "M005",
                        "status": 201,
                        "message": "가사 생성 완료"
                    }
                }
            ),
            400: openapi.Response(
                description="유효하지 않은 데이터입니다.",
                examples={
                    "application/json": {
                        "code": "M005_1",
                        "status": 400,
                        "message": "유효하지 않은 데이터입니다."
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = request.data['subject']
        genres_id = request.data['genres']
        genres = Genre.objects.filter(id__in=genres_id)
        genre_names = [str(genre) for genre in genres]
        genre_names_str = ", ".join(genre_names)
        language = request.data['language']
        vocal = request.data['vocal']

        prompt = (
            f"Create song lyrics based on the keyword '{subject}'. "
            f"The genre should be {genre_names_str}, the language should be {language}, and the vocals should be suitable for {vocal} vocals. "
            f"The song should have 4 verses, each with 4 lines, formatted as follows:\n\n"
            f"[Verse]\nLine 1\nLine 2\nLine 3\nLine 4\n\n"
            f"[Verse 2]\nLine 1\nLine 2\nLine 3\nLine 4\n\n"
            f"[Bridge]\nLine 1\nLine 2\nLine 3\nLine 4\n\n"
            f"[Verse 3]\nLine 1\nLine 2\nLine 3\nLine 4\n"
        )

        try:
            openai.api_key = OPENAI_API_KEY
            response = openai.chat.completions.create(
                model = "gpt-3.5-turbo",
                # model="text-davinci-003",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes song lyrics."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                n=3
            )
            lyrics1 = response.choices[0].message.content
            lyrics2 = response.choices[1].message.content
            lyrics3 = response.choices[2].message.content

            response_data = {
                "lyrics": {
                    "lyrics1": lyrics1,
                    "lyrics2": lyrics2,
                    "lyrics3": lyrics3,
                },
                "code": "M005",
                "status": 201,
                "message": "가사 생성 완료"
            }
            logging.info(f'INFO {client_ip} {current_time} POST /lyrics 201 lyrics created')
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /lyrics 500 {str(e)}')
            return Response({
                "code": "M005_1",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MusicVideo(APIView):
    def post(self,request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        member_id = request.data['member_id']
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            response_data = {
                "code": "P002",
                "status": 404,
                "message": "회원 정보가 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} POST /music_videos 404 does not existing')
            return Response(response_data, status=404)
        data = request.data.copy()






        # lyrics 값을 가져옴
        lyrics = data['lyrics']
        # 벌스별로 나누기 위해 정규 표현식 사용, 그리고 [Verse], [Bridge] 태그 제거
        verses = re.split(r'\[.*?\]\n', lyrics)
        # 빈 문자열 제거
        verses = [verse.strip() for verse in verses if verse.strip()]

        # 뮤직비디오 data
        data = {
            "member_id": data['member_id'],
            "subject": data['subject'],
            "language": data['language'],
            "vocal": data['vocal'],
            "length": 0,
            "cover_image": "url",
            "mv_file": "file_url",
            "genre_ids": [1, 3],
            "instrument_ids": [2, 3],
            "tempo": 1
        }

        # 뮤직비디오 및 벌스 객체 생성
        serializer = MusicVideoSerializer(data=data)
        if serializer.is_valid():
            music_video = serializer.save()
            for idx,verse in enumerate(verses):
                verse_data = {
                    "lyrics" : "verse",
                    'start_time' : 'start_time',
                    'end_time' : 'end_time',
                    'sequence' : 'idx',
                    'mv_id' : serializer.validated_data['id']
                }
                verse_serializer = VerseSerializer(data = verse_data)
                if verse_serializer.is_valid():
                    verse_serializer.save()
