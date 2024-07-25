from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.conf import settings
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model

from member.models import Member
from .models import Genre, Instrument, MusicVideo, History, Style
from .serializers import GenreSerializer, InstrumentSerializer, MusicVideoDetailSerializer, MusicVideoDeleteSerializer, StyleSerializer

from .tasks import suno_music, create_video, mv_create
from celery import group, chord
from celery.result import AsyncResult

from datetime import datetime
import logging
import openai
import re
import json
from django.db.models import Case, When, Q

from elasticsearch_dsl.query import MultiMatch
from .documents import MusicVideoDocument
from oauth.mixins import ApiAuthMixin

User = get_user_model()
logger = logging.getLogger(__name__)

class CreateLyricsView(ApiAuthMixin, APIView):
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
                description="가사 생성 성공",
                examples={
                    "application/json": {
                        "code": "M007",
                        "status": 201,
                        "message": "가사 생성 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="필수 파라미터 누락",
                examples={
                    "application/json": {
                        "code": "M007_1",
                        "status": 400,
                        "message": "필수 조건이 누락되었습니다."
                    }
                }
            ),
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)

        try:
            subject = request.data['subject']
            genres_id = request.data['genres']
            genres = Genre.objects.filter(id__in=genres_id)
            genre_names = [str(genre) for genre in genres]
            genre_names_str = ", ".join(genre_names)
            language = request.data['language']
            vocal = request.data['vocal']

            if not subject or not genres_id or not language or not vocal:
                response_data = {
                    "code": "M007_1",
                    "status": 400,
                    "message": "필수 조건이 누락되었습니다."
                }
                logger.error(f'{client_ip} POST /music-videos/lyrics 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            prompt = (
                f"Create song lyrics based on the keyword '{subject}'. "
                f"The genre should be {genre_names_str}, the language should be {language}, and the vocals should be suitable for {vocal} vocals. "
                f"The song should have 2 verses, each with 4 lines. Each line should be detailed and contain one sentence per line (very important!!). Each line should vividly describe a specific situation or emotion. followed by English translations of each verse, formatted as follows:\n\n"
                f"---(Original Lyrics)---<br /><br />"
                f"[Verse]<br />Line 1<br />Line 2<br />Line 3<br />Line 4<br /><br />"
                f"[Outro]<br />Line 1<br />Line 2<br />Line 3<br />Line 4<br /><br />"
                f"[End]<br /><br />"
                
                f"---(English Translation)---<br /><br />"
                f"[Verse]<br />Line 1<br />Line 2<br />Line 3<br />Line 4<br /><br />"
                f"[Outro]<br />Line 1<br />Line 2<br />Line 3<br />Line 4<br /><br />"
                f"[End]<br /><br />"
            )

            openai.api_key = settings.OPENAI_API_KEY
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system",
                     "content": "You are a helpful assistant that writes song lyrics and provides translations."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                n=3
            )

            # 가사 추출
            def extract_lyrics(content):
                def extract_part(text, start_marker, end_marker):
                    start_idx = text.find(start_marker)
                    if start_idx == -1:
                        return ""
                    start_idx += len(start_marker)
                    end_idx = text.find(end_marker, start_idx)
                    if end_idx == -1:
                        # end_marker가 없는 경우, 텍스트 끝에 end_marker를 추가
                        text += end_marker
                        end_idx = text.find(end_marker, start_idx)
                    end_idx += len(end_marker)
                    return text[start_idx:end_idx]

                original_lyrics = extract_part(content, "---(Original Lyrics)---<br /><br />", "[End]<br /><br />")
                translation_lyrics = extract_part(content, "---(English Translation)---<br /><br />",
                                                  "[End]<br /><br />")
                return original_lyrics, translation_lyrics

            # print(f"0번째 가사 : {response.choices[0].message.content}")
            # print(f"1번째 가사 : {response.choices[1].message.content}")
            # print(f"2번째 가사 : {response.choices[2].message.content}")

            lyrics1_ori, lyrics1_eng = extract_lyrics(response.choices[0].message.content)
            lyrics2_ori, lyrics2_eng = extract_lyrics(response.choices[1].message.content)
            lyrics3_ori, lyrics3_eng = extract_lyrics(response.choices[2].message.content)

            response_data = {
                "lyrics_ori": [
                    lyrics1_ori,
                    lyrics2_ori,
                    lyrics3_ori,
                ],
                "lyrics_eng": [
                    lyrics1_eng,
                    lyrics2_eng,
                    lyrics3_eng,
                ],
                "code": "M007",
                "status": 201,
                "message": "가사 생성 성공"
            }
            logger.info(f'{client_ip} POST /music-videos/lyrics 201 lyrics created')
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'{client_ip} POST /music-videos/lyrics 500 {str(e)}')
            return Response({
                "code": "M007_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MusicVideoView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 생성 API",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'subject': openapi.Schema(type=openapi.TYPE_STRING, description='가사의 주제'),
                'genres_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='장르 ID 목록'),
                'instruments_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='악기 ID 목록'),
                'style_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='영상 스타일 ID'),
                'tempo': openapi.Schema(type=openapi.TYPE_STRING, description='템포 유형'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='언어'),
                'vocal': openapi.Schema(type=openapi.TYPE_STRING, description='보컬 유형'),
                'lyrics': openapi.Schema(type=openapi.TYPE_STRING, description='가사'),
                'lyrics_eng': openapi.Schema(type=openapi.TYPE_STRING, description='가사 번역')
            },
            required=['subject', 'genres_ids', 'instruments_ids', 'style_id', 'tempo', 'language', 'vocal', 'lyrics', 'lyrics_eng']
        ),
        responses={
            201: openapi.Response(
                description="뮤직비디오 생성 성공",
                examples={
                    "application/json": {
                        "code": "M002",
                        "status": 201,
                        "message": "뮤직비디오 생성 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="필수 파라미터 누락",
                examples={
                    "application/json": {
                        "code": "M002_1",
                        "status": 400,
                        "message": "필수 조건이 누락되었습니다."
                    }
                }
            ),
        }
    )
    def post(self,request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            # Request Parameter 값 가져오기
            username = request.user.username
            subject = request.data['subject']
            vocal = request.data['vocal']
            tempo = request.data['tempo']
            language = request.data['language']
            lyrics = request.data['lyrics']
            lyrics_eng = request.data['lyrics_eng']

            # 장르 쉼표로 구분하여 name 리스트 만들기
            genres_ids = request.data['genres_ids']
            genres = Genre.objects.filter(id__in=genres_ids)
            genre_names = [str(genre) for genre in genres]
            genre_names_str = ", ".join(genre_names)

            # 악기 쉼표로 구분하여 name 리스트 만들기
            instruments_ids = request.data['instruments_ids']
            instruments = Instrument.objects.filter(id__in=instruments_ids)
            instruments_names = [str(instrument) for instrument in instruments]
            instruments_str = ", ".join(instruments_names)

            # 스타일 name 값 가져오기
            style_id = request.data['style_id']
            style = Style.objects.get(id=style_id)
            style_name = str(style)

            # 필수 조건 예외 처리
            if not subject or not vocal or not tempo or not language or not genres_ids  or not lyrics or not style_id or not lyrics_eng:
                response_data = {
                    "code": "M002_1",
                    "status": 400,
                    "message": "필수 조건이 누락되었습니다."
                }
                logger.error(f'{client_ip} POST /music-videos 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # 텍스트를 줄 단위로 나누기
            lines = lyrics_eng.strip().split('<br />')

            # [Verse]와 같은 태그를 제외하고 저장, 그리고 모든 기호 제거
            filtered_lines = [
                re.sub(r'[^A-Za-z0-9\s]', '', re.sub(r'\[.*?\]', '', line))
                for line in lines if not line.startswith('[') and line.strip()
            ]

            # 뮤직 생성 task
            music_task = suno_music.s(genre_names_str, instruments_str, tempo, vocal, lyrics, subject)

            # 비디오 생성 task
            video_tasks = group(
                create_video.s(line, style_name) for line in filtered_lines
            )

            # 뮤직비디오 생성 task
            music_video_task = chord(
                header=[music_task] + video_tasks.tasks,
                body=mv_create.s(client_ip, current_time, subject, language, vocal, lyrics, genres_ids, instruments_ids,
                                 tempo, username, style_id)
            )
            task_id = music_video_task.apply_async().id

            response_data = {
                "code": "M002",
                "status": 201,
                "message": "뮤직비디오 생성 요청 성공",
                "task_id": task_id
            }
            logger.info(f'{client_ip} PATCH /music-videos 201 music video created')
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'{client_ip} POST /music-videos 500 {str(e)}')
            return Response({
                "code": "M002_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_summary="뮤직비디오 목록 조회 API",
        operation_description="모든 뮤직비디오 목록을 조회합니다. 정렬 및 페이지네이션 기능을 지원합니다.",
        manual_parameters=[
            openapi.Parameter(
                'sort',
                openapi.IN_QUERY,
                description="정렬 기준 (예: views, created_at 등)",
                type=openapi.TYPE_STRING,
                required=False
            ),
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="페이지 번호 (기본값: 1)",
                type=openapi.TYPE_INTEGER,
                default=1
            ),
            openapi.Parameter(
                'size',
                openapi.IN_QUERY,
                description="페이지당 아이템 수 (기본값: 10)",
                type=openapi.TYPE_INTEGER,
                default=10
            ),
            openapi.Parameter(
                'username',
                openapi.IN_QUERY,
                description="멤버 ID (필터링 용도)",
                type=openapi.TYPE_STRING,
                required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="뮤직비디오 목록 조회 성공",
                examples={
                    "application/json": {
                        "music_videos": [{
                            "id" : 0,
                            "subject": "string",
                            "cover_image": "string",
                            "member_name": "string",
                            "profile_image": "string",
                            "length": 0,
                            "views": 0,
                            "genres": [
                            "string",
                            "string",
                            "string",
                            ],
                            "instruments": [
                            "string",
                            "string",
                            "string",
                            ],
                            "style_name": "string",
                            "language": "string",
                            "vocal": "string",
                            "tempo": "string",
                            "is_completed": True
                            }
                        ],
                        "code": "M001",
                        "status": 200,
                        "message": "뮤직비디오 목록 조회 성공",
                        "pagination": {
                            "current_page": 1,
                            "next_page": True,
                            "page_size": 10,
                            "total_pages": 5,
                            "total_items": 50,
                            "last_page": False
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직비디오 목록 조회 실패",
                examples={
                    "application/json": {
                        "code": "M001_1",
                        "status": 404,
                        "message": "뮤직비디오를 찾을 수 없습니다."
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        user = request.user
        queryset = MusicVideo.objects.all()

        message = '뮤직비디오 정보 조회 성공'

        # 멤버 ID 필터링
        username = request.query_params.get('username', None)
        if username:
            queryset = queryset.filter(username__username=username)
            message = f'사용자 뮤직비디오 정보 조회 성공'
        # 정렬
        sort = request.query_params.get('sort', None)

        if sort:
            if sort == 'countries':
                country = user.country
                members = Member.objects.filter(country=country)
                queryset = queryset.filter(username__in=members).order_by('-views')
            elif sort == 'ages':
                current_year = datetime.now().year
                birth_date = user.birthday
                birth_year = birth_date.year
                age = current_year - birth_year
                if age < 20:
                    members = Member.objects.filter(birthday__year__gte=current_year - 19)
                elif age < 30:
                    members = Member.objects.filter(birthday__year__gte=current_year - 29, birthday__year__lte=current_year - 20)
                elif age < 40:
                    members = Member.objects.filter(birthday__year__gte=current_year - 39, birthday__year__lte=current_year - 30)
                elif age < 50:
                    members = Member.objects.filter(birthday__year__gte=current_year - 49, birthday__year__lte=current_year - 40)
                else:
                    members = Member.objects.filter(birthday__year__lte=current_year - 50)

                queryset = queryset.filter(username__in=members).order_by('-views')
            else:
                queryset = queryset.order_by(f'-{sort}')
                message = f"뮤직비디오 {sort}순 정보 조회 성공"

        # 결과가 없는 경우 처리
        if not queryset.exists():
            response_data = {
                "code": "M001_1",
                "status": 404,
                "message": "뮤직비디오를 찾을 수 없습니다."
            }
            logger.warning(f'{client_ip} GET /music-videos 404 does not existing')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        # 페이지네이션
        page = request.query_params.get('page',1)
        size = request.query_params.get('size',10)
        paginator = Paginator(queryset, size)
        paginated_queryset = paginator.get_page(page)

        serializer = MusicVideoDetailSerializer(paginated_queryset, many=True)

        response_data = {
            "music_videos": serializer.data,
            "code": "M001",
            "HTTPstatus": 200,
            "message": message,
            "pagination": {
                "current_page": paginated_queryset.number,
                "next_page": paginated_queryset.has_next(),
                "page_size": size,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "last_page": not paginated_queryset.has_next()
            }
        }
        logger.info(f'{client_ip} GET /music-videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)

class MusicVideoDevelopView(APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 생성 API",
        operation_description="이 API는 뮤직비디오를 생성하는 데 사용됩니다.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='회원 ID'),
                'subject': openapi.Schema(type=openapi.TYPE_STRING, description='가사의 주제'),
                'lyrics': openapi.Schema(type=openapi.TYPE_STRING, description='가사'),
                'genres_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='장르 ID 목록'),
                'instruments_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='악기 ID 목록'),
                'style_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='영상 스타일 ID'),
                'tempo': openapi.Schema(type=openapi.TYPE_STRING, description='템포'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='언어'),
                'vocal': openapi.Schema(type=openapi.TYPE_STRING, description='보컬'),
                'cover_image': openapi.Schema(type=openapi.TYPE_STRING, description='커버 이미지 URL'),
                'mv_file': openapi.Schema(type=openapi.TYPE_STRING, description='뮤직비디오 파일 URL')
            },
            required=['username', 'subject', 'lyrics', 'genres_ids', 'instruments_ids', 'style_id', 'tempo', 'language', 'vocal', 'cover_image', 'mv_file']
        ),
        responses={
            201: openapi.Response(
                description="뮤직비디오 생성 성공",
                examples={
                    "application/json": {
                        "code": "M002",
                        "status": 201,
                        "message": "뮤직비디오 생성 성공"
                    }
                }
            ),
            400: openapi.Response(
                description="필수 파라미터 누락",
                examples={
                    "application/json": {
                        "code": "M002_1",
                        "status": 400,
                        "message": "필수 조건이 누락되었습니다."
                    }
                }
            ),
            500: openapi.Response(
                description="서버 오류",
                examples={
                    "application/json": {
                        "code": "M002_2",
                        "status": 500,
                        "message": "서버 오류"
                    }
                }
            )
        }
    )
    def post(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)

        try:
            # 요청 데이터 가져오기
            username = request.data.get('username')
            subject = request.data.get('subject')
            lyrics = request.data.get('lyrics')

            genres_ids = request.data['genres_ids']
            genres = Genre.objects.filter(id__in=genres_ids)
            genre_names = [str(genre) for genre in genres]
            genre_names_str = ", ".join(genre_names)

            instruments_ids = request.data['instruments_ids']
            instruments = Instrument.objects.filter(id__in=instruments_ids)
            instruments_names = [str(instrument) for instrument in instruments]
            instruments_str = ", ".join(instruments_names)

            style_id = request.data.get('style_id')

            tempo = request.data.get('tempo')
            language = request.data.get('language')
            vocal = request.data.get('vocal')
            cover_image = request.data.get('cover_image')
            mv_file = request.data.get('mv_file')

            # 필수 필드 확인
            if not (username and subject and lyrics and genres_ids and instruments_ids and style_id and tempo and language and vocal and cover_image and mv_file):
                response_data = {
                    "code": "M002_1",
                    "status": 400,
                    "message": "필수 조건이 누락되었습니다."
                }
                logger.error(f'{client_ip} POST /music-videos/develop 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # 회원 정보 가져오기
            member = Member.objects.filter(username=username).first()

            # 영상 스타일 정보 가져오기
            style = Style.objects.get(id=style_id)

            # 장르와 악기 정보 가져오기
            genres = Genre.objects.filter(id__in=genres_ids)
            instruments = Instrument.objects.filter(id__in=instruments_ids)

            # MusicVideo 객체 생성
            music_video = MusicVideo(
                username=member,
                subject=subject,
                lyrics=lyrics,
                tempo=tempo,
                language=language,
                style_id=style,
                vocal=vocal,
                cover_image=cover_image,
                mv_file=mv_file,
                length=85.0,
                recently_viewed=0,
                views=0
            )
            music_video.save()

            # ManyToMany 필드 추가
            music_video.genre_id.set(genres)
            music_video.instrument_id.set(instruments)

            response_data = {
                "code": "M002",
                "status": 201,
                "message": "뮤직비디오 생성 성공"
            }
            logger.info(f'{client_ip} POST /music-videos/develop 201 success')
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Member.DoesNotExist:
            logger.error(f'{client_ip} POST /music-videos/develop 400 Member with ID {username} does not exist')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 회원: {username}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Genre.DoesNotExist as e:
            logger.error(f'{client_ip} POST /music-videos/develop 400 Genre does not exist: {str(e)}')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 장르 ID: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Instrument.DoesNotExist as e:
            logger.error(f'{client_ip} POST /music-videos/develop 400 Instrument does not exist: {str(e)}')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 악기 ID: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'{client_ip} POST /music-videos/develop 500 {str(e)}')
            return Response({
                "code": "M002_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MusicVideoManageView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 상세 정보 조회 API",
        operation_description="특정 뮤직비디오의 ID를 통해 상세 정보를 조회합니다.",
        responses={
            200: openapi.Response(
                description="뮤직비디오 상세 정보 조회 성공",
                examples={
                    "application/json": {
                        "code": "M003",
                        "status": 200,
                        "message": "뮤직비디오 상세 정보 조회 성공",
                        "data": {
                            "subject": "string",
                            "member_name": "string",
                            "length": 0,
                            "mv_file": "string",
                            "views": 0,
                            "lyrics": "string",
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직비디오 상세 정보 조회 실패",
                examples={
                    "application/json": {
                        "code": "M003_1",
                        "status": 404,
                        "message": "뮤직비디오를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, mv_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        try:
            music_video = MusicVideo.objects.get(id=mv_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M003_1",
                "status": 404,
                "message": "뮤직비디오를 찾을 수 없습니다."
            }
            logger.warning(f'{client_ip} GET /music-videos/{mv_id} 404 does not existing')
            return Response(response_data, status=404)

        serializer = MusicVideoDetailSerializer(music_video)
        response_data = {
            "data": serializer.data,
            "code": "M003",
            "status": 200,
            "message": "뮤직비디오 상세 정보 조회 성공"
        }
        logger.info(f'{client_ip} GET /music-videos/{mv_id} 200 view success')
        return Response(response_data, status=200)

    @swagger_auto_schema(
        operation_summary="뮤직비디오 삭제 API",
        operation_description="이 API는 특정 회원의 뮤직비디오를 삭제하는 데 사용됩니다.",
        responses={
            200: openapi.Response(
                description="뮤직비디오 삭제 성공",
                examples={
                    "application/json": {
                        "code": "M004",
                        "status": 200,
                        "message": "뮤직비디오 삭제 성공",
                        "data": {
                            "username": "username",
                            "subject": "subject",
                            "is_deleted": "1",
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직비디오 삭제 실패",
                examples={
                    "application/json": {
                        "code": "M004_1",
                        "status": 404,
                        "message": "해당 뮤직비디오를 찾을 수 없습니다."
                    }
                }
            ),
        }
    )
    def delete(self, request, mv_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        try:
            music_video = MusicVideo.objects.get(id=mv_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M004_1",
                "status": 404,
                "message": "해당 뮤직비디오를 찾을 수 없습니다."
            }
            logger.warning(f'{client_ip} PATCH /music-videos/{mv_id} 404 does not existing')
            return Response(response_data, status=404)
        music_video.is_deleted = True
        music_video.save()
        serializer = MusicVideoDeleteSerializer(music_video)
        response_data = {
            "code": "M004",
            "status": 200,
            "message": "뮤직비디오 삭제 성공",
            "data": serializer.data
        }
        logger.info(f'{client_ip} PATCH /music-videos/{mv_id} 200 delete success')
        return Response(response_data, status=200)


class GenreListView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="장르 리스트 조회 API",
        operation_description="이 API는 사용자가 원하는 장르를 선택할 수 있도록 장르 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="장르 리스트 조회 성공",
                examples={
                    "application/json": {
                        "genres": [
                            {
                                "genre_id": 0,
                                "genre_name": "string",
                                "genre_image_url": "string",
                            },
                            {
                                "genre_id": 1,
                                "genre_name": "string",
                                "genre_image_url": "string",
                            },
                            {
                                "genre_id": 2,
                                "genre_name": "string",
                                "genre_image_url": "string",
                            },
                            {
                                "genre_id": 3,
                                "genre_name": "string",
                                "genre_image_url": "string",
                            },
                        ],
                        "code": "M005",
                        "status": 200,
                        "message": "장르 리스트 조회 성공",
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
        try:
            genres = Genre.objects.all()
            serializer = GenreSerializer(genres, many=True)
            response_data = {
                "genres": [
                    {
                        "genre_id": item["id"],
                        "genre_name": item["name"],
                        "genre_image_url": item["image_url"]
                    } for item in serializer.data
                ],
                "code": "M005",
                "status": 200,
                "message": "장르 리스트 조회 성공"
            }
            logger.info(f'{client_ip} GET /music-videos/genres 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M005_1",
                "status": 500,
                "message": "장르 리스트를 불러올 수 없습니다."
            }
            logger.error(f'{client_ip} GET /music-videos/genres 500 failed : {e}')
            return Response(response_data, status=500)

class InstrumentListView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="악기 리스트 조회 API",
        operation_description="이 API는 사용자가 원하는 악기를 선택할 수 있도록 악기 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="악기 리스트 조회 성공",
                examples={
                    "application/json": {
                        "instruments": [{
                                "instrument_id": 0,
                                "instrument_name": "string",
                                "instrument_image_url": "string",
                            },
                            {
                                "instrument_id": 1,
                                "instrument_name": "string",
                                "instrument_image_url": "string",
                            },
                            {
                                "instrument_id": 2,
                                "instrument_name": "string",
                                "instrument_image_url": "string",
                            },
                            {
                                "instrument_id": 3,
                                "instrument_name": "string",
                                "instrument_image_url": "string",
                            }
                        ],
                        "code": "M006",
                        "status": 200,
                        "message": "악기 리스트 조회 성공",
                    }
                }
            ),
            500: openapi.Response(
                description="악기 리스트를 불러올 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M006_1",
                        "status": 500,
                        "message": "악기 리스트를 불러올 수 없습니다."
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        try:
            instruments = Instrument.objects.all()
            serializer = InstrumentSerializer(instruments, many=True)
            response_data = {
                "instruments": [
                    {
                        "instrument_id": item["id"],
                        "instrument_name": item["name"],
                        "instrument_image_url": item["image_url"]
                    } for item in serializer.data
                ],
                "code": "M006",
                "status": 200,
                "message": "악기 리스트 조회 성공"
            }
            logger.info(f'{client_ip} GET /music-videos/instruments 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M006_1",
                "status": 500,
                "message": "악기 리스트를 불러올 수 없습니다."
            }
            logger.error(f'{client_ip} GET /music-videos/instruments 500 failed : {e}')
            return Response(response_data, status=500)
class StyleListView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="영상 스타일 리스트 조회 API",
        operation_description="이 API는 사용자가 원하는 영상 스타일을 선택할 수 있도록 영상 스타일 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="영상 스타일 리스트 조회 성공",
                examples={
                    "application/json": {
                        "styles": [
                            {
                                "style_id": 0,
                                "style_name": "string",
                                "style_image_url": "string",
                            },
                            {
                                "style_id": 1,
                                "style_name": "string",
                                "style_image_url": "string",
                            },
                            {
                                "style_id": 2,
                                "style_name": "string",
                                "style_image_url": "string",
                            },
                            {
                                "style_id": 3,
                                "style_name": "string",
                                "style_image_url": "string",
                            },
                        ],
                        "code": "M011",
                        "status": 200,
                        "message": "영상 스타일 리스트 조회 성공",
                    }
                }
            ),
            500: openapi.Response(
                description="영상 스타일 리스트를 불러올 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M011_1",
                        "status": 500,
                        "message": "영상 스타일 리스트를 불러올 수 없습니다."
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        try:
            styles = Style.objects.all()
            serializer = StyleSerializer(styles, many=True)
            response_data = {
                "data": [
                    {
                        "style_id": item["id"],
                        "style_name": item["name"],
                        "style_image_url": item["image_url"]
                    } for item in serializer.data
                ],
                "code": "M011",
                "status": 200,
                "message": "스타일 리스트 조회 성공"
            }
            logger.info(f'{client_ip} GET /music-videos/styles 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M011_1",
                "status": 500,
                "message": "스타일 리스트를 불러올 수 없습니다."
            }
            logger.error(f'{client_ip} GET /music-videos/styles 500 failed : {e}')
            return Response(response_data, status=500)


class HistoryCreateView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 시청 기록 등록 API",
        operation_description="사용자가 특정 뮤직비디오를 조회했을 때 시청 기록을 등록합니다.",
        responses={
            201: openapi.Response(
                description="사용자의 뮤직비디오 시청 기록 등록 성공",
                examples={
                    "application/json": {
                        "history_id": 0,
                        "code": "M008",
                        "status": 201,
                        "message": "사용자의 뮤직비디오 시청 기록 등록 성공",
                    }
                }
            ),
            400: openapi.Response(
                description="사용자의 뮤직비디오로 인해 시청 기록 등록 실패",
                examples={
                    "application/json": {
                        "code": "M008_2",
                        "status": 400,
                        "message": "사용자의 뮤직비디오입니다.",
                    }
                }
            ),
            404: openapi.Response(
                description="시청 기록 등록 실패",
                examples={
                    "application/json": [
                        {
                            "code": "M008_1",
                            "status": 404,
                            "message": "뮤직 비디오를 찾을 수 없습니다."
                        },
                    ]
                }
            ),
            409: openapi.Response(
                description="이미 시청한 기록이 있습니다.",
                examples={
                    "application/json": {
                        "history_id": 0,
                        "code": "M008_3",
                        "status": 409,
                        "message": "이미 시청한 기록이 있습니다.",
                    }
                }
            ),
        }
    )
    def post(self, request, mv_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        member = request.user

        try:
            mv = MusicVideo.objects.get(id=mv_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M008_2",
                "status": 404,
                "message": "뮤직 비디오를 찾을 수 없습니다."
            }
            logger.warning(f'{client_ip} POST /music-videos/histories/create/{mv_id} 404 does not existing')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        if mv.username == member:
            response_data = {
                "code": "M008_3",
                "status": 400,
                "message": "사용자의 뮤직비디오입니다."
            }
            logger.warning(f'{client_ip} POST /music-videos/histories/create/{mv_id} 400 the user\'s music video')
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

        try:
            history_test = History.objects.get(username=member.username, mv_id=mv)
            if history_test:
                response_data = {
                    "history_id": history_test.id,
                    "current_play_time": history_test.current_play_time,
                    "code": "M008_4",
                    "status": 409,
                    "message": "이미 시청한 기록이 있습니다."
                }
                logger.warning(f'{client_ip} /music-videos/histories/create/{mv_id} 409 already exists')
                return Response(response_data, status=status.HTTP_409_CONFLICT)
        except:
            histories = History.objects.create(
                username=member,
                mv_id=mv,
                current_play_time=0,
                is_deleted=False
            )
            response_data = {
                "history_id": histories.id,
                "code": "M008",
                "status": 201,
                "message": "시청 기록 추가 성공"
            }
            mv.views += 1
            mv.recently_viewed += 1
            mv.save()
            logger.info(f'{client_ip} GET /music-videos/histories/create/{mv_id} 201 success')
            return Response(response_data, status=201)

class HistoryUpdateView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 시청 기록 갱신 API",
        operation_description="사용자의 뮤직비디오 시청 기록을 갱신합니다.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'current_play_time': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description="Current play time"
                )
            },
            required=['current_play_time']
        ),
        responses={
            200: openapi.Response(
                description="사용자의 뮤직비디오 시청 기록 갱신 성공",
                examples={
                    "application/json": {
                        "code": "M009",
                        "status": 200,
                        "message": "사용자 뮤직비디오 시청 기록 갱신 성공",
                    }
                }
            ),
            404: openapi.Response(
                description="시청 기록을 찾을 수 없습니다.",
                examples={
                    "application/json": [
                        {
                            "code": "M009_1",
                            "status": 404,
                            "message": "시청 기록을 찾을 수 없습니다."
                        },
                        {
                            "code": "M009_2",
                            "status": 404,
                            "message": "사용자의 시청 기록이 아닙니다."
                        }
                    ]
                }
            ),
        }
    )
    def patch(self, request, history_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        member = request.user
        try:
            histories = History.objects.get(id=history_id)
            if not histories.username == member:
                response_data = {
                    "code": "M009_2",
                    "status": 404,
                    "message": "사용자의 시청 기록이 아닙니다."
                }
                logger.warning(
                    f'{client_ip} PATCH /music-videos/histories/update/{history_id} 404 Not Found')
                return Response(response_data, status=status.HTTP_404_NOT_FOUND)

            current_play_time = request.data.get('current_play_time', histories.current_play_time)
            histories.current_play_time = current_play_time
            # histories.updated_at = datetime.now()
            histories.save()
            response_data = {
                "history_id": histories.id,
                "code": "M009",
                "status": 200,
                "message": "뮤직비디오 시청 기록 갱신 성공"
            }
            logger.info(f'{client_ip} PATCH /music-videos/histories/update/{history_id} 200 success')
            return Response(response_data, status=status.HTTP_200_OK)

        except History.DoesNotExist:
            response_data = {
                "code": "M009_1",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다"
            }
            logger.warning(
                f'{client_ip} PATCH /music-videos/histories/update/{history_id} 404 Not Found')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)


class HistoryDetailView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 시청 기록 조회 API",
        operation_description="사용자의 뮤직비디오 시청 기록을 조회합니다.",
        manual_parameters=[
            openapi.Parameter(
                'page',
                openapi.IN_QUERY,
                description="페이지 번호 (기본값: 1)",
                type=openapi.TYPE_INTEGER,
                default=1
            ),
            openapi.Parameter(
                'size',
                openapi.IN_QUERY,
                description="페이지당 아이템 수 (기본값: 10)",
                type=openapi.TYPE_INTEGER,
                default=10
            ),
        ],
        responses={
            200: openapi.Response(
                description="뮤직비디오 시청 기록 조회 성공",
                examples={
                    "application/json": {
                        "code": "M010",
                        "status": 200,
                        "message": "뮤직비디오 시청 기록 조회 성공"
                    }
                }
            ),
            404: openapi.Response(
                description="잘못된 요청",
                examples={
                    "application/json": [
                        {
                            "code": "M010_1",
                            "status": 404,
                            "message": "회원 정보를 찾을 수 없습니다."
                        },
                        {
                            "code": "M010_2",
                            "status": 404,
                            "message": "시청 기록을 찾을 수 없습니다."
                        }
                    ]
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        username = request.user.username

        member = Member.objects.filter(username=username).first()

        if not member:
            response_data = {
                "code": "M010_1",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(
                f'{client_ip} /music-videos/histories 404 Not Found')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        member_histories = History.objects.filter(username=member).order_by('-updated_at')
        if not member_histories.exists():
            response_data = {
                "code": "M010_2",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다."
            }
            logger.warning(
                f'{client_ip} /music-videos/histories 404 Not Found')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        watch_mv_id = member_histories.values_list('mv_id', flat=True)
        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(watch_mv_id)])
        watch_music_videos = MusicVideo.objects.filter(id__in=watch_mv_id).order_by(preserved_order)

        page = request.query_params.get('page', 1)
        size = request.query_params.get('size', 10)
        paginator = Paginator(watch_music_videos, size)
        paginated_queryset = paginator.get_page(page)

        serializer = MusicVideoDetailSerializer(paginated_queryset, many=True)

        response_data = {
            "music_videos": serializer.data,
            "code": "M010",
            "HTTPstatus": 200,
            "message": "뮤직비디오 시청 기록 조회 성공",
            "pagination": {
                "current_page": paginated_queryset.number,
                "next_page": paginated_queryset.has_next(),
                "page_size": size,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "last_page": not paginated_queryset.has_next()
            }
        }
        logger.info(f'{client_ip} GET /music-videos/histories 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)

class MusicVideoSearchView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 검색 API",
        operation_description="키워드로 뮤직비디오를 검색할 수 있습니다.",
        manual_parameters=[
            openapi.Parameter('mv_name', openapi.IN_QUERY, description="Music video name", type=openapi.TYPE_STRING),
            openapi.Parameter('sort', openapi.IN_QUERY, description="Sort by field", type=openapi.TYPE_STRING),
            openapi.Parameter('page', openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER),
            openapi.Parameter('size', openapi.IN_QUERY, description="Page size", type=openapi.TYPE_INTEGER),
        ],
        responses={
            200: openapi.Response(
                description="뮤직비디오 검색 성공",
                examples={
                    "application/json": {
                        "music_videos": [{
                            "id": 0,
                            "subject": "string",
                            "cover_image": "string",
                            "member_name": "string",
                            "length": 0,
                            "views": 0,
                            "genres": [
                                "string",
                                "string",
                                "string",
                            ],
                            "instruments": [
                                "string",
                                "string",
                                "string",
                            ],
                            "style_name": "string",
                            "language": "string",
                            "vocal": "string",
                            "tempo": "string",
                            "is_completed": True
                        }
                        ],
                        "code": "S001",
                        "HTTPstatus": 200,
                        "message": "뮤직비디오 검색 성공",
                        "pagination": {
                            "current_page": 1,
                            "next_page": True,
                            "page_size": 10,
                            "total_pages": 5,
                            "total_items": 50,
                            "last_page": False
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직비디오 검색 실패",
                examples={
                    "application/json": {
                        "code": "S001_1",
                        "status": 404,
                        "message": "뮤직비디오를 찾을 수 없습니다."
                    }
                }
            ),
        }
    )
    def get(self, request):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = '뮤직비디오 정보 조회 성공'
        mv_name = request.query_params.get('mv_name', None)
        queryset = MusicVideo.objects.all()
        user = request.user
        if mv_name:
            log_message = {
                "client_ip": client_ip,
                "username": user.username,
                "country": user.country.name,
                "sex": user.sex,
                "action": "search",
                "mv_name": mv_name
            }
            logger.info(json.dumps(log_message, ensure_ascii=False))
            # Elasticsearch에서 유사한 이름의 뮤직비디오 검색
            q = MultiMatch(query=mv_name, fields=['subject'], fuzziness='auto')
            search = MusicVideoDocument.search().query(q)
            response = search.execute()
            music_video_ids = [hit.meta.id for hit in response]
            queryset = queryset.filter(id__in=music_video_ids)
        # 정렬
        sort = request.query_params.get('sort', None)

        if sort:
            queryset = queryset.order_by(f'-{sort}')
            message = f"뮤직비디오 {sort}순 정보 조회 성공"

        # 결과가 없는 경우 처리
        if not queryset.exists():
            response_data = {
                "code": "S001_1",
                "status": 404,
                "message": "뮤직비디오를 찾을 수 없습니다."
            }
            logger.warning(f'{client_ip} GET /music-videos/searches 404 not found')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)

        # 페이지네이션
        page = request.query_params.get('page',1)
        size = request.query_params.get('size',10)
        paginator = Paginator(queryset, size)
        paginated_queryset = paginator.get_page(page)

        serializer = MusicVideoDetailSerializer(paginated_queryset, many=True)

        response_data = {
            "music_videos": serializer.data,
            "code": "S001",
            "HTTPstatus": 200,
            "message": message,
            "pagination": {
                "current_page": paginated_queryset.number,
                "next_page": paginated_queryset.has_next(),
                "page_size": size,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count,
                "last_page": not paginated_queryset.has_next()
            }
        }
        logger.info(f'{client_ip} GET /music-videos/searches 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)

class MusicVideoStatusView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 제작 상태 확인 API",
        operation_description="뮤직비디오 제작 작업의 상태를 확인합니다",
        manual_parameters=[
            openapi.Parameter(
                'task_id',
                openapi.IN_PATH,
                description="뮤직비디오 제작 작업의 ID",
                type=openapi.TYPE_STRING
            )
        ],
        responses={
            200: openapi.Response(
                description="작업이 진행 중이거나 커스텀 상태입니다",
                examples={
                    "application/json": {
                        "code": "M012_1",
                        "task_status": "PENDING",
                        "HTTPstatus": 200,
                        "message": "뮤직비디오 제작 진행중입니다..."
                    }
                }
            ),
            201: openapi.Response(
                description="작업이 성공적으로 완료되었습니다",
                examples={
                    "application/json": {
                        "code": "M012",
                        "task_status": "SUCCESS",
                        "HTTPstatus": 201,
                        "message": "뮤직비디오 제작 성공하였습니다."
                    }
                }
            ),
            500: openapi.Response(
                description="작업이 실패하였습니다",
                examples={
                    "application/json": {
                        "code": "M012_2",
                        "task_status": "FAILURE",
                        "HTTPstatus": 500,
                        "message": "뮤직비디오 제작 실패하였습니다."
                    }
                }
            ),
            404: openapi.Response(
                description="작업을 찾을 수 없습니다",
                examples={
                    "application/json": {
                        "code": "M012_4",
                        "task_id": "task_id",
                        "HTTPstatus": 404,
                        "message": "task가 존재하지 않습니다."
                    }
                }
            )
        }
    )
    def get(self, request, task_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        try:
            task = AsyncResult(task_id)

            if task.state == 'PENDING':
                response_data = {
                    "code": "M012_1",
                    "task_status": "PENDING",
                    "HTTPstatus": 200,
                    "message": "뮤직비디오 제작 진행중입니다..."
                }
                http_status = status.HTTP_200_OK
            elif task.state == 'SUCCESS':
                response_data = {
                    "code": "M012",
                    "task_status": "SUCCESS",
                    "HTTPstatus": 201,
                    "message": "뮤직비디오 제작 성공하였습니다."
                }
                http_status = status.HTTP_201_CREATED
            elif task.state == 'FAILURE':
                response_data = {
                    "code": "M012_2",
                    "task_status": "FAILURE",
                    "HTTPstatus": 500,
                    "message": "뮤직비디오 제작 실패하였습니다."
                }
                http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            else:
                response_data = {
                    "code": "M012_3",
                    "task_status": task.state,
                    'HTTPstatus': 200,
                    'message': str(task.info),  # 이곳에서 오류 메시지나 추적 정보 포함
                }
                http_status = status.HTTP_200_OK
            logger.info(f'{client_ip} GET /music-videos/status/{task_id} 200 success')
            return Response(response_data, status=http_status)
        except:
            response_data = {
                "code": "M012_4",
                "task_id": task_id,
                "HTTPstatus": 404,
                "message": "task가 존재하지 않습니다."
            }
            logger.warning(f'{client_ip} GET /music-videos/status/{task_id} 404 does not existing')
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)


