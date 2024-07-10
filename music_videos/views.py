from urllib import request

from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from django.conf import settings
from django.core.paginator import Paginator
from member.models import Member
from .models import Genre, Instrument, MusicVideo, History
from .serializers import MusicVideoSerializer, GenreSerializer, InstrumentSerializer, MusicVideoDetailSerializer, MusicVideoDeleteSerializer, HistorySerializer

from datetime import datetime
import re
import logging
import openai
import requests
import json
import time
import boto3
import os
import cv2
import numpy as np
from moviepy.editor import AudioFileClip, concatenate_videoclips
from moviepy.video.VideoClip import ImageClip

from botocore.exceptions import NoCredentialsError

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
            openai.api_key = settings.OPENAI_API_KEY
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


# Dall-e 이미지 프롬프팅 코드
def Dall_e_image(verses, subject, vocal, genre_names_str):
    openai.api_key = settings.OPENAI_API_KEY
    image_url = []

    for i in range(4):
        prompt = f'''
        It's the image of a music video.
        The title of the song is {subject}.
        The main character of the music video is an animated {vocal} character and the genre of the song is a {genre_names_str}.
        
        {verses[i]}
        '''
        try:
            response = openai.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1792",
                quality="standard",
                n=1,
            )
            image_url.append(response.data[0].url)
        except Exception as e:
            if 'content_policy_violation' in str(e):
                i = i - 1
                pass
            else:
                print(f"Unhandled Exception: {e}")

    return image_url

def suno_music(genre_names_str, instruments_str, tempo, vocal, lyrics, subject):
    url = "https://api.sunoapi.com/api/v1/suno/create"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.SUNO_API_KEY}"
    }
    data = {
        "prompt": (
            lyrics
        ),
        "tags": f"{genre_names_str}, {instruments_str}, {tempo}, {vocal}",
        "custom_mode": True,
        "title": subject
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Unhandled Exception: {response}")
        print(response.text)

def suno_music_get(task_id):

    url = f"https://api.sunoapi.com/api/v1/suno/clip/{task_id}"
    headers = {
        "Authorization": f"Bearer {settings.SUNO_API_KEY}"
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()



def mv_create(image_urls, output_size, audio_url, member_id):
    # Function to read an image from a URL and return it as a numpy array
    def read_image_from_url(url):
        response = requests.get(url)
        image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is not None:
            return image
        return None  # Return None if the image is invalid

    # Function to download an audio file from a URL
    def download_audio(url, filename):
        response = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(response.content)

    # Function to create a video clip from an image
    def create_image_clip(image, duration, size):
        img = cv2.resize(image, size)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        clip = ImageClip(img_rgb).set_duration(duration)
        return clip

    # Function to upload a file to S3 and return the URL
    def upload_to_s3(file_obj, member_id, timestamp):
        s3 = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME,
                          aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        s3_bucket = settings.AWS_STORAGE_BUCKET_NAME

        s3_key = f"mv_videos/{member_id}_{timestamp}.mp4"
        try:
            s3.upload_file(file_obj, s3_bucket, s3_key)
            url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}{s3_key}"
            return url
        except NoCredentialsError:
            print("Credentials not available")
            return None

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # Temporary filename for the downloaded audio file
    audio_filename = f'temp_audio_{timestamp}.mp3'
    # Temporary filename for the video file
    video_filename = f'temp_video_{timestamp}.mp4'
    # Download the audio file
    download_audio(audio_url, audio_filename)

    # 오디오 파일의 길이를 네 등분하여 각 클립의 길이로 설정
    audio = AudioFileClip(audio_filename)
    total_duration = audio.duration
    clip_duration = total_duration / 4

    # 이미지 읽기 및 비디오 클립 생성
    image_clips = []
    for url in image_urls:
        img = read_image_from_url(url)
        if img is not None:
            clip = create_image_clip(img, clip_duration, output_size)
            image_clips.append(clip)
        else:
            print(f"{url}에서 이미지를 읽거나 처리하는 데 실패했습니다.")

    # 클립들을 크로스페이드 트랜지션으로 연결
    if image_clips:
        for i in range(len(image_clips) - 1):
            image_clips[i] = image_clips[i].crossfadeout(1)  # 1초 크로스페이드 아웃
            image_clips[i+1] = image_clips[i + 1].crossfadein(1)  # 1초 크로스페이드 인

        video = concatenate_videoclips(image_clips, method="compose")

        # 비디오에 오디오 추가
        final_video = video.set_audio(audio)

        final_video.write_videofile(video_filename, codec='libx264', fps=24)

        # 비디오를 S3에 업로드
        video_url = upload_to_s3(video_filename, member_id, timestamp)
        os.remove(audio_filename)
        os.remove(video_filename)
        if video_url:
            return video_url
        else:
            print("비디오를 S3에 업로드하는 데 실패했습니다.")
    else:
        os.remove(audio_filename)
        print("유효한 이미지가 없어 비디오를 생성할 수 없습니다.")


class MusicVideoView(APIView):
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
        subject = request.data['subject']
        vocal = request.data['vocal']
        tempo = request.data['tempo']
        member_id = request.data['member_id']
        language = request.data['language']
        # 장르 쉼표로 구분
        genres_ids = request.data['genres_ids']
        genres = Genre.objects.filter(id__in=genres_ids)
        genre_names = [str(genre) for genre in genres]
        genre_names_str = ", ".join(genre_names)

        instruments_ids = request.data['instruments_ids']
        instruments = Instrument.objects.filter(id__in=instruments_ids)
        instruments_names = [str(instrument) for instrument in instruments]
        instruments_str = ", ".join(instruments_names)


        # lyrics 값을 가져옴
        lyrics = request.data['lyrics']
        # 벌스별로 나누기 위해 정규 표현식 사용, 그리고 [Verse], [Bridge] 태그 제거
        verses = re.split(r'\[.*?\]\n', lyrics)
        # 빈 문자열 제거
        verses = [verse.strip() for verse in verses if verse.strip()]

        # Dall-e 이미지 프롬프팅 코드
        try:
            image_urls = Dall_e_image(verses,subject,vocal,genre_names_str)
        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_videos 500 {str(e)}')
            return Response({
                "code": "M005_1",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Suno 음악 프롬프팅 코드
        try:
            response = suno_music(genre_names_str, instruments_str, tempo, vocal, lyrics, subject)
            task_id = response['data']['task_id']
            while(True):
                time.sleep(2)
                result = suno_music_get(task_id)
                suno_status = result['data']['status']
                if suno_status=='completed':
                    break
            get_key = list(result['data']['clips'].keys())[1]
            audio_url = result['data']['clips'][get_key]['audio_url']
            cover_image_url = result['data']['clips'][get_key]['image_url']
            duration = result['data']['clips'][get_key]['metadata']['duration']

        except Exception as e:
            logging.error(f'ERROR {client_ip} {current_time} POST /music_videos 500 {str(e)}')
            return Response({
                "code": "M005_1",
                "status": 500,
                "message": f"서버 오류: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # music video Create
        output_size = (1024, 1792)

        video_url = mv_create(image_urls, output_size, audio_url, member_id)

        # 뮤직비디오 data
        data = {
            "member_id": member_id,
            "subject": subject,
            "language": language,
            "vocal": vocal,
            "length": duration,
            "cover_image": cover_image_url,
            "mv_file": video_url,
            "lyrics": lyrics,
            "genres_ids": genres_ids,
            "instruments_ids": instruments_ids,
            "tempo": tempo
        }
        # 뮤직비디오 및 벌스 객체 생성
        serializer = MusicVideoSerializer(data=data)
        if serializer.is_valid():
            music_video = serializer.save()

            response_data = {
                "code": "M002",
                "status": 201,
                "message": "뮤직비디오 생성 완료"
            }
            logging.info(f'INFO {client_ip} {current_time} POST /music_videos 201 music_video created')
            return Response(response_data, status=status.HTTP_201_CREATED)
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
                        "music_videos": [
                            # 여기에 예시 데이터를 포함하세요
                        ],
                        "code": "M004",
                        "HTTPstatus": 200,
                        "message": "뮤직비디오 정보 조회 성공",
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
            )
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
        if (sort=='countries'):
            member = Member.objects.get(id=member_id)
            members = Member.objects.filter(country_id=member.country_id)
            queryset = MusicVideo.objects.filter(member_id__in=members)
        else:
            queryset = queryset.order_by(f'-{sort}')
            message = f"뮤직비디오 {sort}순 정보 조회 성공"

        # 결과가 없는 경우 처리
        if not queryset.exists():
            logging.info(f'INFO {client_ip} {current_time} GET /music_videos 404 not found')
            return Response({"error": "music videos not found"}, status=status.HTTP_404_NOT_FOUND)

        # 페이지네이션
        page = request.query_params.get('page',1)
        size = request.query_params.get('size',10)
        paginator = Paginator(queryset, size)
        paginated_queryset = paginator.get_page(page)

        serializer = MusicVideoDetailSerializer(paginated_queryset, many=True)

        response_data = {
            'music_videos': serializer.data,
            "code": "M004",
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
                            "message": "뮤직비디오 삭제 성공"
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="해당하는 뮤직비디오가 존재하지 않습니다.",
                examples={
                    "application/json": {
                        "code": "M004_1",
                        "status": 404,
                        "message": "해당하는 뮤직비디오가 존재하지 않습니다."
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
                "message": "해당하는 뮤직비디오가 존재하지 않습니다."
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
                        "code": "M005",
                        "status": 200,
                        "message": "장르 리스트 조회 성공",
                        "data": {
                            "name": "string",
                            "code": "M005",
                            "HTTPstatus": 200,
                            "message": "장르 리스트 조회 성공"
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

class InstrumentListView(APIView):
    @swagger_auto_schema(
        operation_summary="악기 리스트 조회",
        operation_description="이 API는 사용자가 원하는 악기를 선택할 수 있도록 악기 리스트를 제공하는 기능을 합니다.",
        responses={
            200: openapi.Response(
                description="악기 리스트 조회 성공",
                examples={
                    "application/json": {
                        "code": "M006",
                        "status": 200,
                        "message": "악기 리스트 조회 성공",
                        "data": {
                            "name": "string",
                            "code": "M006",
                            "HTTPstatus": 200,
                            "message": "악기 리스트 조회 성공"
                        }
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
            serializer = GenreSerializer(instruments, many=True)
            response_data = {
                "code": "M006",
                "status": 200,
                "message": "악기 리스트 조회 성공",
                "data": serializer.data
            }
            logging.info(f'INFO {client_ip} {current_time} GET /instrument_list 200 success')
            return Response(response_data, status=200)
        except Exception as e:
            response_data = {
                "code": "M006_1",
                "status": 500,
                "message": "악기 리스트를 불러올 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /instrument_list 500 failed')
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
                            # 여기에 직렬화된 뮤직비디오 상세 정보의 예시를 포함하세요
                        }
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직비디오 정보가 없습니다.",
                examples={
                    "application/json": {
                        "code": "M003_1",
                        "status": 404,
                        "message": "뮤직비디오 정보가 없습니다."
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
            # recently_viewed 값 +1
            music_video.recently_viewed += 1
            # 변경 사항 저장
            music_video.save()
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M003_1",
                "status": 404,
                "message": "뮤직비디오 정보가 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} GET /music_videos 404 does not existing')
            return Response(response_data, status=404)

        serializer = MusicVideoDetailSerializer(music_video)
        response_data = {
            "code": "M003",
            "status": 200,
            "message": "뮤직비디오 상세 정보 조회 성공"
        }
        logging.info(f'INFO {client_ip} {current_time} GET /music_videos 200 view success')
        return Response(serializer.data, status=200)


class HistoryCreateView(APIView):
    @swagger_auto_schema(
        operation_summary="사용자의 뮤직비디오 시청 기록 생성",
        operation_description="사용자가 특정 뮤직비디오를 조회했을 때 시청 기록을 생성합니다.",
        responses={
            200: openapi.Response(
                description="이미 시청한 기록이 있습니다.",
                examples={
                    "application/json": {
                        "code": "M008_1",
                        "status": 200,
                        "message": "이미 시청한 기록이 있습니다.",
                    }
                }
            ),
            201: openapi.Response(
                description="사용자의 뮤직비디오 시청 기록 생성 완료",
                examples={
                    "application/json": {
                        "code": "M008",
                        "status": 201,
                        "message": "사용자의 뮤직비디오 시청 기록 생성 완료",
                    }
                }
            ),
            404: openapi.Response(
                description="뮤직 비디오를 찾을 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M008_2",
                        "status": 404,
                        "message": "뮤직 비디오를 찾을 수 없습니다."
                    }
                }
            ),
            500: openapi.Response(
                description="서버 오류로 시청 기록을 추가할 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M008_3",
                        "status": 404,
                        "message": "서버 오류로 시청 기록을 추가할 수 없습니다."
                    }
                }
            )
        }
    )
    def post(self, request, member_id, mv_id):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            response_data = {
                "code": "M008_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다"
            }
            logging.warning(f'WARNING {client_ip} {current_time} POST /history 404')
            return Response(response_data, status=404)

        try:
            history_test = History.objects.get(member_id=member, mv_id=mv_id)
            if history_test:
                response_data = {
                    "history_id": history_test.id,
                    "code": "M008_1",
                    "status": 200,
                    "message": "이미 시청한 기록이 있습니다."
                }
                logging.warning(f'INFO {client_ip} {current_time} GET /history 200')
                return Response(response_data, status=200)
        except:
            pass

        try:
            mv = MusicVideo.objects.get(id=mv_id)
        except MusicVideo.DoesNotExist:
            response_data = {
                "code": "M008_3",
                "status": 404,
                "message": "뮤직 비디오를 찾을 수 없습니다."
            }
            logging.warning(f'WARNING {client_ip} {current_time} POST /history 404 Not Found')
            return Response(response_data, status=404)

        try:
            histories = History.objects.create(
                member_id=member,
                mv_id=mv,
                current_play_time=0,
                is_deleted=False
            )
            response_data = {
                "history_id": "history.id",
                "code": "M008",
                "status": 201,
                "message": "시청 기록 추가 성공"
            }
            serializer = HistorySerializer(histories)
            mv.views += 1
            mv.recently_viewed += 1
            mv.save()
            logging.info(f'INFO {client_ip} {current_time} GET /history 201 success')
            return Response(serializer.data, status=201)

        except Exception as e:
            response_data = {
                "code": "M008_4",
                "status": 500,
                "message": "서버 오류로 시청 기록을 추가할 수 없습니다.",
            }
            logging.warning(f'WARNING {client_ip} {current_time} 500 failed')
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
            500: openapi.Response(
                description="서버 오류로 시청 기록을 갱신할 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M009_2",
                        "status": 500,
                        "message": "서버 오류로 시청 기록을 갱신할 수 없습니다."
                    }
                }
            )
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
                "message": "시청 기록 갱신 성공"
            }
            logging.info(f'INFO {client_ip} {current_time} PATCH /history/{history_id} 200 success')
            return Response(response_data, status=200)

        except History.DoesNotExist:
            response_data = {
                "code": "M009_1",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다."
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
            ),404: openapi.Response(
                description="요청하는 정보를 찾을 수 없습니다.",
                examples={
                    "application/json": {
                        "code": "M010_1",
                        "status": 404,
                        "message": "요청하는 정보를 찾을 수 없습니다."
                    }
                }
            )
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
                "message": "멤버를 찾을 수 없습니다."
            }
            logging.warning(
                f'WARNING {client_ip} {current_time} /history/ 404 Not Found')
            return Response(response_data, status=404)
        try:
            member_histories = History.objects.filter(member_id=member).order_by('-updated_at')
        except History.DoesNotExist:
            response_data = {
                "code": "M010_2",
                "status": 404,
                "message": "시청 기록을 찾을 수 없습니다."
            }
            logging.warning(
                f'WARNING {client_ip} {current_time} /history/ 404 Not Found')
            return Response(response_data, status=404)

        watch_mv_id = member_histories.values_list('mv_id', flat=True)
        watch_music_videos = MusicVideo.objects.filter(id__in=watch_mv_id)

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



