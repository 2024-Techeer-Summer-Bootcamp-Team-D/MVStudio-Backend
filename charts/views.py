from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from oauth.mixins import ApiAuthMixin, PublicApiMixin

from member.models import Member, Country
from music_videos.models import History, MusicVideo

from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DailyChartView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="날짜별 조회수 통계 차트 조회 API",
        operation_description="사용자의 채널을 날짜별 조회수를 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="날짜별 조회수 통계 차트 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "C001_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "daily_views": [
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                                {
                                    "daily_views_date": "yyyy-mm-dd",
                                    "daily_views_views": 0,
                                },
                            ]
                        }
                        },
                        {
                        "code": "C001",
                        "status": 200,
                        "message": "날짜별 조회수 통계 차트 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "daily_views": [
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            {
                                "daily_views_date": "yyyy-mm-dd",
                                "daily_views_views": 0,
                            },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="날짜별 조회수 통계 차트 조회 실패",
                examples={
                    "application/json": {
                        "code": "C001_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )

    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "C001_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member)

        start_date = member.created_at.date()
        end_date = datetime.now().date()
        date_range = (end_date - start_date).days + 1
        daily_views = {(start_date + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(date_range)}

        history_data = (History.objects
                        .filter(mv_id__in=music_videos)
                        .annotate(day=TruncDate('created_at'))
                        .values('day')
                        .annotate(views=Count('id'))
                        .order_by('day'))

        for data in history_data:
            daily_views[data['day'].strftime('%Y-%m-%d')] = data['views']

        if not music_videos.exists():
            response_data = {
                "code": "C001_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "daily_views": [
                    {
                        "daily_views_date": date,
                        "daily_views_views": views
                    } for date, views in daily_views.items()
                ],
            }
            logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            total_views += music_video.views
            if music_video.views >= popular_mv_views and music_video.views != 0:
                popular_mv_subject.append(music_video.subject)
                popular_mv_views = music_video.views

        response_data = {
            "code": "C001",
            "status": 200,
            "message": "날짜별 조회수 통계 차트 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "daily_views": [
                    {
                        "daily_views_date": date,
                        "daily_views_views": views,
                    } for date, views in daily_views.items()
                ],
        }
        logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class GenderChartView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="성별 통계 차트 조회 API",
        operation_description="사용자의 채널을 성별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="성별 통계 차트 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "C002_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "gender_list": [
                                {
                                    "gender_name": "string",
                                    "gender_number": 0,
                                },
                                ]
                        }
                        },
                        {
                        "code": "C002",
                        "status": 200,
                        "message": "성별 통계 차트 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "gender_list": [
                            {
                                "gender_name": "string",
                                "gender_number": 0,
                            },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="성별 통계 차트 조회 실패",
                examples={
                    "application/json": {
                        "code": "C002_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "C002_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        gender_list = [
            {'gender_name': 'Male', 'gender_number': 0},
            {'gender_name': 'Female', 'gender_number': 0},
        ]

        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                member_gender = Member.objects.get(username=viewer).sex
                if member_gender == "M":
                    gender_list[0]['gender_number'] += 1
                elif member_gender == "F":
                    gender_list[1]['gender_number'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "C002_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "gender_list": [
                    {
                        "gender_name": item['gender_name'],
                        "gender_number": item['gender_number']
                    } for item in gender_list
                ],
            }
            logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "C002",
            "status": 200,
            "message": "성별 통계 차트 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "gender_list": [
                    {
                        "gender_name": item['gender_name'],
                        "gender_number": item['gender_number']
                    } for item in gender_list
                ],
        }
        logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class CountryChartView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="국가별 통계 차트 조회 API",
        operation_description="사용자의 채널을 국가별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="국가별 통계 차트 조회 성공",
                examples={
                    "application/json": [
                        {
                        "code": "C003_1",
                        "status": 200,
                        "message": "사용자 채널 개수가 0개입니다.",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "",
                            "popular_mv_views": 0,
                            "country_list": [
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                ]
                        }
                        },
                        {
                        "code": "C003",
                        "status": 200,
                        "message": "국가별 통계 차트 조회 성공",
                        "data": {
                            "member_name": "string",
                            "total_mv": 0,
                            "total_views": 0,
                            "popular_mv_subject": "string",
                            "popular_mv_views": 0,
                            "country_list": [
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                                {
                                    "country_id": 0,
                                    "country_name": "string",
                                    "country_views": 0,
                                },
                            ],
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="국가별 통계 차트 조회 실패",
                examples={
                    "application/json": {
                        "code": "C003_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "C003_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        countries = Country.objects.filter(is_deleted=False)
        country_list = []
        for country in countries:
            country_list.append({
                'country_id': country.id,
                'country_name': country.name,
                'country_views': 0
            })

        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                member_country = Member.objects.get(username=viewer).country
                for country in country_list:
                    if member_country.name == country['country_name']:
                        country['country_views'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "C003_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "country_list": [
                    {
                        'country_id': item['country_id'],
                        'country_name': item['country_name'],
                        'country_views': item['country_views']
                    } for item in country_list
                ],
            }
            logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "C003",
            "status": 200,
            "message": "국가별 통계 차트 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "country_list": [
                {
                    'country_id': item['country_id'],
                    'country_name': item['country_name'],
                    'country_views': item['country_views']
                } for item in country_list
            ],
        }
        logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)


class AgeChartView(ApiAuthMixin, APIView):
    @swagger_auto_schema(
        operation_summary="연령별 통계 차트 조회 API",
        operation_description="사용자의 채널을 연령별 통계로 분석할 수 있습니다.",
        responses={
            200: openapi.Response(
                description="연령별 통계 차트 조회 성공",
                examples={
                    "application/json": [
                        {
                            "code": "C004_1",
                            "status": 200,
                            "message": "사용자 채널 개수가 0개입니다.",
                            "data": {
                                "member_name": "string",
                                "total_mv": 0,
                                "total_views": 0,
                                "popular_mv_subject": "",
                                "popular_mv_views": 0,
                                "age_list": [
                                    {
                                        "age_group": "string",
                                        "age_views": 0
                                    },
                                ]
                            }
                        },
                        {
                            "code": "C004",
                            "status": 200,
                            "message": "연령별 통계 차트 조회 성공",
                            "data": {
                                "member_name": "string",
                                "total_mv": 0,
                                "total_views": 0,
                                "popular_mv_subject": "string",
                                "popular_mv_views": 0,
                                "age_list": [
                                    {
                                        "age_group": "string",
                                        "age_views": 0
                                    },
                                ]
                            }
                        }
                    ]
                }
            ),
            404: openapi.Response(
                description="사용자 채널 연령별 통계 조회 실패",
                examples={
                    "application/json": {
                        "code": "C004_2",
                        "status": 404,
                        "message": "회원 정보를 찾을 수 없습니다."
                    }
                }
            )
        }
    )
    def get(self, request, username):
        client_ip = request.META.get('REMOTE_ADDR', None)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            member = Member.objects.get(username=username)
        except Member.DoesNotExist:
            response_data = {
                "code": "C004_2",
                "status": 404,
                "message": "회원 정보를 찾을 수 없습니다."
            }
            logger.warning(f'WARNING {client_ip} {current_time} /music_videos 404 Member Not Found')
            return Response(response_data, status=404)

        member_name = member.nickname
        music_videos = MusicVideo.objects.filter(username=member.username).values_list('id', flat=True)

        age_list = [
            {'age_group': '10s and under', 'age_views': 0},
            {'age_group': '20s', 'age_views': 0},
            {'age_group': '30s', 'age_views': 0},
            {'age_group': '40s', 'age_views': 0},
            {'age_group': '50s and above', 'age_views': 0}
        ]

        current_year = datetime.now().year
        processed_viewers = set()

        for video in music_videos:
            viewers = History.objects.filter(mv_id=video).values_list('username', flat=True)
            for viewer in viewers:
                if viewer in processed_viewers:
                    continue
                processed_viewers.add(viewer)
                viewer_member = Member.objects.get(username=viewer)
                birth_date = viewer_member.birthday
                birth_year = birth_date.year
                age = current_year - birth_year
                if age < 20:
                    age_list[0]['age_views'] += 1
                elif age < 30:
                    age_list[1]['age_views'] += 1
                elif age < 40:
                    age_list[2]['age_views'] += 1
                elif age < 50:
                    age_list[3]['age_views'] += 1
                else:
                    age_list[4]['age_views'] += 1

        if not music_videos.exists():
            response_data = {
                "code": "C004_1",
                "status": 200,
                "message": "사용자 채널 개수가 0개입니다.",
                "member_name": member_name,
                "total_mv": 0,
                "total_views": 0,
                "popular_mv_subject": "",
                "popular_mv_views": 0,
                "age_list": [
                    {
                        'age_group': item['age_group'],
                        'age_views': item['age_views']
                    } for item in age_list
                ],
            }
            logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 No music videos')
            return Response(response_data, status=200)

        total_mv = music_videos.count()
        total_views = 0
        popular_mv_subject = []
        popular_mv_views = 0

        for music_video in music_videos:
            mv_views = MusicVideo.objects.get(id=music_video).views
            total_views += mv_views
            if mv_views >= popular_mv_views and mv_views != 0:
                popular_mv_subject.append(MusicVideo.objects.get(id=music_video).subject)
                popular_mv_views = mv_views

        response_data = {
            "code": "C004",
            "status": 200,
            "message": "연령별 통계 차트 조회 성공",
            "member_name": member_name,
            "total_mv": total_mv,
            "total_views": total_views,
            "popular_mv_subject": popular_mv_subject,
            "popular_mv_views": popular_mv_views,
            "age_list": [
                {
                    'age_group': item['age_group'],
                    'age_views': item['age_views']
                } for item in age_list
            ],
        }
        logger.info(f'INFO {client_ip} {current_time} GET /music_videos 200 views success')
        return Response(response_data, status=status.HTTP_200_OK)

