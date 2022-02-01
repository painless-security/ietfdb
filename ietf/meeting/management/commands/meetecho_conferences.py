# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime

from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ietf.meeting.models import Session
from ietf.utils.meetecho import ConferenceManager, MeetechoAPIError


class Command(BaseCommand):
    help = 'Manage Meetecho conferences'
    
    def add_arguments(self, parser) -> None:
        parser.add_argument('group', type=str)
    
    def handle(self, group, *args, **options):
        conf_mgr = ConferenceManager(settings.MEETECHO_API_CONFIG)
        try:
            confs = conf_mgr.fetch(group)
        except MeetechoAPIError as err:
            raise CommandError('API error fetching Meetecho conference data') from err

        self.stdout.write(f'Meetecho conferences for {group}:\n\n')
        for conf in confs:
            sessions = Session.objects.filter(
                group__acronym=group,
                meeting__date__gte=datetime.date.today(),
                remote_instructions__contains=conf.url,
            )
            sessions_desc = ', '.join(str(s.pk) for s in sessions) or None
            self.stdout.write(
                dedent(f'''\
                * {conf.description}
                    Start time: {conf.start_time} 
                    Duration: {int(conf.duration.total_seconds() // 60)} minutes
                    URL: {conf.url}
                    Associated session PKs: {sessions_desc}
                
                ''')
            )