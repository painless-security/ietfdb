# Copyright The IETF Trust 2007-2019, All Rights Reserved
# -*- coding: utf-8 -*-

from ietf.settings import *                                          # pyflakes:ignore

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'HOST': 'db',
        'PORT': 3306,
        'NAME': 'ietf_utf8',
        'ENGINE': 'django.db.backends.mysql',
        'USER': 'django',
        'PASSWORD': 'RkTkDPFnKpko',
        'OPTIONS': {
            'sql_mode': 'STRICT_TRANS_TABLES',
            'init_command': 'SET storage_engine=InnoDB; SET names "utf8"',
        },
    },
}

DATABASE_TEST_OPTIONS = {
    'init_command': 'SET storage_engine=InnoDB',
}

IDSUBMIT_IDNITS_BINARY = "/usr/local/bin/idnits"
IDSUBMIT_REPOSITORY_PATH = "test/id/"
IDSUBMIT_STAGING_PATH = "test/staging/"
INTERNET_DRAFT_ARCHIVE_DIR = "test/archive/"
INTERNET_ALL_DRAFTS_ARCHIVE_DIR = "test/archive/"
RFC_PATH = "test/rfc/"

AGENDA_PATH = 'data/developers/www6s/proceedings/'
MEETINGHOST_LOGO_PATH = AGENDA_PATH

USING_DEBUG_EMAIL_SERVER=True
EMAIL_HOST='localhost'
EMAIL_PORT=2025

TRAC_WIKI_DIR_PATTERN = "test/wiki/%s"
TRAC_SVN_DIR_PATTERN = "test/svn/%s"

MEDIA_BASE_DIR = 'test'
MEDIA_ROOT = MEDIA_BASE_DIR + '/media/'
MEDIA_URL = '/media/'

PHOTOS_DIRNAME = 'photo'
PHOTOS_DIR = MEDIA_ROOT + PHOTOS_DIRNAME

DOCUMENT_PATH_PATTERN = 'data/developers/ietf-ftp/{doc.type_id}/'

SUBMIT_YANG_CATALOG_MODEL_DIR = 'data/developers/ietf-ftp/yang/catalogmod/'
SUBMIT_YANG_DRAFT_MODEL_DIR = 'data/developers/ietf-ftp/yang/draftmod/'
SUBMIT_YANG_INVAL_MODEL_DIR = 'data/developers/ietf-ftp/yang/invalmod/'
SUBMIT_YANG_IANA_MODEL_DIR = 'data/developers/ietf-ftp/yang/ianamod/'
SUBMIT_YANG_RFC_MODEL_DIR   = 'data/developers/ietf-ftp/yang/rfcmod/'
