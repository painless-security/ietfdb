# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-

from email.message import EmailMessage
from textwrap import dedent
from traceback import format_exception

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ietf.utils.mail import send_smtp

import debug  # pyflakes:ignore


class EmailOnFailureCommand(BaseCommand):
    """Command that sends email when an exception occurs

    Subclasses can override failure_message, failure_subject, and failure_recipients
    to customize the behavior. Both failure_subject and failure_message are formatted
    with keywords for interpolation. By default, the exception being handled will
    be available for interpolation as {error}. More interpolation values can
    be added through the **extra argument to make_failure_message().

    When a command is executed, its handle() method will be called as usual.
    If an exception occurs, instead of printing this to the terminal and
    exiting with an error, a message generated via the make_failure_message()
    method will be sent to failure_recipients. The command will exit successfully
    to the shell.

    This can be prevented for debugging by passing the --no-failure-email option.
    In this case, the usual error handling will be used. To make this available,
    the subclass must call super().add_arguments() in its own add_arguments() method.
    """
    failure_message = dedent("""\
    An exception occurred: 
    
    {error}
    """)
    failure_subject = 'Exception in management command'
    failure_recipients = tuple(item[1] for item in settings.ADMINS)

    def execute(self, *args, **options):
        try:
            super().execute(*args, **options)
        except Exception as error:
            if options['email_on_failure']:
                msg = self.make_failure_message(error)
                send_smtp(msg)
            else:
                raise

    def make_failure_message(self, error, **extra):
        """Generate an EmailMessage to report an error"""
        format_values = dict(error=error)
        format_values.update(**extra)
        msg = EmailMessage()
        msg['To'] = self.failure_recipients
        msg['From'] = settings.SERVER_EMAIL
        msg['Subject'] = self.failure_subject.format(**format_values)
        msg.set_content(
            self.failure_message.format(**format_values)
        )
        msg.add_attachment(
            ''.join(format_exception(None, error, error.__traceback__)),
            filename='traceback.txt',
        )
        return msg

    def add_arguments(self, parser):
        parser.add_argument('--no-failure-email', dest='email_on_failure', action='store_false',
                            help='Disable sending email on failure')