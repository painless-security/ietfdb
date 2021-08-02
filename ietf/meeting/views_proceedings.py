from pathlib import Path

from django import forms
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.utils import add_state_change_event
from ietf.doc.models import DocAlias, DocEvent, Document, NewRevisionDocEvent, State
from ietf.ietfauth.utils import role_required
from ietf.meeting.helpers import get_meeting
from ietf.name.models import ProceedingsMaterialTypeName
from ietf.utils.text import xslugify
from ietf.utils.validators import file_extention_validator, mime_type_validator, validate_file_size


class UploadProceedingsMaterialForm(forms.Form):
    """Form to upload a new or replacement proceedings material"""
    material = forms.FileField(
        help_text='File to include in the proceedings (must be PDF)',
        label='File to upload',
        required=True,
        validators=[
            file_extention_validator(['.pdf']),
            validate_file_size,
            mime_type_validator(['application/pdf']),
        ],
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
    state = forms.ModelChoiceField(
        queryset=State.objects.filter(type='procmaterials', used=True),
        label='State',
        help_text='Material only appears if state is "active"',
        empty_label=None,
        required=True,
    )


def save_proceedings_material_doc(meeting, material_type, title, by, file=None, state=None):
    events = []

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
        file_path = (
                Path(doc.get_file_path()) / f'{doc.name}-{doc.rev}'
        ).with_suffix(
            Path(file.name).suffix
        )
        with file_path.open('wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        doc.uploaded_filename = file_path.name
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
    if material is not None:
        # uploading a replacement, so return to the edit page when done
        next_page = urlreverse('ietf.meeting.views_proceedings.edit_material',
                               kwargs=dict(num=num, material_type=material_type.pk))
    else:
        # for a new item, return to the materials page instead
        next_page = urlreverse('ietf.meeting.views.materials', kwargs=dict(num=num))

    if request.method == 'POST':
        form = UploadProceedingsMaterialForm(request.POST, request.FILES)

        if form.is_valid():
            doc = save_proceedings_material_doc(
                meeting,
                material_type,
                file=form.cleaned_data.get('material', None),
                title=None,
                by=request.user.person,
            )
            if material is None:
                meeting.proceedings_materials.create(type=material_type, document=doc)
            return redirect(next_page)
    else:
        form = UploadProceedingsMaterialForm()

    return render(request, 'meeting/proceedings/upload_material.html', {
        'back_href': next_page,
        'form': form,
        'material': material,
        'material_type': material_type,
        'meeting': meeting,
    })


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
                title=form.cleaned_data['title'],
                file=form.cleaned_data.get('material', None),
                state=form.cleaned_data['state'],
                by=request.user.person,
            )
            return redirect("ietf.meeting.views.materials", num=meeting.number)
    else:
        form = EditProceedingsMaterialForm(
            initial=dict(
                title=material.document.title,
                state=material.document.get_state(),
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
