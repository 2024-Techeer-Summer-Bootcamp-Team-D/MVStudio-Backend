from rest_framework import serializers, viewsets
from .models import Member
from django.db import IntegrityError


class MemberSerializer(serializers.Serializer):
    login_id = serializers.CharField()
    nickname = serializers.CharField()
    password = serializers.CharField(write_only=True)
    age = serializers.IntegerField()
    sex = serializers.CharField()
    youtube_account = serializers.CharField()
    instagram_account = serializers.CharField()

    def create(self, validated_data):
        login_id = validated_data.get('login_id')
        nickname = validated_data.get('nickname')
        password = validated_data.get('password')
        age = validated_data.get('age')
        sex = validated_data.get('sex')
        youtube_account = validated_data.get('youtube_account')
        instagram_account = validated_data.get('instagram_account')

        try:
            member = Member(login_id=login_id, nickname=nickname, password=password, 
                            age=age, sex=sex, youtube_account=youtube_account,
                            instagram_account=instagram_account)
            member.save()
            return {
                "code": "M001",
                "status": 201,
                "message": "회원가입 완료"
            }
        except IntegrityError as e:
            # 중복된 login_id가 이미 존재하는 경우의 예외 처리
            return {
                "code": "M002",
                "status": 400,
                "message": "이미 존재하는 로그인 ID입니다."
            }