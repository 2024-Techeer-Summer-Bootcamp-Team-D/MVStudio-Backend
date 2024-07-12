# member/serializers.py

from rest_framework import serializers
from django.db import IntegrityError
from .models import Member, Country
from django.db import IntegrityError

class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'login_id', 'nickname', 'password', 'birthday', 'sex', 'country']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        try:
            member = Member.objects.create(
                login_id=validated_data['login_id'],
                nickname=validated_data['nickname'],
                password=validated_data['password'],
                birthday=validated_data['birthday'],
                sex=validated_data['sex'],
                country=validated_data['country'],
            )
            return member
        except IntegrityError as e:
            existing_member = Member.objects.get(login_id=validated_data['login_id'])
            return existing_member

class MemberDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['login_id', 'nickname', 'profile_image', 'comment', 'country', 'birthday', 'youtube_account', 'instagram_account']


class MemberLoginSerializer(serializers.Serializer):
    login_id = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)

    def validate(self, data):
        login_id = data.get('login_id')
        password = data.get('password')

        if not Member.objects.filter(login_id=login_id).exists():
            raise serializers.ValidationError("로그인 실패: 해당 로그인 ID가 존재하지 않습니다.")

        if not Member.objects.filter(login_id=login_id, password=password).exists():
            raise serializers.ValidationError("로그인 실패: 로그인 ID 또는 비밀번호가 잘못되었습니다.")

        return data

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name']