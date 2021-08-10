from pathlib import Path

from django import forms
from django.http import Http404, FileResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.utils import add_state_change_event
from ietf.doc.models import DocAlias, DocEvent, Document, NewRevisionDocEvent, State
from ietf.ietfauth.utils import role_required
from ietf.meeting.forms import FileUploadForm
from ietf.meeting.models import Meeting, Sponsor
from ietf.meeting.helpers import get_meeting
from ietf.name.models import ProceedingsMaterialTypeName
from ietf.secr.proceedings.utils import handle_upload_file
from ietf.utils.text import xslugify

class UploadProceedingsMaterialForm(FileUploadForm):
    def __init__(self, *args, **kwargs):
        super().__init__(doc_type='procmaterials', *args, **kwargs)
        self.fields['file'].label = 'Select a file to upload. Allowed format{}: {}'.format(
            '' if len(self.mime_types) == 1 else 's',
            ', '.join(self.mime_types),
        )


class EditProceedingsMaterialForm(forms.Form):
    """Form to edit proceedings material properties"""
    # A note: we use Document._meta to get the max length of a model field.
    # The leading underscore makes this look like accessing a private member,
    # but it is in fact part of Django's API.
    # noinspection PyProtectedMember
    title = forms.CharField(
        help_text='Label that will appear on the proceedings page',
        max_length=Document._meta.get_field("title").max_length,
        required=True,
    )


def save_proceedings_material_doc(meeting, material_type, title, request, file=None, state=None):
    events = []
    by = request.user.person

    doc_name = '-'.join([
        'proceedings',
        meeting.number,
        xslugify(
            getattr(material_type, 'slug', material_type)
        ).replace('_', '-')[:128],
    ])

    created = False
    doc = Document.objects.filter(type_id='procmaterials', name=doc_name).first()
    if doc is None:
        if file is None:
            raise ValueError('Cannot create a new document without a file')
        doc = Document.objects.create(
            type_id='procmaterials',
            name=doc_name,
            rev="00",
        )
        created = True

    # do this even if we did not create the document, just to be sure the alias exists
    alias, _ = DocAlias.objects.get_or_create(name=doc.name)
    alias.docs.add(doc)

    if file:
        if not created:
            doc.rev = '{:02}'.format(int(doc.rev) + 1)
        filename = f'{doc.name}-{doc.rev}{Path(file.name).suffix}'
        save_error = handle_upload_file(file, filename, meeting, 'procmaterials', )
        if save_error is not None:
            raise RuntimeError(save_error)

        doc.uploaded_filename = filename
        e = NewRevisionDocEvent.objects.create(
            type="new_revision",
            doc=doc,
            rev=doc.rev,
            by=by,
            desc="New version available: <b>%s-%s</b>" % (doc.name, doc.rev),
        )
        events.append(e)

    if doc.title != title and title is not None:
        e = DocEvent(doc=doc, rev=doc.rev, by=by, type='changed_document')
        e.desc = f'Changed title to <b>{title}</b>'
        if doc.title:
            e.desc += f' from {doc.title}'
        e.save()
        events.append(e)
        doc.title = title

    # Set the state and create a change event if necessary
    prev_state = doc.get_state('procmaterials')
    new_state = state if state is not None else State.objects.get(type_id='procmaterials', slug='active')
    if prev_state != new_state:
        if not created:
            e = add_state_change_event(doc, by, prev_state, new_state)
            events.append(e)
        doc.set_state(new_state)

    if events:
        doc.save_with_history(events)

    return doc


@role_required('Secretariat')
def upload_material(request, num, material_type):
    meeting = get_meeting(num)

    # turn the material_type slug into the actual instance
    material_type = get_object_or_404(ProceedingsMaterialTypeName, slug=material_type)
    material = meeting.proceedings_materials.filter(type=material_type).first()

    if request.method == 'POST':
        form = UploadProceedingsMaterialForm(request.POST, request.FILES)

        if form.is_valid():
            doc = save_proceedings_material_doc(
                meeting,
                material_type,
                request=request,
                file=form.cleaned_data.get('file', None),
                title=str(material if material is not None else material_type),
            )
            if material is None:
                meeting.proceedings_materials.create(type=material_type, document=doc)
            return redirect('ietf.meeting.views_proceedings.material_details')
    else:
        form = UploadProceedingsMaterialForm()

    return render(request, 'meeting/proceedings/upload_material.html', {
        'form': form,
        'material': material,
        'material_type': material_type,
        'meeting': meeting,
        'submit_button_label': 'Upload',
    })

@role_required('Secretariat')
def material_details(request, num):
    meeting = get_meeting(num)
    proceedings_materials = [
        (type_slug, ProceedingsMaterialTypeName.objects.get(pk=type_slug), meeting.proceedings_materials.filter(type=type_slug).first())
        for type_slug in ['acknowledgements', 'social_event', 'host_speaker_series', 'additional_information']
    ]
    return render(
        request,
        'meeting/proceedings/material_details.html',
        dict(
            meeting=meeting,
            proceedings_materials=proceedings_materials,
        )
    )

@role_required('Secretariat')
def edit_material(request, num, material_type):
    meeting = get_meeting(num)
    material = meeting.proceedings_materials.filter(type_id=material_type).first()
    if material is None:
        raise Http404('No such material for this meeting')
    if request.method == 'POST':
        form = EditProceedingsMaterialForm(request.POST, request.FILES)
        if form.is_valid():
            save_proceedings_material_doc(
                meeting,
                material_type,
                request=request,
                title=form.cleaned_data['title'],
                file=form.cleaned_data.get('file', None),
            )
            return redirect("ietf.meeting.views_proceedings.material_details", num=meeting.number)
    else:
        form = EditProceedingsMaterialForm(
            initial=dict(
                title=material.document.title,
            ),
        )

    return render(request, 'meeting/proceedings/edit_material.html', {
        'action': 'revise',
        'back_href': urlreverse('ietf.meeting.views.materials', kwargs={'num': num}),
        'form': form,
        'material': material,
        'material_type': material.type,
        'meeting': meeting,
    })

@role_required('Secretariat')
def remove_restore_material(request, num, material_type, action):
    if action not in ['remove', 'restore']:
        return HttpResponseBadRequest('Unsupported action')
    meeting = get_meeting(num)
    material = meeting.proceedings_materials.filter(type_id=material_type).first()
    if material is None:
        raise Http404('No such material for this meeting')
    if request.method == 'POST':
        material.document.set_state(
            State.objects.get(
                type_id='procmaterials',
                slug='active' if action == 'restore' else 'removed',
            )
        )
        return redirect('ietf.meeting.views_proceedings.material_details', num=num)

    return render(
        request,
        'meeting/proceedings/remove_restore_material.html',
        dict(material=material, action=action)
    )

@role_required('Secretariat')
def edit_sponsors(request, num):
    meeting = get_meeting(num)

    SponsorFormSet = forms.inlineformset_factory(
        Meeting,
        Sponsor,
        fields=('name', 'logo',),
        extra=2,
    )

    if request.method == 'POST':
        formset = SponsorFormSet(request.POST, request.FILES, instance=meeting)
        if formset.is_valid():
            formset.save()
            # remove any logos from deleted sponsors
            for form in formset.deleted_forms:
                try:
                    Path(form.instance.logo.path).unlink()
                except FileNotFoundError:
                    pass  # After python 3.8, can use missing_ok param to unlink instead
            return redirect('ietf.meeting.views.materials', num=meeting.number)
    else:
        formset = SponsorFormSet(instance=meeting)

    return render(request, 'meeting/proceedings/edit_sponsors.html', {
        'formset': formset,
        'meeting': meeting,
    })


def sponsor_logo(request, num, sponsor_id):
    sponsor = get_object_or_404(Sponsor, pk=sponsor_id)
    if sponsor.meeting.number != num:
        raise Http404()

    return FileResponse(sponsor.logo.open())
