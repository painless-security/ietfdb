# Copyright The IETF Trust 2013-2019, All Rights Reserved
import datetime
import re
import json
from collections import namedtuple

from django import forms
from django.db.models import Q

import debug                            # pyflakes:ignore

from ietf.group.models import Group
from ietf.meeting.models import Meeting, Room, TimeSlot, Session, SchedTimeSessAssignment
from ietf.name.models import TimeSlotTypeName, SessionPurposeName
import ietf.utils.fields


# using Django week_day lookup values (Sunday=1)
SESSION_DAYS = ((2,'Monday'),
                (3,'Tuesday'),
                (4,'Wednesday'),
                (5,'Thursday'),
                (6,'Friday'))
        
SESSION_DURATION_RE = re.compile(r'^\d{2}:\d{2}')

#----------------------------------------------------------
# Helper Functions
#----------------------------------------------------------
def get_next_slot(slot):
    '''Takes a TimeSlot object and returns the next TimeSlot same day and same room, None if there
    aren't any.  You must check availability of the slot as we sometimes need to get the next
    slot whether it's available or not.  For use with combine option.
    '''
    same_day_slots = TimeSlot.objects.filter(meeting=slot.meeting,location=slot.location,time__day=slot.time.day).order_by('time')
    try:
        i = list(same_day_slots).index(slot)
        return same_day_slots[i+1]
    except IndexError:
        return None
    
def get_times(meeting,day):
    '''
    Takes a Meeting object and an integer representing the week day (sunday=1).  
    Returns a list of tuples for use in a ChoiceField.  The value is start_time, 
    The label is [start_time]-[end_time].
    '''
    # pick a random room
    rooms = Room.objects.filter(meeting=meeting,session_types='regular')
    if rooms:
        room = rooms[0]
    else:
        room = None
    slots = TimeSlot.objects.filter(meeting=meeting,time__week_day=day,location=room).order_by('time')
    choices = [ (t.time.strftime('%H%M'), '%s-%s' % (t.time.strftime('%H%M'), t.end_time().strftime('%H%M'))) for t in slots ]
    return choices

#----------------------------------------------------------
# Base Classes
#----------------------------------------------------------
class BaseMeetingRoomFormSet(forms.models.BaseInlineFormSet):
    def clean(self):
        '''Check that any rooms marked for deletion are not in use'''
        for form in self.deleted_forms:
            room = form.cleaned_data['id']
            schedtimesessassignments = SchedTimeSessAssignment.objects.filter(timeslot__location=room,
                                                                session__isnull=False)
            if schedtimesessassignments:
                raise forms.ValidationError('Cannot delete meeting room %s.  Already assigned to some session.' % room.name)
                
class TimeSlotModelChoiceField(forms.ModelChoiceField):
    '''
    Custom ModelChoiceField, changes the label to a more readable format
    '''
    def label_from_instance(self, obj):
        
        return "%s %s - %s" % (obj.time.strftime('%a %H:%M'),obj.name,obj.location)
        
class TimeChoiceField(forms.ChoiceField):
    '''
    We are modifying the time choice field with javascript so the value submitted may not have
    been in the initial select list.  Just override valid_value validaion.
    '''
    def valid_value(self, value):
        return True
        
#----------------------------------------------------------
# Forms
#----------------------------------------------------------
class MeetingSelectForm(forms.Form):
    meeting = forms.ChoiceField()

    def __init__(self,*args,**kwargs):
        choices = kwargs.pop('choices')
        super(MeetingSelectForm, self).__init__(*args,**kwargs)
        self.fields['meeting'].widget.choices = choices

class MeetingModelForm(forms.ModelForm):
    idsubmit_cutoff_time_utc     = ietf.utils.fields.DurationField()
    idsubmit_cutoff_warning_days = ietf.utils.fields.DurationField()
    class Meta:
        model = Meeting
        exclude = ('type', 'schedule', 'session_request_lock_message')
        widgets = {
            'group_conflict_types': forms.CheckboxSelectMultiple(),
        }

    def __init__(self,*args,**kwargs):
        super(MeetingModelForm, self).__init__(*args,**kwargs)
        if 'instance' in kwargs:
            for f in [ 'idsubmit_cutoff_warning_days', 'idsubmit_cutoff_time_utc', ]:
                self.fields[f].help_text = kwargs['instance']._meta.get_field(f).help_text

    def clean_number(self):
        number = self.cleaned_data['number']
        if not number.isdigit():
            raise forms.ValidationError('Meeting number must be an integer')
        return number
        
    def save(self, force_insert=False, force_update=False, commit=True):
        meeting = super(MeetingModelForm, self).save(commit=False)
        meeting.type_id = 'ietf'
        if commit:
            meeting.save()
            # must call save_m2m() because we saved with commit=False above, see:
            # https://docs.djangoproject.com/en/2.2/topics/forms/modelforms/#the-save-method
            self.save_m2m()
        return meeting
        
class MeetingRoomForm(forms.ModelForm):
    class Meta:
        model = Room
        exclude = ['resources']

class MeetingRoomOptionsForm(forms.Form):
    copy_timeslots = forms.BooleanField(
        required=False,
        initial=False,
        label='Duplicate timeslots from previous meeting for new rooms?',
    )

class TimeSlotForm(forms.Form):
    day = forms.ChoiceField()
    time = forms.TimeField()
    duration = ietf.utils.fields.DurationField()
    name = forms.CharField(help_text='Name that appears on the agenda')
    
    def __init__(self,*args,**kwargs):
        if 'meeting' in kwargs:
            self.meeting = kwargs.pop('meeting')
        super(TimeSlotForm, self).__init__(*args,**kwargs)
        self.fields["time"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["duration"].widget.attrs["placeholder"] = "HH:MM"
        self.fields["day"].choices = self.get_day_choices()

    def clean_duration(self):
        '''Limit to HH:MM format'''
        duration = self.data['duration']
        if not SESSION_DURATION_RE.match(duration):
            raise forms.ValidationError('{} value has an invalid format. It must be in HH:MM format'.format(duration))
        return self.cleaned_data['duration']

    def get_day_choices(self):
        '''Get day choices for form based on meeting duration'''
        choices = []
        start = self.meeting.date 
        for n in range(-self.meeting.days, self.meeting.days):
            date = start + datetime.timedelta(days=n)
            choices.append((n, date.strftime("%a %b %d")))
        return choices


class SessionPurposeAndTypeWidget(forms.MultiWidget):
    css_class = 'session_purpose_widget'  # class to apply to all widgets

    def __init__(self, purpose_choices, type_choices, *args, **kwargs):
        # Avoid queries on models that need to be migrated into existence - this widget is
        # instantiated during Django setup. Attempts to query, e.g., SessionPurposeName will
        # prevent migrations from running.
        widgets = (
            forms.Select(
                choices=purpose_choices,
                attrs={
                    'class': self.css_class,
                },
            ),
            forms.Select(
                choices=type_choices,
                attrs={
                    'class': self.css_class,
                    'data-allowed-options': None,
                },
            ),
        )
        super().__init__(widgets=widgets, *args, **kwargs)

    # These queryset properties are needed to propagate changes to the querysets after initialization
    # down to the widgets. The usual mechanisms in the ModelChoiceFields don't handle this for us
    # because the subwidgets are not attached to Fields in the usual way.
    @property
    def purpose_choices(self):
        return self.widgets[0].choices

    @purpose_choices.setter
    def purpose_choices(self, value):
        self.widgets[0].choices = value

    @property
    def type_choices(self):
        return self.widgets[1].choices

    @type_choices.setter
    def type_choices(self, value):
        self.widgets[1].choices = value

    def render(self, *args, **kwargs):
        # Fill in the data-allowed-options (could not do this in init because it needs to
        # query SessionPurposeName, which will break the migration if done during initialization)
        self.widgets[1].attrs['data-allowed-options'] = json.dumps(self._allowed_types())
        return super().render(*args, **kwargs)

    def decompress(self, value):
        if value:
            return [getattr(val, 'pk', val) for val in value]
        else:
            return [None, None]

    class Media:
        js = ('secr/js/session_purpose_and_type_widget.js',)

    def _allowed_types(self):
        """Map from purpose to allowed type values"""
        return {
            purpose.slug: list(purpose.timeslot_types.values_list('pk', flat=True))
            for purpose in SessionPurposeName.objects.all()
        }


class SessionPurposeAndTypeField(forms.MultiValueField):
    """Field to update Session purpose and type

    Uses SessionPurposeAndTypeWidget to coordinate setting the session purpose and type to valid
    combinations. Its value should be a tuple with (purpose, type). Its cleaned value is a
    namedtuple with purpose and value properties.
    """
    def __init__(self, purpose_queryset, type_queryset, **kwargs):
        fields = (
            forms.ModelChoiceField(queryset=purpose_queryset, label='Purpose'),
            forms.ModelChoiceField(queryset=type_queryset, label='Type'),
        )
        self.widget = SessionPurposeAndTypeWidget(*(field.choices for field in fields))
        super().__init__(fields=fields, **kwargs)

    @property
    def purpose_queryset(self):
        return self.fields[0].queryset

    @purpose_queryset.setter
    def purpose_queryset(self, value):
        self.fields[0].queryset = value
        self.widget.purpose_choices = self.fields[0].choices

    @property
    def type_queryset(self):
        return self.fields[1].queryset

    @type_queryset.setter
    def type_queryset(self, value):
        self.fields[1].queryset = value
        self.widget.type_choices = self.fields[1].choices

    def compress(self, data_list):
        # Convert data from the cleaned list from the widget into a namedtuple
        if data_list:
            compressed = namedtuple('CompressedSessionPurposeAndType', 'purpose type')
            return compressed(*data_list)
        return None

    def validate(self, value):
        # Additional validation - value has been passed through compress() already
        if value.type not in value.purpose.timeslot_types.all():
            raise forms.ValidationError(
                '"%(type)s" is not an allowed type for the purpose "%(purpose)s"',
                params={'type': value.type, 'purpose': value.purpose},
                code='invalid_type',
            )

class MiscSessionForm(TimeSlotForm):
    short = forms.CharField(max_length=32,label='Short Name',help_text='Enter an abbreviated session name (used for material file names)',required=False)
    purpose = SessionPurposeAndTypeField(
        purpose_queryset=SessionPurposeName.objects.none(),
        type_queryset=TimeSlotTypeName.objects.none(),
    )
    group = forms.ModelChoiceField(
        queryset=Group.objects.filter(
            Q(type__in=['ietf','team','area'],state='active')|
            Q(type__features__has_meetings=True,state='active')
        ).exclude(
            type_id__in=['wg','ag','rg','rag','program']
        ).order_by(
            'name'
        ),
        help_text='''Select a group to associate with this session.  For example:<br>
                     Tutorials = Education,<br>
                     Code Sprint = Tools Team,<br>
                     Plenary = IETF''',
        required=False)
    location = forms.ModelChoiceField(queryset=Room.objects, required=False)
    remote_instructions = forms.CharField(max_length=255)
    show_location = forms.BooleanField(required=False)

    def __init__(self,*args,**kwargs):
        if 'meeting' in kwargs:
            self.meeting = kwargs.pop('meeting')
        if 'session' in kwargs:
            self.session = kwargs.pop('session')
        initial = kwargs.setdefault('initial', dict())
        initial['purpose'] = (initial.pop('purpose', ''), initial.pop('type', ''))
        super(MiscSessionForm, self).__init__(*args,**kwargs)
        self.fields['location'].queryset = Room.objects.filter(meeting=self.meeting)
        self.fields['purpose'].purpose_queryset = SessionPurposeName.objects.filter(
            used=True
        ).exclude(
            slug='session'
        ).order_by('name')
        self.fields['purpose'].type_queryset = TimeSlotTypeName.objects.filter(used=True)

    def clean(self):
        super(MiscSessionForm, self).clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        group = cleaned_data['group']
        type = cleaned_data['purpose'].type
        short = cleaned_data['short']
        if type.slug in ('other','plenary','lead') and not group:
            raise forms.ValidationError('ERROR: a group selection is required')
        if type.slug in ('other','plenary','lead') and not short:
            raise forms.ValidationError('ERROR: a short name is required')
            
        return cleaned_data
    
    def clean_group(self):
        group = self.cleaned_data['group']
        if hasattr(self, 'session') and self.session.group != group and self.session.materials.all():
            raise forms.ValidationError("ERROR: can't change group after materials have been uploaded")
        return group

class UploadBlueSheetForm(forms.Form):
    file = forms.FileField(help_text='example: bluesheets-84-ancp-01.pdf')
    
    def clean_file(self):
        file = self.cleaned_data['file']
        if not re.match(r'bluesheets-\d+',file.name):
            raise forms.ValidationError('Incorrect filename format')
        return file

class RegularSessionEditForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ['agenda_note']

