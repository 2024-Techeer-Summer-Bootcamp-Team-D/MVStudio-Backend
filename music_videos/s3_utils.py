import boto3
from threading import Lock
from django.conf import settings

lock = Lock()

def upload_file_to_s3(file, key, ExtraArgs):
    with lock:
        s3 = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME,
                          aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                          aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        s3_bucket = settings.AWS_STORAGE_BUCKET_NAME

        try:
            if ExtraArgs['ContentType'] == 'video/mp4':
                s3.upload_file(file, s3_bucket, key, ExtraArgs)
            else:
                s3.upload_fileobj(file, s3_bucket, key, ExtraArgs)

            url = f"https://{settings.AWS_S3_CUSTOM_DOMAIN}{key}"

            return url

        except Exception as e:
            print(f"error : {e}")
            return None
