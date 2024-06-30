FROM python:3.10

ENV PYTHONUNBUFFERED 1

WORKDIR /MVStudio-Backend

COPY ./requirements.txt /requirements.txt

RUN pip install --upgrade -r /requirements.txt

COPY . ./

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]