# tasks.py

from music_videos.models import MusicVideo
from config.celery import app
from celery import group, chain, chord
from django.conf import settings

from .serializers import MusicVideoSerializer
from .s3_utils import upload_file_to_s3

from datetime import datetime
import requests
import json
import time
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, vfx
import requests
import tempfile
import logging
import os
from io import BytesIO
from PIL import Image

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
        "prompt": (
            lyrics
        ),
        "tags": f"{genre_names_str}, {instruments_str}, {tempo}, {vocal}",
        "custom_mode": True,
        "title": subject
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        task_id = response.json()['data']['task_id']

        while (True):
            time.sleep(5)

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
        get_key = list(result['data']['clips'].keys())[1]
        audio_url = result['data']['clips'][get_key]['audio_url']
        duration = result['data']['clips'][get_key]['metadata']['duration']

        print(audio_url)
        print(duration)

        return audio_url, duration
    else:
        return


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
    reversed_video = video.fx(vfx.time_mirror)

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
            clips.append(reversed_video)
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
        "width": 1344,
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

    response = requests.post(url, json=payload, headers=headers)
    uuid = response.json()['uuid']

    url = f"https://api.aivideoapi.com/status?uuid={uuid}"

    headers = {
        "accept": "application/json",
        "Authorization": settings.RUNWAYML_API_KEY
    }

    while (True):
        time.sleep(15)
        response = requests.get(url, headers=headers).json()
        if (response['status'] == 'success'):
            break

    print('video 생성 성공',response['url'])
    return response['url']



@app.task(queue='final_queue')
def mv_create(results, client_ip, current_time, subject, language, vocal, lyrics, genres_ids, instruments_ids, tempo, member_id):
    audio_url = results[0][0]
    duration = results[0][1]
    urls = results[1:]
    one_clip_size = (duration / 8)
    clip_count = int(one_clip_size // 4)
    last_clip_size = one_clip_size % 4

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
    s3_key = f"mv_videos/{member_id}_{timestamp}.mp4"
    video_url = upload_file_to_s3(video_filename, s3_key, ExtraArgs={
        "ContentType": content_type,
    })

    cover_image_url = upload_file_to_s3(buffer, f"cover_images/{member_id}_{timestamp}.png", {"ContentType": "image/png"})

    if clips:
        os.remove(audio_filename)
        os.remove(video_filename)
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
    else:
        os.remove(audio_filename)
        os.remove(video_filename)
        print("유효한 이미지가 없어 비디오를 생성할 수 없습니다.")


@app.task
def create_music_video(client_ip, current_time, subject, vocal, tempo, member_id, language, genre_names_str, instruments_str, filtered_lines, lyrics, genres_ids, instruments_ids, style):

    music_task = suno_music.s(genre_names_str, instruments_str, tempo, vocal, lyrics, subject)
    print("music_task 성공", music_task)
    video_tasks = group(
        create_video.s(line, style) for line in filtered_lines
    )
    print("video_tasks 성공", video_tasks)
    music_video_task = chord(
        header = [music_task] + video_tasks.tasks,
        body = mv_create.s(client_ip, current_time, subject, language, vocal, lyrics, genres_ids, instruments_ids, tempo, member_id)
    )
    result = music_video_task.apply_async()
    return result.id
