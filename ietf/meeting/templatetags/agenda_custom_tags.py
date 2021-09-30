# Copyright The IETF Trust 2013-2020, All Rights Reserved
# -*- coding: utf-8 -*-


from django import template

register = template.Library()



# returns the a dictioary's value from it's key.
@register.filter(name='lookup')
def lookup(dict, index):
    if index in dict:
        return dict[index]
    return ''

# returns the length of the value of a dict.
# We are doing this to how long the title for the calendar should be. (this should return the number of time slots)
@register.filter(name='colWidth')
def get_col_width(dict, index):
    if index in dict:
        return len(dict[index])
    return 0

# Replaces characters that are not acceptable html ID's
@register.filter(name='to_acceptable_id')
def to_acceptable_id(inp):
    # see http://api.jquery.com/category/selectors/?rdfrom=http%3A%2F%2Fdocs.jquery.com%2Fmw%2Findex.php%3Ftitle%3DSelectors%26redirect%3Dno
    # for more information.
    invalid = ["!","\"", "#","$","%","&","'","(",")","*","+",",",".","/",":",";","<","=",">","?","@","[","\\","]","^","`","{","|","}","~"," "]
    out = str(inp)
    for i in invalid:
        out = out.replace(i,'_')
    return out


@register.filter(name='durationFormat')
def durationFormat(inp):
    return "%.1f" % (float(inp)/3600)

# from:
#    http://www.sprklab.com/notes/13-passing-arguments-to-functions-in-django-template
#
@register.filter(name="call")
def callMethod(obj, methodName):
    method = getattr(obj, methodName)

    if "__callArg" in obj.__dict__:
        ret = method(*obj.__callArg)
        del obj.__callArg
        return ret
    return method()

@register.filter(name="args")
def args(obj, arg):
    if "__callArg" not in obj.__dict__:
        obj.__callArg = []

    obj.__callArg += [arg]
    return obj

@register.filter
def is_regular_agenda_item(assignment):
    """Is this agenda item a regular session item?

    A regular item appears as a sub-entry in a timeslot within the agenda

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> is_regular_agenda_item(factory('regular'))
    True

    >>> any(is_regular_agenda_item(factory(t)) for t in ['plenary', 'break', 'reg', 'other', 'officehours'])
    False
    """
    return assignment.slot_type().slug == 'regular'


@register.filter
def is_plenary_agenda_item(assignment):
    """Is this agenda item a plenary session item?

    A plenary item appears as a top-level agenda entry

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> is_plenary_agenda_item(factory('plenary'))
    True

    >>> any(is_plenary_agenda_item(factory(t)) for t in ['regular', 'break', 'reg', 'other', 'officehours'])
    False
    """
    return assignment.slot_type().slug == 'plenary'


@register.filter
def is_special_agenda_item(assignment):
    """Is this agenda item a special item?

    Special items appear as top-level agenda entries with their own timeslot information.

    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_timeslot = namedtuple('t2', ['slug'])
    >>> mock_assignment = namedtuple('t1', ['slot_type'])  # slot_type must be a callable
    >>> factory = lambda t: mock_assignment(slot_type=lambda: mock_timeslot(slug=t))
    >>> all(is_special_agenda_item(factory(t)) for t in ['break', 'reg', 'other', 'officehours'])
    True

    >>> any(is_special_agenda_item(factory(t)) for t in ['regular', 'plenary'])
    False
    """
    return assignment.slot_type().slug in [
        'break',
        'reg',
        'other',
        'officehours',
    ]


@register.filter
def should_suppress_agenda_session_buttons(assignment):
    """Should this agenda item suppress the session buttons (jabber link, etc)?

    This answers whether the session_buttons_include.html button should refuse
    to display its buttons even if included.

    In IETF-111 and earlier, office hours sessions were designated by a name ending
    with ' office hours' and belonged to the IESG or some other group. This led to
    incorrect session buttons being displayed. Suppress session buttons
    when name ends with 'office hours' in the pre-111 meetings.
    >>> from collections import namedtuple  # use to build mock objects
    >>> mock_meeting = namedtuple('t3', ['number'])
    >>> mock_session = namedtuple('t2', ['name'])
    >>> mock_assignment = namedtuple('t1', ['meeting', 'session'])  # meeting must be a callable
    >>> factory = lambda num, name: mock_assignment(session=mock_session(name), meeting=lambda: mock_meeting(num))
    >>> test_cases = [('105', 'acme office hours'), ('111', 'acme office hours')]
    >>> all(should_suppress_agenda_session_buttons(factory(*tc)) for tc in test_cases)
    True
    >>> test_cases = [('interim-2020-acme-112', 'acme'), ('112', 'acme'), ('150', 'acme'), ('105', 'acme'),]
    >>> test_cases.extend([('111', 'acme'), ('interim-2020-acme-112', 'acme office hours')])
    >>> test_cases.extend([('112', 'acme office hours'), ('150', 'acme office hours')])
    >>> any(should_suppress_agenda_session_buttons(factory(*tc)) for tc in test_cases)
    False
    """
    num = assignment.meeting().number
    if num.isdigit() and int(num) <= settings.MEETING_LEGACY_OFFICE_HOURS_END:
        return assignment.session.name.lower().endswith(' office hours')
    else:
        return False
