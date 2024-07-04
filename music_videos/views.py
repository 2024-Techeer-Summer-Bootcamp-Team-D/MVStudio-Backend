import logging
import openai
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
import environ
from rest_framework import status
from datetime import datetime
from .serializers import CreateLyricsSerializer
from member.models import Member

env = environ.Env()
environ.Env.read_env()

OPENAI_API_KEY = env('OPENAI_API_KEY')

class CreateLyricsView(APIView):
    @swagger_auto_schema(
        operation_summary="가사 생성 API",
        operation_description="이 API는 가사를 생성하는 데 사용됩니다.",
        request_body=CreateLyricsSerializer,
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
        serializer = CreateLyricsSerializer(data=request.data)
        if serializer.is_valid():
            subject = serializer.validated_data['subject']
            genre = serializer.validated_data['genre']
            language = serializer.validated_data['language']
            vocal = serializer.validated_data['vocal']

            prompt = (
                f"Create song lyrics based on the keyword '{subject}'. "
                f"The genre should be {genre}, the language should be {language}, and the vocals should be suitable for {vocal} vocals. "
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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# class MusicVideo(APIView):
#     def post(self,request):
#         client_ip = request.META.get('REMOTE_ADDR', None)
#         current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         member_id = request.data['member_id']
#         try:
#             member = Member.objects.get(id=member_id)
#         except Member.DoesNotExist:
#             response_data = {
#                 "code": "P002",
#                 "status": 404,
#                 "message": "회원 정보가 없습니다."
#             }
#             logging.warning(f'WARNING {client_ip} {current_time} POST /music_videos 404 does not existing')
#             return Response(response_data, status=404)
#         data = request.data.copy()