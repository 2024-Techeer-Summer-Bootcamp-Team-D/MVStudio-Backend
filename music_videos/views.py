
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import environ
from member.models import Member
from .models import Genre, Verse
from .serializers import MusicVideoSerializer, VerseSerializer, GenreSerializer, InstrumentSerializer

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
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'subject': openapi.Schema(type=openapi.TYPE_STRING, description='가사의 주제'),
                'genres': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='장르 ID 목록'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='언어'),
                'vocal': openapi.Schema(type=openapi.TYPE_STRING, description='보컬 유형'),
            },
            required=['subject', 'genres', 'language', 'vocal']
        ),
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

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'member_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='회원 ID'),
                'subject': openapi.Schema(type=openapi.TYPE_STRING, description='가사의 주제'),
                'genres_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='장르 ID 목록'),
                'instruments_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='악기 ID 목록'),
                'tempo': openapi.Schema(type=openapi.TYPE_STRING, description='템포 유형'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='언어'),
                'vocal': openapi.Schema(type=openapi.TYPE_STRING, description='보컬 유형'),
                'lyrics': openapi.Schema(type=openapi.TYPE_STRING, description='가사')
            },
            required=['member_id', 'subject', 'genres_ids', 'instruments_ids', 'tempo_id', 'vocal', 'lyrics']
        )
    )
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
            "genres_ids": data['genres_ids'],
            "instruments_ids": data['instruments_ids'],
            "tempo": data['tempo']
        }

        print(verses)
        # 뮤직비디오 및 벌스 객체 생성
        serializer = MusicVideoSerializer(data=data)
        if serializer.is_valid():
            print("ok")
            music_video = serializer.save()
            # for idx,verse in enumerate(verses):
            #     verse_data = {
            #         "lyrics" : "verse",
            #         'start_time' : 'start_time',
            #         'end_time' : 'end_time',
            #         'sequence' : 'idx',
            #         'mv_id' : serializer.validated_data['id']
            #     }
            #     verse_serializer = VerseSerializer(data = verse_data)
            #     if verse_serializer.is_valid():
            #         verse_serializer.save()

            response_data = {
                "lyrics": serializer.validated_data['id'],
                "code": "M005",
                "status": 201,
                "message": "가사 생성 완료"
            }
            logging.info(f'INFO {client_ip} {current_time} POST /music_videos 201 music_video created')
            return Response(response_data, status=status.HTTP_201_CREATED)

class GenreListView(APIView):
    @swagger_auto_schema(
        operation_summary="장르 리스트 조회 API",
        operation_description="이 API는 사용자가 뮤직비디오 생성 시 장르를 선택할 수 있도록 장르 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="장르 리스트 조회 성공",
                examples={
                    "application/json": {
                        "code": "M005",
                        "status": 200,
                        "message": "장르 리스트 조회 성공",
                        "data": {
                            "name": "string",
                            "code": "P003",
                            "HTTPstatus": 200,
                            "message": "국가 리스트 조회 성공"
                        }
                    }
                }
            ),
            500: openapi.Response(
                description="장르 리스트를 불러올 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M005_1",
                        "status": 500,
                        "message": "장르 리스트를 불러올 수 없습니다."
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            genres = Genre.objects.all()
            serializer = GenreSerializer(genres, many=True)
            response_data = {
                "code": "M005",
                "status": 200,
                "message": "장르 리스트 조회 성공",
                "data": serializer.data
            }
            logging.info(f'INFO {client_ip} {current_time} GET /genre_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M005_1",
                "status": 500,
                "message": "장르 리스트를 불러올 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /genre_list 500 failed')
            return Response(response_data, status=500)