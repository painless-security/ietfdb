# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


"""
WSGI configuration for the datatracker.

The following apache datatracker configuration has been used together with a
datatracker checkout of trunk@ under /srv/www/ietfdb/ to run this on a development
server using mod_wsgi under apache.  For a production server, additional access
restrictions are needed for the secretariat tools.

----
# This directive must be set globally, not inside <Virtualhost/>:
WSGIPythonEggs /var/www/.python-eggs/

<VirtualHost *:80> 
    ServerName tracker.tools.ietf.org

    ServerSignature Off
    CustomLog /var/log/apache2/tracker.tools.ietf.org-access.log full
    ErrorLog /var/log/apache2/tracker.tools.ietf.org-error.log

    DocumentRoot "/srv/www/ietfdb/static/"

    Alias	/robots.tx	/srv/www/ietfdb/static/dev/robots.txt
    AliasMatch	"^/((favicon.ico|images|css|js|media|secretariat)(.*))$" /srv/www/ietfdb/static/$1

    WSGIScriptAlias / /srv/www/ietfdb/ietf/wsgi.py

    <Location "/accounts/login">
        AuthType Digest
        AuthName "IETF"
        AuthUserFile /var/local/loginmgr/digest
        AuthGroupFile /var/local/loginmgr/groups
        AuthDigestDomain http://tools.ietf.org/
        Require valid-user
    </Location>
</VirtualHost>
----

"""


import os
import sys
import syslog

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

syslog.openlog(str("datatracker"), syslog.LOG_PID, syslog.LOG_USER)

if not path in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ietf.settings")

syslog.syslog("Starting datatracker wsgi instance")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

