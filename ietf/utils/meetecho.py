# Copyright The IETF Trust 2021, All Rights Reserved
#
"""Meetecho interim meeting scheduling API

Implements the v1 API described in email from alex@meetecho.com
on 2021-12-09.

API methods return Python objects equivalent to the JSON structures
specified in the API documentation. Times and durations are represented
in the Python API by datetime and timedelta objects, respectively.
"""
import requests

import debug  # pyflakes: ignore

from datetime import datetime, timedelta
from json import JSONDecodeError
from typing import Sequence, Union
from urllib.parse import urljoin


class MeetechoAPI:
    def __init__(self, api_base: str, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self._session = requests.Session()
        # if needed, add a trailing slash so urljoin won't eat the trailing path component
        self.api_base = api_base if api_base.endswith('/') else f'{api_base}/'

    def _request(self, method, url, api_token=None, json=None):
        """Execute an API request"""
        headers = {}
        if api_token is not None:
            headers['Authorization'] = f'bearer {api_token}'

        try:
            response = self._session.request(
                method,
                urljoin(self.api_base, url),
                headers=headers,
                json=json,
                timeout=3.01,  # python-requests doc recommend slightly > a multiple of 3 seconds
            )
        except requests.RequestException as err:
            raise MeetechoAPIError(str(err)) from err
        if response.status_code != 200:
            raise MeetechoAPIError(f'API request failed (HTTP status code = {response.status_code})')

        try:
            return response.json()
        except JSONDecodeError as err:
            raise MeetechoAPIError('Error decoding response as JSON') from err

    def _deserialize_time(self, s: str) -> datetime:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S')

    def _serialize_time(self, dt: datetime) -> str:
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def _deserialize_duration(self, minutes: int) -> timedelta:
        return timedelta(minutes=minutes)

    def _serialize_duration(self, td: timedelta) -> int:
        return int(td.total_seconds() // 60)

    def _deserialize_meetings_response(self, response):
        """In-place deserialization of response data structure

        Deserializes data in the structure where needed (currently, that's time-related structures)
        """
        for session_data in response['rooms'].values():
            session_data['room']['start_time'] = self._deserialize_time(session_data['room']['start_time'])
            session_data['room']['duration'] = self._deserialize_duration(session_data['room']['duration'])
        return response

    def retrieve_wg_tokens(self, acronyms: Union[str, Sequence[str]]):
        """Retrieve API tokens for one or more WGs

        :param acronyms: list of WG acronyms for which tokens are requested 
        :return: {'tokens': {acronym0: token0, acronym1: token1, ...}}
        """
        return self._request(
            'POST', 'auth/ietfservice/tokens',
            json={
                'client': self.client_id,
                'secret': self.client_secret,
                'wgs': [acronyms] if isinstance(acronyms, str) else acronyms,
            }
        )

    def schedule_meeting(self, wg_token: str, description: str, start_time: datetime, duration: timedelta,
                         extrainfo=''):
        """Schedule a meeting session
        
        Return structure is:
          {
            "rooms": {
              "<session UUID>": {
                "room": {
                  "id": int,
                  "start_time": datetime,
                  "duration": timedelta
                  description: str,
                },
                "url": str,
                "deletion_token": str
              }
            }
          }
              
        :param wg_token: token retrieved via retrieve_wg_tokens() 
        :param description: str describing the meeting
        :param start_time: starting time as a datetime
        :param duration: duration as a timedelta
        :param extrainfo: str with additional information for Meetecho staff
        :return: scheduled meeting data dict
        """
        return self._deserialize_meetings_response(
            self._request(
                'POST', 'meeting/interim/createRoom',
                api_token=wg_token,
                json={
                    'description': description,
                    'start_time': self._serialize_time(start_time),
                    'duration': self._serialize_duration(duration),
                    'extrainfo': extrainfo,
                },
            )
        )

    def fetch_meetings(self, wg_token: str):
        """Fetch all meetings scheduled for a given wg

        Return structure is:
          {
            "rooms": {
              "<session UUID>": {
                "room": {
                  "id": int,
                  "start_time": datetime,
                  "duration": timedelta
                  "description": str,
                },
                "url": str,
                "deletion_token": str
              }
            }
          }
          
        As of 2022-01-31, the return structure also includes a 'group' key whose
        value is the group acronym. This is not shown in the documentation.

        :param wg_token: token from retrieve_wg_tokens()
        :return: meeting data dict
        """
        return self._deserialize_meetings_response(
            self._request('GET', 'meeting/interim/fetchRooms', api_token=wg_token)
        )

    def delete_meeting(self, deletion_token: str):
        """Remove a scheduled meeting

        :param deletion_token: deletion_key from fetch_meetings() or schedule_meeting() return data
        :return: {}
        """
        return self._request('POST', 'meeting/interim/deleteRoom', api_token=deletion_token)


class MeetechoAPIError(Exception):
    """Base class for MeetechoAPI exceptions"""


class Conference:
    """Scheduled session/room representation"""
    def __init__(self, id, public_id, description, start_time, duration, url, deletion_token):
        self.id = id  # Meetecho system ID
        self.public_id = public_id  # public session UUID
        self.description = description
        self.start_time = start_time
        self.duration = duration
        self.url = url
        self.deletion_token = deletion_token

    @classmethod
    def from_api_dict(cls, api_dict, public_id=None):
        return cls(
            **api_dict['room'],
            public_id=public_id,
            url=api_dict['url'],
            deletion_token=api_dict['deletion_token'],
        )


class ConferenceManager:
    def __init__(self, api_config: dict):
        self.api = MeetechoAPI(**api_config)
        
    def wg_token(self, group_acronym):
        return self.api.retrieve_wg_tokens(group_acronym)['tokens'][group_acronym]
    
    def fetch(self, group):
        group_acronym = group.acronym if hasattr(group, 'acronym') else group
        response = self.api.fetch_meetings(self.wg_token(group_acronym))
        return [Conference.from_api_dict(val, pub_id) 
                for pub_id, val in response['rooms'].items()]
