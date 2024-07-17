from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.conf import settings
from django.core.paginator import Paginator
from member.models import Member
from .models import Genre, Instrument, MusicVideo, History, Style
from .serializers import GenreSerializer, InstrumentSerializer, MusicVideoDetailSerializer, MusicVideoDeleteSerializer, HistorySerializer, StyleSerializer
from .tasks import suno_music, create_video, mv_create
from celery import group, chord
from celery.result import AsyncResult

from datetime import datetime
import logging
import openai
from django.db.models import Case, When

from elasticsearch_dsl.query import MultiMatch
from .documents import MusicVideoDocument


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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
                logging.error(f'ERROR {client_ip} {current_time} POST /lyrics 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            prompt = (
                f"Create song lyrics based on the keyword '{subject}'. "
                f"The genre should be {genre_names_str}, the language should be {language}, and the vocals should be suitable for {vocal} vocals. "
                f"The song should have 2 verses, each with 4 lines. Each line should be detailed and At least 2 sentences per line(very important!!). Each line should vividly describe a specific situation or emotion. followed by English translations of each verse, formatted as follows:\n\n"
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
                "lyrics_ori": {
                    "lyrics1": lyrics1_ori,
                    "lyrics2": lyrics2_ori,
                    "lyrics3": lyrics3_ori,
                },
                "lyrics_eng": {
                    "lyrics1": lyrics1_eng,
                    "lyrics2": lyrics2_eng,
                    "lyrics3": lyrics3_eng,
                },
                "code": "M007",
                "status": 201,
                "message": "가사 생성 성공"
            }
            logging.info(f'INFO {client_ip} {current_time} POST /lyrics 201 lyrics created')
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /lyrics 500 {str(e)}')
            return Response({
                "code": "M007_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MusicVideoView(APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 생성",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'member_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='회원 ID'),
                'subject': openapi.Schema(type=openapi.TYPE_STRING, description='가사의 주제'),
                'genres_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='장르 ID 목록'),
                'instruments_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Items(type=openapi.TYPE_INTEGER), description='악기 ID 목록'),
                'style_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='영상 스타일 ID'),
                'tempo': openapi.Schema(type=openapi.TYPE_STRING, description='템포 유형'),
                'language': openapi.Schema(type=openapi.TYPE_STRING, description='언어'),
                'vocal': openapi.Schema(type=openapi.TYPE_STRING, description='보컬 유형'),
                'lyrics': openapi.Schema(type=openapi.TYPE_STRING, description='가사')
            },
            required=['member_id', 'subject', 'genres_ids', 'instruments_ids', 'style_id', 'tempo', 'language', 'vocal', 'lyrics']
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
            subject = request.data['subject']
            vocal = request.data['vocal']
            tempo = request.data['tempo']
            member_id = request.data['member_id']
            language = request.data['language']
            lyrics = request.data['lyrics']
            lyrics_eng = request.data['lyrics_eng']

            # 장르 쉼표로 구분
            genres_ids = request.data['genres_ids']
            genres = Genre.objects.filter(id__in=genres_ids)
            genre_names = [str(genre) for genre in genres]
            genre_names_str = ", ".join(genre_names)

            # 악기 쉼표로 구분
            instruments_ids = request.data['instruments_ids']
            instruments = Instrument.objects.filter(id__in=instruments_ids)
            instruments_names = [str(instrument) for instrument in instruments]
            instruments_str = ", ".join(instruments_names)

            # 스타일 쉼표로 구분
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
                logging.error(f'ERROR {client_ip} {current_time} POST /music_video 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # 텍스트를 줄 단위로 나누기
            lines = lyrics_eng.strip().split('\n')
            # [Verse]와 같은 태그를 제외하고 저장
            filtered_lines = [line for line in lines if not line.startswith('[') and line.strip()]

            music_task = suno_music.s(genre_names_str, instruments_str, tempo, vocal, lyrics, subject)

            video_tasks = group(
                create_video.s(line, style_name) for line in filtered_lines
            )

            music_video_task = chord(
                header=[music_task] + video_tasks.tasks,
                body=mv_create.s(client_ip, current_time, subject, language, vocal, lyrics, genres_ids, instruments_ids,
                                 tempo, member_id)
            )
            task_id = music_video_task.apply_async().id

            response_data = {
                "code": "M002",
                "status": 200,
                "message": "뮤직비디오 생성 요청 성공",
                "task_id": task_id
            }
            logging.info(f'INFO {client_ip} {current_time} PATCH /music_video 200 post success')
            return Response(response_data, status=200)
        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /lyrics 500 {str(e)}')
            return Response({
                "code": "M002_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @swagger_auto_schema(
        operation_summary="뮤직비디오 목록 조회",
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
                'member_id',
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
                        "HTTPstatus": 200,
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        queryset = MusicVideo.objects.all()

        message = '뮤직비디오 정보 조회 성공'

        # 멤버 ID 필터링
        member_id = request.query_params.get('member_id', None)
        # 정렬
        sort = request.query_params.get('sort', None)

        if member_id:
            queryset = queryset.filter(member_id=member_id)
            message = f'사용자 뮤직비디오 정보 조회 성공'
        if sort:
            if (sort=='countries'):
                member = Member.objects.get(id=member_id)
                members = Member.objects.filter(country_id=member.country_id)
                queryset = MusicVideo.objects.filter(member_id__in=members)
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
            logging.warning(f'WARNING {client_ip} {current_time} GET /music_videos 404 does not existing')
            return Response(response_data, status=404)

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
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MusicVideoDevelopView(APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 생성 API",
        operation_description="이 API는 뮤직비디오를 생성하는 데 사용됩니다.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'member_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='회원 ID'),
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
            required=['member_id', 'subject', 'lyrics', 'genres_ids', 'instruments_ids', 'style_id', 'tempo', 'language', 'vocal', 'cover_image', 'mv_file']
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            # 요청 데이터 가져오기
            member_id = request.data.get('member_id')
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
            if not (member_id and subject and lyrics and genres_ids and instruments_ids and style_id and tempo and language and vocal and cover_image and mv_file):
                response_data = {
                    "code": "M002_1",
                    "status": 400,
                    "message": "필수 조건이 누락되었습니다."
                }
                logging.error(f'ERROR {client_ip} {current_time} POST /music_video_develop 400 missing required fields')
                return Response(response_data, status=status.HTTP_400_BAD_REQUEST)

            # 회원 정보 가져오기
            member = Member.objects.get(id=member_id)

            # 영상 스타일 정보 가져오기
            style = Style.objects.get(id=style_id)

            # 장르와 악기 정보 가져오기
            genres = Genre.objects.filter(id__in=genres_ids)
            instruments = Instrument.objects.filter(id__in=instruments_ids)

            # MusicVideo 객체 생성
            music_video = MusicVideo(
                member_id=member,
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
            logging.info(f'INFO {client_ip} {current_time} POST /music_video_develop 201 success')
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Member.DoesNotExist:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_video_develop 400 Member with ID {member_id} does not exist')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 회원 ID: {member_id}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Genre.DoesNotExist as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_video_develop 400 Genre does not exist: {str(e)}')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 장르 ID: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Instrument.DoesNotExist as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_video_develop 400 Instrument does not exist: {str(e)}')
            return Response({
                "code": "M002_1",
                "status": 400,
                "message": f"잘못된 악기 ID: {str(e)}"
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_video_develop 500 {str(e)}')
            return Response({
                "code": "M002_2",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MusicVideoDeleteView(APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 삭제",
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
                            "member_id": "member_id",
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
    def delete(self, request, music_video_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            music_video = MusicVideo.objects.get(id=music_video_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M004_1",
                "status": 404,
                "message": "해당 뮤직비디오를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} PATCH /music_video 404 does not existing')
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
        logging.info(f'INFO {client_ip} {current_time} PATCH /music_video/{music_video_id} 200 delete success')
        return Response(response_data, status=200)


class GenreListView(APIView):
    @swagger_auto_schema(
        operation_summary="장르 리스트 조회",
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
                            },
                            {
                                "genre_id": 1,
                                "genre_name": "string",
                            },
                            {
                                "genre_id": 2,
                                "genre_name": "string",
                            },
                            {
                                "genre_id": 3,
                                "genre_name": "string",
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            logging.info(f'INFO {client_ip} {current_time} GET /genre_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M005_1",
                "status": 500,
                "message": "장르 리스트를 불러올 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /genre_list 500 failed : {e}')
            return Response(response_data, status=500)


class InstrumentListView(APIView):
    @swagger_auto_schema(
        operation_summary="악기 리스트 조회",
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            logging.info(f'INFO {client_ip} {current_time} GET /instrument_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M006_1",
                "status": 500,
                "message": "악기 리스트를 불러올 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /instrument_list 500 failed : {e}')
            return Response(response_data, status=500)

class StyleListView(APIView):
    @swagger_auto_schema(
        operation_summary="영상 스타일 리스트 조회",
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
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            logging.info(f'INFO {client_ip} {current_time} GET /genre_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M011_1",
                "status": 500,
                "message": "스타일 리스트를 불러올 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /genre_list 500 failed : {e}')
            return Response(response_data, status=500)


class MusicVideoDetailView(APIView):

    @swagger_auto_schema(
        operation_summary="뮤직비디오 상세 정보 조회",
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
    def get(self, request, music_video_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            music_video = MusicVideo.objects.get(id=music_video_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M003_1",
                "status": 404,
                "message": "뮤직비디오를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /music_videos 404 does not existing')
            return Response(response_data, status=404)

        serializer = MusicVideoDetailSerializer(music_video)
        response_data = {
            "data": serializer.data,
            "code": "M003",
            "status": 200,
            "message": "뮤직비디오 상세 정보 조회 성공"
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 view success')
        return Response(response_data, status=200)


class HistoryCreateView(APIView):
    @swagger_auto_schema(
        operation_summary="사용자의 뮤직비디오 시청 기록 등록",
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
            404: openapi.Response(
                description="잘못된 요청",
                examples={
                    "application/json": [
                        {
                            "code": "M008_1",
                            "status": 404,
                            "message": "회원 정보를 찾을 수 없습니다."
                        },
                        {
                            "code": "M008_2",
                            "status": 404,
                            "message": "뮤직 비디오를 찾을 수 없습니다."
                        }
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
    def post(self, request, member_id, mv_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            response_data = {
                "code": "M008_1",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다"
            }
            logging.warning(f'WARNING {client_ip} {current_time} /history member 404 does not existing')
            return Response(response_data, status=404)

        try:
            mv = MusicVideo.objects.get(id=mv_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M008_2",
                "status": 404,
                "message": "뮤직 비디오를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} POST /history music_video 404 does not existing')
            return Response(response_data, status=404)

        try:
            history_test = History.objects.get(member_id=member, mv_id=mv)
            if history_test:
                response_data = {
                    "history_id": history_test.id,
                    "code": "M008_3",
                    "status": 409,
                    "message": "이미 시청한 기록이 있습니다."
                }
                logging.warning(f'INFO {client_ip} {current_time} /history 409 conflict')
                return Response(response_data, status=409)
        except:
            pass

        try:
            histories = History.objects.create(
                member_id=member,
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
            logging.info(f'INFO {client_ip} {current_time} GET /history 201 success')
            return Response(response_data, status=201)

        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} 500 failed: {str(e)}')
            response_data = {
                "code": "M008_4",
                "status": 500,
                "message": "서버 오류로 시청 기록을 추가할 수 없습니다.",

            }
            return Response(response_data, status=500)


class HistoryUpdateView(APIView):
    @swagger_auto_schema(
        operation_summary="사용자의 뮤직비디오 시청 기록 갱신",
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
                    "application/json": {
                        "code": "M009_1",
                        "status": 404,
                        "message": "시청 기록을 찾을 수 없습니다."
                    }
                }
            ),
        }
    )
    def patch(self, request, history_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            histories = History.objects.get(id=history_id)
            current_play_time = request.data.get('current_play_time', histories.current_play_time)
            histories.current_play_time = current_play_time
            histories.updated_at = datetime.now()
            histories.save()
            response_data = {
                "history_id": histories.id,
                "code": "M009",
                "status": 200,
                "message": "뮤직비디오 시청 기록 갱신 성공"
            }
            logging.info(f'INFO {client_ip} {current_time} PATCH /history/{history_id} 200 success')
            return Response(response_data, status=200)

        except History.DoesNotExist:
            response_data = {
                "code": "M009_1",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다"
            }
            logging.warning(
                f'WARNING {client_ip} {current_time} PATCH /history/{history_id} 404 Not Found')
            return Response(response_data, status=404)

        except Exception as e:
            response_data = {
                "code": "M009_2",
                "status": 500,
                "message": "서버 오류로 시청 기록을 갱신할 수 없습니다.",
            }
            logging.error(
                f'ERROR {client_ip} {current_time} PATCH /history/{history_id} 500 Internal Server Error')
            return Response(response_data, status=500)


class HistoryDetailView(APIView):
    @swagger_auto_schema(
        operation_summary="사용자의 뮤직비디오 시청 기록 조회",
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
    def get(self, request, member_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            response_data = {
                "code": "M010_1",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logging.warning(
                f'WARNING {client_ip} {current_time} /history/ 404 Not Found')
            return Response(response_data, status=404)

        member_histories = History.objects.filter(member_id=member).order_by('-updated_at')
        if not member_histories.exists():
            response_data = {
                "code": "M010_2",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다."
            }
            logging.warning(
                f'WARNING {client_ip} {current_time} /history/ 404 Not Found')
            return Response(response_data, status=404)

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
        logging.info(f'INFO {client_ip} {current_time} GET /histories 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MusicVideoSearchView(APIView):
    @swagger_auto_schema(
        operation_summary="뮤직비디오 검색",
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

        if mv_name:
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
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 404 not found')
            return Response({"error": "music videos not found"}, status=status.HTTP_404_NOT_FOUND)

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
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class MusicVideoStatusView(APIView):
    @swagger_auto_schema(
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
            return Response(response_data, status=http_status)
        except:
            response_data = {
                "code": "M012_4",
                "task_id": task_id,
                "HTTPstatus": 404,
                "message": "task가 존재하지 않습니다."
            }
            return Response(response_data, status=status.HTTP_404_NOT_FOUND)