# member/serializers.py

from rest_framework import serializers
from .models import Member, Country
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)

    def validate_email(self, email):
        if not email:
            raise serializers.ValidationError(
                _("email field not allowed empty")
            )
        used = User.objects.filter(email__iexact=email)
        if used.count() > 0:
            raise serializers.ValidationError(
                _("A user is already registered with this e-mail address."))

        return email

    def validate_username(self, username):

        if not username:
            raise serializers.ValidationError(
                _("username field not allowed empty")
            )

        used = User.objects.filter(username__iexact=username).first()
        if used:
            raise serializers.ValidationError(
                _("A user is already registered with this username."))

        return username

    def validate(self, data):
        data['password'] = data['password']
        data['email'] = self.validate_email(data['email'])
        data['username'] = self.validate_username(data['username'])
        print("check validate ALL")

        return data

    def get_cleaned_data(self):
        return {
            'username': self.validated_data.get('username', ''),
            'password': self.validated_data.get('password', ''),
            'email': self.validated_data.get('email', '')
        }

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"]
        )

        return user

class MemberDetailSerializer(serializers.ModelSerializer):
    country = serializers.SerializerMethodField()
    country_id = serializers.IntegerField(required=False)
    class Meta:
        model = Member
        fields = ['username', 'email', 'name', 'nickname', 'profile_image', 'comment', 'country', 'country_id', 'birthday', 'sex', 'youtube_account', 'instagram_account']
        read_only_fields = ['username']

    def get_country(self, obj):
        return obj.country.name
    def update(self, instance, validated_data):
        country_id = validated_data.pop('country_id', None)
        if country_id is not None:
            country = Country.objects.filter(id=country_id).first()
            if country:
                instance.country = country
        return super().update(instance, validated_data)


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name']
