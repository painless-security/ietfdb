# Copyright The IETF Trust 2007-2019, All Rights Reserved

from django import forms

from ietf.doc.models import Document
from ietf.meeting.models import Session
from ietf.meeting.utils import add_event_info_to_session_qs


# ---------------------------------------------
# Globals
# ---------------------------------------------

VALID_SLIDE_EXTENSIONS = ('.doc','.docx','.pdf','.ppt','.pptx','.txt','.zip')
VALID_MINUTES_EXTENSIONS = ('.txt','.html','.htm','.pdf')
VALID_AGENDA_EXTENSIONS = ('.txt','.html','.htm')
VALID_BLUESHEET_EXTENSIONS = ('.pdf','.jpg','.jpeg')

#----------------------------------------------------------
# Forms
#----------------------------------------------------------

class RecordingForm(forms.Form):
    external_url = forms.URLField(label='Url')
    session = forms.ModelChoiceField(queryset=Session.objects,empty_label='')
    
    def __init__(self, *args, **kwargs):
        self.meeting = kwargs.pop('meeting')
        super(RecordingForm, self).__init__(*args,**kwargs)
        self.fields['session'].queryset = add_event_info_to_session_qs(
            Session.objects.filter(meeting=self.meeting, type__in=['regular','plenary','other'])
        ).filter(current_status='sched').order_by('group__acronym')

class RecordingEditForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['external_url']
        
    def __init__(self, *args, **kwargs):
        super(RecordingEditForm, self).__init__(*args, **kwargs)
        self.fields['external_url'].label='Url'

