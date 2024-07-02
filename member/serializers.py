from rest_framework import serializers, viewsets
from .models import Member
from django.db import IntegrityError


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id','login_id','nickname','password','age','sex','country']
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def create(self, validated_data):
        try:
            member = Member.objects.create(
                login_id=validated_data['login_id'],
                nickname=validated_data['nickname'],
                password=validated_data['password'],
                age=validated_data['age'],
                sex=validated_data['sex'],
                country=validated_data['country'],
            )
            return member
        except IntegrityError as e:
            raise serializers.ValidationError({"login_id": "This login_id is already in use."})


class MemberDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['login_id', 'nickname', 'age', 'sex', 'country']
        
    def update(self, instance, validated_data):
        instance.nickname = validated_data.get('nickname', instance.nickname)
        instance.country = validated_data.get('country', instance.country)
        instance.save()
        return instance
