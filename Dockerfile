# 베이스 이미지를 선택합니다. 여기서는 Python 3.10을 사용합니다.
FROM python:3.10

# 환경 변수를 설정합니다.
ENV PYTHONUNBUFFERED 1

# 작업 디렉토리를 설정합니다.
WORKDIR /MVStudio-Backend

# 요구사항 파일을 복사합니다.
COPY ./requirements.txt /requirements.txt

# Python 패키지를 설치합니다.
RUN pip install --upgrade -r /requirements.txt

# 프로젝트 파일을 모두 복사합니다.
COPY . ./

# Django의 collectstatic 명령어를 실행합니다.
RUN python manage.py collectstatic --noinput