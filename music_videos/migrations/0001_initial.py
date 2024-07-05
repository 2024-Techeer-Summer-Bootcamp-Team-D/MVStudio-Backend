# Generated by Django 5.0.6 on 2024-07-05 12:27

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("member", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Genre",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="Instrument",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name="MusicVideo",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("subject", models.CharField(max_length=200)),
                ("tempo", models.CharField(max_length=10)),
                ("language", models.CharField(max_length=100)),
                ("vocal", models.CharField(max_length=100)),
                ("length", models.IntegerField()),
                ("cover_image", models.CharField(max_length=1000)),
                ("mv_file", models.CharField(max_length=1000)),
                ("views", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                ("genre_id", models.ManyToManyField(to="music_videos.genre")),
                (
                    "instrument_id",
                    models.ManyToManyField(null=True, to="music_videos.instrument"),
                ),
                (
                    "member_id",
                    models.ForeignKey(
                        db_column="member_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="member.member",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Verse",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("lyrics", models.CharField(max_length=500)),
                ("sequence", models.IntegerField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_deleted", models.BooleanField(default=False)),
                (
                    "mv_id",
                    models.ForeignKey(
                        db_column="mv_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="music_videos.musicvideo",
                    ),
                ),
            ],
        ),
    ]