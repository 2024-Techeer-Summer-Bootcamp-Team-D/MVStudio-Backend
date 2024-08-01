# tasks.py

from music_videos.models import MusicVideo
from config.celery import app
from django.conf import settings
from django.contrib.auth import get_user_model

from .serializers import MusicVideoSerializer
from .s3_utils import upload_file_to_s3

from datetime import datetime
import json
import time
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, vfx
from moviepy.decorators import apply_to_audio, apply_to_mask, requires_duration
import requests
import tempfile
import logging
import os
from io import BytesIO
from PIL import Image
import numpy as np

User = get_user_model()

logger = logging.getLogger(__name__)
@app.task
def hot_music_video_scheduled():
    MusicVideo.objects.update(recently_viewed=0)
    print("All MusicVideo recently_viewed columns have been reset to 0.")
    logger.info("All MusicVideo recently_viewed columns have been reset to 0.")

@app.task
def rebuild_elasticsearch_index():
    os.system('python manage.py search_index --rebuild -f')

@app.task(queue='music_queue')
def suno_music(genre_names_str, instruments_str, tempo, vocal, lyrics, subject):
    url = "https://api.sunoapi.com/api/v1/suno/create"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.SUNO_API_KEY}"
    }
    data = {
        "prompt": lyrics,
        "tags": f"Under 60 seconds, {genre_names_str}, {instruments_str}, {tempo}, {vocal} vocal, short music",
        "custom_mode": True,
        "title": subject
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error creating Suno task: {e}")
        return {"error": "Error creating Suno task", "details": str(e)}

    if response.status_code == 200:
        task_id = response.json()['data']['task_id']

        timeout = 15 * 60
        elapsed_time = 0
        polling_interval = 30

        while (True):
            time.sleep(polling_interval)
            elapsed_time += polling_interval

            if elapsed_time > timeout:
                return {"error": "Polling timeout exceeded 15 minutes"}

            url = f"https://api.sunoapi.com/api/v1/suno/clip/{task_id}"
            headers = {
                "Authorization": f"Bearer {settings.SUNO_API_KEY}"
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                suno_status = result['data']['status']
                if suno_status == 'completed':
                    break
            else:
                return
        get_key1 = list(result['data']['clips'].keys())[0]
        get_key2 = list(result['data']['clips'].keys())[1]

        duration1 = result['data']['clips'][get_key1]['metadata']['duration']
        duration2 = result['data']['clips'][get_key2]['metadata']['duration']

        if(duration2 < duration1):
            audio_url = result['data']['clips'][get_key2]['audio_url']
            return audio_url, duration2
        else:
            audio_url = result['data']['clips'][get_key1]['audio_url']
            return audio_url, duration1
    else:
        return {"error": "Failed to create Suno task", "status_code": response.status_code}

@requires_duration
@apply_to_mask
@apply_to_audio
def time_mirror(clip):
    duration_per_frame = 1 / clip.fps
    return clip.fl_time(lambda t: np.max(clip.duration - t - duration_per_frame, 0), keep_duration=True)
def create_reversed_video_clip(url, clip_count, last_clip_size):
    # URL에서 비디오 파일 다운로드
    response = requests.get(url)

    # 임시 파일에 비디오 데이터 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video_file:
        temp_video_file.write(response.content)
        temp_video_path = temp_video_file.name

    # 비디오 파일 로드
    video = VideoFileClip(temp_video_path)

    # 비디오를 역재생
    reversed_video = time_mirror(video)

    # 기본 재생 클립과 역재생 클립을 이어붙임
    plus_clip = concatenate_videoclips([video, reversed_video])

    if (clip_count == 1):
        reversed_video_cut = reversed_video.subclip(0, last_clip_size)
        final_clip = concatenate_videoclips([video, reversed_video_cut])
    else:
        clips = [plus_clip] * (clip_count // 2)
        if (clip_count % 2 == 0):
            video_cut = video.subclip(0, last_clip_size)
            clips.append(video_cut)
            final_clip = concatenate_videoclips(clips)
        else:
            clips.append(video)
            reversed_video_cut = reversed_video.subclip(0, last_clip_size)
            clips.append(reversed_video_cut)
            final_clip = concatenate_videoclips(clips)
    final_clip = final_clip.fadein(1).fadeout(1)

    return final_clip



@app.task(queue='video_queue')
def create_video(line, style):
    url = "https://api.aivideoapi.com/runway/generate/text"

    payload = {
        "text_prompt": f"masterpiece, {style}, {line}",
        "model": "gen3",
        "width": 1280,
        "height": 768,
        "motion": 5,
        "seed": 0,
        "upscale": True,
        "interpolate": True,
        "callback_url": ""
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": settings.RUNWAYML_API_KEY
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        uuid = data['uuid']
    except Exception as e:
        logger.error(f'create video task error data : {data} error : {str(e)}')
        try:
            response = requests.post(url, json=payload, headers=headers)
            uuid = response.json()['uuid']
        except Exception as e:
            logger.error(f'create video task error data : {data} error : {str(e)}')
            return False

    url = f"https://api.aivideoapi.com/status?uuid={uuid}"

    headers = {
        "accept": "application/json",
        "Authorization": settings.RUNWAYML_API_KEY
    }

    timeout = 30 * 60  # 30 minutes in seconds
    elapsed_time = 0
    polling_interval = 15  # seconds

    while (True):
        time.sleep(polling_interval)
        elapsed_time += polling_interval

        if elapsed_time > timeout:
            return {"error": "Polling timeout exceeded 30 minutes"}
        try:
            response = requests.get(url, headers=headers).json()
            if (response['status'] == 'success'):
                break
            elif(response['status'] == 'failed'):
                return False
        except Exception as e:
            logger.error(f'create video task error data : {response.json()} error : {str(e)}')
            return False
    return response['url']



@app.task(queue='final_queue')
def mv_create(results, client_ip, current_time, subject, language, vocal, lyrics, genres_ids, instruments_ids, tempo, username, style_id):
    audio_url = results[0][0]
    duration = results[0][1]
    urls = results[1:]

    for url in urls:
        if url is False:
            urls.remove(url)
    urls_count = len(urls)
    one_clip_size = (duration / urls_count)
    clip_count = int(one_clip_size // 5)
    last_clip_size = one_clip_size % 5

    clips = []
    for url in urls:
        clip = create_reversed_video_clip(url, clip_count, last_clip_size)
        clips.append(clip)
    video = concatenate_videoclips(clips, method="compose")

    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # Function to download an audio file from a URL
    def download_audio(url, filename):
        response = requests.get(url)
        with open(filename, 'wb') as f:
            f.write(response.content)

    # Temporary filename for the downloaded audio file
    audio_filename = f'temp_audio_{timestamp}.mp3'
    # Temporary filename for the video file
    video_filename = f'temp_video_{timestamp}.mp4'
    # Download the audio file
    download_audio(audio_url, audio_filename)

    audio = AudioFileClip(audio_filename)


    # 특정 시간(time)에서 프레임 추출
    frame = video.get_frame(1)
    image = Image.fromarray(frame)

    # 이미지를 BytesIO 객체에 저장
    buffer = BytesIO()
    image.save(buffer, 'PNG')
    buffer.seek(0)

    # 비디오에 오디오 추가
    final_video = video.set_audio(audio)

    final_video.write_videofile(video_filename, codec='libx264', fps=24)

    # 비디오를 S3에 업로드
    content_type = 'video/mp4'
    s3_key = f"mv_videos/{username}_{timestamp}.mp4"
    video_url = upload_file_to_s3(video_filename, s3_key, ExtraArgs={
        "ContentType": content_type,
    })

    cover_image_url = upload_file_to_s3(buffer, f"cover_images/{username}_{timestamp}.png", {"ContentType": "image/png"})

    if clips:
        os.remove(audio_filename)
        os.remove(video_filename)
        # 뮤직비디오 data
        data = {
            "username": username,
            "subject": subject,
            "language": language,
            "vocal": vocal,
            "length": duration,
            "cover_image": cover_image_url,
            "mv_file": video_url,
            "lyrics": lyrics,
            "genres_ids": genres_ids,
            "instruments_ids": instruments_ids,
            "tempo": tempo,
            "style_id": style_id
        }
        # 뮤직비디오 및 벌스 객체 생성
        serializer = MusicVideoSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            logging.info(f'INFO {client_ip} {current_time} POST /music_videos 201 music_video created')
            return
        return False
    else:
        os.remove(audio_filename)
        os.remove(video_filename)
        print("유효한 이미지가 없어 비디오를 생성할 수 없습니다.")
        return