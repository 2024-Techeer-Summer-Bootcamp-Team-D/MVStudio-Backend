# tasks.py

from music_videos.models import MusicVideo
from config.celery import app
from django.conf import settings

from .serializers import MusicVideoSerializer
from .s3_utils import upload_file_to_s3

from datetime import datetime
import requests
import json
import time
import cv2
import numpy as np
from moviepy.editor import AudioFileClip, concatenate_videoclips
from moviepy.video.VideoClip import ImageClip
import openai
import logging
import os

logger = logging.getLogger(__name__)
@app.task
def hot_music_video_scheduled():
    MusicVideo.objects.update(recently_viewed=0)
    print("All MusicVideo recently_viewed columns have been reset to 0.")
    logger.info("All MusicVideo recently_viewed columns have been reset to 0.")

@app.task
def rebuild_elasticsearch_index():
    os.system('python manage.py search_index --rebuild -f')
def Dall_e_image(verses, subject, vocal, genre_names_str):
    openai.api_key = settings.OPENAI_API_KEY
    image_url = []
    i = 0

    while i < 4:
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
            i += 1
        except Exception as e:
            if 'content_policy_violation' in str(e):
                print(f'{e}')
                # i를 감소시키지 않고, 단지 다시 시도하도록 놔둡니다.
                pass
            else:
                print(f"Unhandled Exception: {e}")
                i += 1  # 예외가 발생해도 다음으로 넘어가기 위해 i를 증가시킵니다.

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
        content_type = 'video/mp4'
        s3_key = f"mv_videos/{member_id}_{timestamp}.mp4"

        video_url = upload_file_to_s3(video_filename, s3_key, ExtraArgs={
            "ContentType": content_type,
        })

        os.remove(audio_filename)
        os.remove(video_filename)
        if video_url:
            return video_url
    else:
        os.remove(audio_filename)
        os.remove(video_filename)
        print("유효한 이미지가 없어 비디오를 생성할 수 없습니다.")


@app.task
def create_music_video(client_ip, current_time, subject, vocal, tempo, member_id, language, genre_names_str, instruments_str, verses, lyrics, genres_ids, instruments_ids):
    # Suno 음악 프롬프팅 코드
    try:
        response = suno_music(genre_names_str, instruments_str, tempo, vocal, lyrics, subject)
        task_id = response['data']['task_id']

    except Exception as e:
        logging.error(f'ERROR {client_ip} {current_time} POST /music_videos 500 {str(e)}')
        return

    # Dall-e 이미지 프롬프팅 코드
    try:
        image_urls = Dall_e_image(verses, subject, vocal, genre_names_str)
    except Exception as e:
        logging.error(f'ERROR {client_ip} {current_time} POST /music_videos 500 {str(e)}')
        return

    try:
        while (True):
            time.sleep(2)
            result = suno_music_get(task_id)
            suno_status = result['data']['status']
            if suno_status == 'completed':
                break
        get_key = list(result['data']['clips'].keys())[1]
        audio_url = result['data']['clips'][get_key]['audio_url']
        cover_image_url = result['data']['clips'][get_key]['image_url']
        duration = result['data']['clips'][get_key]['metadata']['duration']
    except Exception as e:
        logging.error(f'ERROR {client_ip} {current_time} POST /music_videos 500 {str(e)}')
        return

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
        serializer.save()
        logging.info(f'INFO {client_ip} {current_time} POST /music_videos 201 music_video created')
        return
