# Generated by Django 2.2.25 on 2021-12-10 08:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('person', '0020_auto_20210920_0924'),
    ]

    operations = [
        migrations.AlterField(
            model_name='personalapikey',
            name='endpoint',
            field=models.CharField(choices=[('/api/appauth/authortools', '/api/appauth/authortools'), ('/api/appauth/bibxml', '/api/appauth/bibxml'), ('/api/iesg/position', '/api/iesg/position'), ('/api/meeting/session/video/url', '/api/meeting/session/video/url'), ('/api/notify/meeting/bluesheet', '/api/notify/meeting/bluesheet'), ('/api/notify/meeting/registration', '/api/notify/meeting/registration'), ('/api/v2/person/person', '/api/v2/person/person')], max_length=128),
        ),
    ]
