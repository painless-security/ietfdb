# Copyright The IETF Trust 2022, All Rights Reserved
# -*- coding: utf-8 -*-
import datetime

from textwrap import dedent

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ietf.meeting.models import Session
from ietf.utils.meetecho import MeetechoAPI, MeetechoAPIError


class Command(BaseCommand):
    help = 'Manage Meetecho conferences'
    
    def add_arguments(self, parser) -> None:
        parser.add_argument('group', type=str)
    
    def handle(self, group, *args, **options):
        api = MeetechoAPI(
            api_base=settings.MEETECHO_API_BASE,
            client_id=settings.MEETECHO_CLIENT_ID,
            client_secret=settings.MEETECHO_CLIENT_SECRET,
        )
        
        try:
            result = api.retrieve_wg_tokens(group)
        except MeetechoAPIError as err:
            raise CommandError('Unable to retrieve wg tokens') from err
        try:
            token = result['tokens'][group]
        except KeyError as err:
            raise CommandError('Unexpected data returned when retrieving wg tokens') from err
        
        try:
            result = api.fetch_meetings(token)
        except MeetechoAPIError as err:
            raise CommandError('Unable to fetch meetings') from err
        try:
            all_room_data = result['rooms']
        except KeyError as err:
            raise CommandError('Unexpected data returned from when fetching meetings') from err
    
        self.stdout.write(f'Meetecho conferences for {group}:\n\n')
        for uuid, data in all_room_data.items():
            sessions = Session.objects.filter(
                group__acronym=group,
                meeting__date__gte=datetime.date.today(),
                remote_instructions__contains=data['url'],
            )
            sessions_desc = ', '.join(str(s.pk) for s in sessions) or None
            self.stdout.write(
                dedent(f'''\
                * {data['room']['description']}
                    Start time: {data['room']['start_time']} 
                    Duration: {int(data['room']['duration'].total_seconds() // 60)} minutes
                    URL: {data['url']}
                    Associated session PKs: {sessions_desc}
                
                ''')
            )