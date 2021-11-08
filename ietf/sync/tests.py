# Copyright The IETF Trust 2012-2020, All Rights Reserved
# -*- coding: utf-8 -*-


import os
import io
import json
import datetime
import quopri

from django.conf import settings
from django.urls import reverse as urlreverse

import debug                            # pyflakes:ignore

from ietf.doc.factories import WgDraftFactory
from ietf.doc.models import Document, DocAlias, DocEvent, DeletedEvent, DocTagName, RelatedDocument, State, StateDocEvent
from ietf.doc.utils import add_state_change_event
from ietf.group.factories import GroupFactory
from ietf.person.models import Person
from ietf.sync import iana, rfceditor
from ietf.utils.mail import outbox, empty_outbox
from ietf.utils.test_utils import login_testing_unauthorized
from ietf.utils.test_utils import TestCase


class IANASyncTests(TestCase):
    def test_protocol_page_sync(self):
        draft = WgDraftFactory()
        DocAlias.objects.create(name="rfc1234").docs.add(draft)
        DocEvent.objects.create(doc=draft, rev=draft.rev, type="published_rfc", by=Person.objects.get(name="(System)"))

        rfc_names = iana.parse_protocol_page('<html><a href="/go/rfc1234/">RFC 1234</a></html>')
        self.assertEqual(len(rfc_names), 1)
        self.assertEqual(rfc_names[0], "rfc1234")

        iana.update_rfc_log_from_protocol_page(rfc_names, datetime.datetime.now() - datetime.timedelta(days=1))
        self.assertEqual(DocEvent.objects.filter(doc=draft, type="rfc_in_iana_registry").count(), 1)

        # make sure it doesn't create duplicates
        iana.update_rfc_log_from_protocol_page(rfc_names, datetime.datetime.now() - datetime.timedelta(days=1))
        self.assertEqual(DocEvent.objects.filter(doc=draft, type="rfc_in_iana_registry").count(), 1)

    def test_changes_sync(self):
        draft = WgDraftFactory(ad=Person.objects.get(user__username='ad'))

        data = json.dumps({
            "changes": [
                    {
                        "time": "2011-10-09 12:00:01",
                        "doc": draft.name,
                        "state": "IANA Not OK",
                        "type": "iana_review",
                    },
                    {
                        "time": "2011-10-09 12:00:02",
                        "doc": draft.name,
                        "state": "IANA - Review Needed", # this should be skipped
                        "type": "iana_review",
                    },
                    {
                        "time": "2011-10-09 12:00:00",
                        "doc": draft.name,
                        "state": "Waiting on RFC-Editor",
                        "type": "iana_state",
                    },
                    {
                        "time": "2011-10-09 11:00:00",
                        "doc": draft.name,
                        "state": "In Progress",
                        "type": "iana_state",
                    }
                ]
            })

        changes = iana.parse_changes_json(data)
        # check sorting
        self.assertEqual(changes[0]["time"], "2011-10-09 11:00:00")

        empty_outbox()
        added_events, warnings = iana.update_history_with_changes(changes)

        self.assertEqual(len(added_events), 3)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(draft.get_state_slug("draft-iana-review"), "not-ok")
        self.assertEqual(draft.get_state_slug("draft-iana-action"), "waitrfc")
        e = draft.latest_event(StateDocEvent, type="changed_state", state_type="draft-iana-action")
        self.assertEqual(e.desc, "IANA Action state changed to <b>Waiting on RFC Editor</b> from In Progress")
#        self.assertEqual(e.time, datetime.datetime(2011, 10, 9, 5, 0)) # check timezone handling
        self.assertEqual(len(outbox), 3 )
        for m in outbox:
            self.assertTrue('aread@' in m['To']) 

        # make sure it doesn't create duplicates
        added_events, warnings = iana.update_history_with_changes(changes)
        self.assertEqual(len(added_events), 0)
        self.assertEqual(len(warnings), 0)

    def test_changes_sync_errors(self):
        draft = WgDraftFactory()

        # missing "type"
        data = json.dumps({
                "changes": [
                        {
                            "time": "2011-10-09 12:00:01",
                            "doc": draft.name,
                            "state": "IANA Not OK",
                        },
                    ]
            })

        self.assertRaises(Exception, iana.parse_changes_json, data)

        # error response
        data = json.dumps({
                "error": "I am in error."
            })

        self.assertRaises(Exception, iana.parse_changes_json, data)
        
        # missing document from database
        data = json.dumps({
                "changes": [
                        {
                            "time": "2011-10-09 12:00:01",
                            "doc": "draft-this-does-not-exist",
                            "state": "IANA Not OK",
                            "type": "iana_review",
                        },
                    ]
            })

        changes = iana.parse_changes_json(data)
        added_events, warnings = iana.update_history_with_changes(changes)
        self.assertEqual(len(added_events), 0)
        self.assertEqual(len(warnings), 1)

    def test_iana_review_mail(self):
        draft = WgDraftFactory()

        subject_template = 'Subject: [IANA #12345] Last Call: <%(draft)s-%(rev)s.txt> (Long text) to Informational RFC'
        msg_template = """From: %(fromaddr)s
Date: Thu, 10 May 2012 12:00:0%(rtime)d +0000
Content-Transfer-Encoding: quoted-printable
Content-Type: text/plain; charset=utf-8
%(subject)s

(BEGIN IANA %(tag)s%(embedded_name)s)

IESG:

IANA has reviewed %(draft)s-%(rev)s, which is=20
currently in Last Call, and has the following comments:

IANA understands that, upon approval of this document, there are no=20
IANA Actions that need completion.

Thanks,

%(person)s
IANA “Fake Test” Person
ICANN

(END IANA %(tag)s)
"""

        subjects =  ( subject_template % dict(draft=draft.name,rev=draft.rev) , 'Subject: Vacuous Subject' )

        tags = ('LAST CALL COMMENTS', 'COMMENTS')

        embedded_names = (': %s-%s.txt'%(draft.name,draft.rev), '')

        for subject in subjects:
            for tag in tags:
                for embedded_name in embedded_names:
                    if embedded_name or not 'Vacuous' in subject: 
                    
                        rtime = 7*subjects.index(subject) + 5*tags.index(tag) + embedded_names.index(embedded_name)
                        person=Person.objects.get(user__username="iana")
                        fromaddr = person.email().formatted_email()
                        msg = msg_template % dict(person=quopri.encodestring(person.name.encode('utf-8')),
                                                  fromaddr=fromaddr,
                                                  draft=draft.name,
                                                  rev=draft.rev,
                                                  tag=tag,
                                                  rtime=rtime,
                                                  subject=subject,
                                                  embedded_name=embedded_name,)
                        doc_name, review_time, by, comment = iana.parse_review_email(msg.encode('utf-8'))
    
                        self.assertEqual(doc_name, draft.name)
                        self.assertEqual(review_time, datetime.datetime(2012, 5, 10, 5, 0, rtime))
                        self.assertEqual(by, Person.objects.get(user__username="iana"))
                        self.assertIn("there are no IANA Actions", comment.replace("\n", ""))
    
                        events_before = DocEvent.objects.filter(doc=draft, type="iana_review").count()
                        iana.add_review_comment(doc_name, review_time, by, comment)
    
                        e = draft.latest_event(type="iana_review")
                        self.assertTrue(e)
                        self.assertEqual(e.desc, comment)
                        self.assertEqual(e.by, by)
    
                        # make sure it doesn't create duplicates
                        iana.add_review_comment(doc_name, review_time, by, comment)
                        self.assertEqual(DocEvent.objects.filter(doc=draft, type="iana_review").count(), events_before+1)

    def test_notify_page(self):
        # check that we can get the notify page
        url = urlreverse("ietf.sync.views.notify", kwargs=dict(org="iana", notification="changes"))
        login_testing_unauthorized(self, "secretary", url)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "new changes at")

        # we don't actually try posting as that would trigger a real run
        

class RFCSyncTests(TestCase):
    def write_draft_file(self, name, size):
        with io.open(os.path.join(settings.INTERNET_DRAFT_PATH, name), 'w') as f:
            f.write("a" * size)

    def test_rfc_index(self):
        area = GroupFactory(type_id='area')
        doc = WgDraftFactory(
            group__parent=area,
            states=[('draft-iesg','rfcqueue'),('draft-stream-ise','rfc-edit')],
            ad=Person.objects.get(user__username='ad'),
        )
        # it's a bit strange to have draft-stream-ise set when draft-iesg is set
        # too, but for testing purposes ...
        doc.action_holders.add(doc.ad)  # not normally set, but add to be sure it's cleared

        updated_doc = Document.objects.create(name="draft-ietf-something")
        DocAlias.objects.create(name=updated_doc.name).docs.add(updated_doc)
        DocAlias.objects.create(name="rfc123").docs.add(updated_doc)

        today = datetime.date.today()

        t = '''<?xml version="1.0" encoding="UTF-8"?>
<rfc-index xmlns="http://www.rfc-editor.org/rfc-index"
           xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" 
           xsi:schemaLocation="http://www.rfc-editor.org/rfc-index 
                               http://www.rfc-editor.org/rfc-index.xsd">
    <bcp-entry>
        <doc-id>BCP0001</doc-id>
        <is-also>
            <doc-id>RFC1234</doc-id>
            <doc-id>RFC2345</doc-id>
        </is-also>
    </bcp-entry>
    <fyi-entry>
        <doc-id>FYI0001</doc-id>
        <is-also>
            <doc-id>RFC1234</doc-id>
        </is-also>
    </fyi-entry>
    <std-entry>
        <doc-id>STD0001</doc-id>
        <title>Test</title>
        <is-also>
            <doc-id>RFC1234</doc-id>
        </is-also>
    </std-entry>
    <rfc-entry>
        <doc-id>RFC1234</doc-id>
        <title>A Testing RFC</title>
        <author>
            <name>A. Irector</name>
        </author>
        <date>
            <month>%(month)s</month>
            <year>%(year)s</year>
        </date>
        <format>
            <file-format>ASCII</file-format>
        </format>
        <page-count>42</page-count>
        <keywords>
            <kw>test</kw>
        </keywords>
        <abstract><p>This is some interesting text.</p></abstract>
        <draft>%(name)s-%(rev)s</draft>
        <updates>
            <doc-id>RFC123</doc-id>
        </updates>
        <is-also>
            <doc-id>BCP0001</doc-id>
        </is-also>
        <current-status>PROPOSED STANDARD</current-status>
        <publication-status>PROPOSED STANDARD</publication-status>
        <stream>IETF</stream>
        <area>%(area)s</area>
        <wg_acronym>%(group)s</wg_acronym>
        <errata-url>http://www.rfc-editor.org/errata_search.php?rfc=1234</errata-url>
    </rfc-entry>
</rfc-index>''' % dict(year=today.strftime("%Y"),
                       month=today.strftime("%B"),
                       name=doc.name,
                       rev=doc.rev,
                       area=doc.group.parent.acronym,
                       group=doc.group.acronym)

        errata = [{
                "errata_id":1,
                "doc-id":"RFC123",
                "errata_status_code":"Verified",
                "errata_type_code":"Editorial",
                "section": "4.1",
                "orig_text":"   S: 220-smtp.example.com ESMTP Server",
                "correct_text":"   S: 220 smtp.example.com ESMTP Server",
                "notes":"There are 3 instances of this (one on p. 7 and two on p. 8). \n",
                "submit_date":"2007-07-19",
                "submitter_name":"Rob Siemborski",
                "verifier_id":99,
                "verifier_name":None,
                "update_date":"2019-09-10 09:09:03"},
        ]

        data = rfceditor.parse_index(io.StringIO(t))
        self.assertEqual(len(data), 1)

        rfc_number, title, authors, rfc_published_date, current_status, updates, updated_by, obsoletes, obsoleted_by, also, draft, has_errata, stream, wg, file_formats, pages, abstract = data[0]

        # currently, we only check what we actually use
        self.assertEqual(rfc_number, 1234)
        self.assertEqual(title, "A Testing RFC")
        self.assertEqual(rfc_published_date.year, today.year)
        self.assertEqual(rfc_published_date.month, today.month)
        self.assertEqual(current_status, "Proposed Standard")
        self.assertEqual(updates, ["RFC123"])
        self.assertEqual(set(also), set(["BCP1", "FYI1", "STD1"]))
        self.assertEqual(draft, doc.name)
        self.assertEqual(wg, doc.group.acronym)
        self.assertEqual(has_errata, True)
        self.assertEqual(stream, "IETF")
        self.assertEqual(pages, "42")
        self.assertEqual(abstract, "This is some interesting text.")

        draft_filename = "%s-%s.txt" % (doc.name, doc.rev)
        self.write_draft_file(draft_filename, 5000)

        changes = []
        for cs, d, rfc_published in rfceditor.update_docs_from_rfc_index(data, errata, today - datetime.timedelta(days=30)):
            changes.append(cs)

        doc = Document.objects.get(name=doc.name)

        events = doc.docevent_set.all()
        self.assertEqual(events[0].type, "sync_from_rfc_editor")
        self.assertEqual(events[1].type, "changed_action_holders")
        self.assertEqual(events[2].type, "published_rfc")
        self.assertEqual(events[2].time.date(), today)
        self.assertTrue("errata" in doc.tags.all().values_list("slug", flat=True))
        self.assertTrue(DocAlias.objects.filter(name="rfc1234", docs=doc))
        self.assertTrue(DocAlias.objects.filter(name="bcp1", docs=doc))
        self.assertTrue(DocAlias.objects.filter(name="fyi1", docs=doc))
        self.assertTrue(DocAlias.objects.filter(name="std1", docs=doc))
        self.assertTrue(RelatedDocument.objects.filter(source=doc, target__name="rfc123", relationship="updates"))
        self.assertEqual(doc.title, "A Testing RFC")
        self.assertEqual(doc.abstract, "This is some interesting text.")
        self.assertEqual(doc.get_state_slug(), "rfc")
        self.assertEqual(doc.get_state_slug("draft-iesg"), "pub")
        self.assertCountEqual(doc.action_holders.all(), [])
        self.assertEqual(doc.get_state_slug("draft-stream-ise"), "pub")
        self.assertEqual(doc.std_level_id, "ps")
        self.assertEqual(doc.pages, 42)
        self.assertTrue(not os.path.exists(os.path.join(settings.INTERNET_DRAFT_PATH, draft_filename)))
        self.assertTrue(os.path.exists(os.path.join(settings.INTERNET_DRAFT_ARCHIVE_DIR, draft_filename)))

        # make sure we can apply it again with no changes
        changed = list(rfceditor.update_docs_from_rfc_index(data, errata, today - datetime.timedelta(days=30)))
        self.assertEqual(len(changed), 0)

    def _generate_rfc_queue_xml(self, draft, state, auth48_url=None):
        """Generate an RFC queue xml string for a draft"""
        t = '''<rfc-editor-queue xmlns="http://www.rfc-editor.org/rfc-editor-queue">
<section name="IETF STREAM: WORKING GROUP STANDARDS TRACK">
<entry xml:id="%(name)s">
<draft>%(name)s-%(rev)s.txt</draft>
<date-received>2010-09-08</date-received>
<state>%(state)s</state>
<auth48-url>%(auth48_url)s</auth48-url>
<normRef>
<ref-name>%(ref)s</ref-name>
<ref-state>IN-QUEUE</ref-state>
</normRef>
<authors>A. Author</authors>
<title>
%(title)s
</title>
<bytes>10000000</bytes>
<source>%(group)s</source>
</entry>
</section>
</rfc-editor-queue>''' % dict(name=draft.name,
                              rev=draft.rev,
                              title=draft.title,
                              group=draft.group.name,
                              ref="draft-ietf-test",
                              state=state,
                              auth48_url=(auth48_url or ''))
        t = t.replace('<auth48-url></auth48-url>\n', '')  # strip empty auth48-url tags
        return t

    def test_rfc_queue(self):
        draft = WgDraftFactory(states=[('draft-iesg','ann')], ad=Person.objects.get(user__username='ad'))
        draft.action_holders.add(draft.ad)  # add an action holder so we can test that it's removed later

        expected_auth48_url = "http://www.rfc-editor.org/auth48/rfc1234"
        t = self._generate_rfc_queue_xml(draft,
                                         state='EDIT*R*A(1G)',
                                         auth48_url=expected_auth48_url)

        drafts, warnings = rfceditor.parse_queue(io.StringIO(t))
        # rfceditor.parse_queue() is tested independently; just sanity check here
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(warnings), 0)

        mailbox_before = len(outbox)

        changed, warnings = rfceditor.update_drafts_from_queue(drafts)
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)

        draft = Document.objects.get(pk=draft.pk)
        self.assertEqual(draft.get_state_slug("draft-rfceditor"), "edit")
        self.assertEqual(draft.get_state_slug("draft-iesg"), "rfcqueue")
        self.assertCountEqual(draft.action_holders.all(), [])
        self.assertEqual(set(draft.tags.all()), set(DocTagName.objects.filter(slug__in=("iana", "ref"))))
        events = draft.docevent_set.all()
        self.assertEqual(events[0].type, "changed_state") # changed draft-iesg state
        self.assertEqual(events[1].type, "changed_action_holders")
        self.assertEqual(events[2].type, "changed_state") # changed draft-rfceditor state
        self.assertEqual(events[3].type, "rfc_editor_received_announcement")

        self.assertEqual(len(outbox), mailbox_before + 1)
        self.assertTrue("RFC Editor queue" in outbox[-1]["Subject"])

        # make sure we can apply it again with no changes
        changed, warnings = rfceditor.update_drafts_from_queue(drafts)
        self.assertEqual(len(changed), 0)
        self.assertEqual(len(warnings), 0)

    def test_rfceditor_parse_queue(self):
        """Test that rfceditor.parse_queue() behaves as expected.

        Currently does a limited test - old comment was 
        "currently, we only check what we actually use".
        """
        draft = WgDraftFactory(states=[('draft-iesg','ann')])
        t = self._generate_rfc_queue_xml(draft,
                                         state='EDIT*R*A(1G)',
                                         auth48_url="http://www.rfc-editor.org/auth48/rfc1234")

        drafts, warnings = rfceditor.parse_queue(io.StringIO(t))
        self.assertEqual(len(drafts), 1)
        self.assertEqual(len(warnings), 0)

        draft_name, date_received, state, tags, missref_generation, stream, auth48, cluster, refs = drafts[0]
        self.assertEqual(draft_name, draft.name)
        self.assertEqual(state, "EDIT")
        self.assertEqual(set(tags), set(["iana", "ref"]))
        self.assertEqual(auth48, "http://www.rfc-editor.org/auth48/rfc1234")

    def test_rfceditor_parse_queue_TI_state(self):
        # Test with TI state introduced 11 Sep 2019
        draft = WgDraftFactory(states=[('draft-iesg','ann')])
        t = self._generate_rfc_queue_xml(draft,
                                         state='TI',
                                         auth48_url="http://www.rfc-editor.org/auth48/rfc1234")
        __, warnings = rfceditor.parse_queue(io.StringIO(t))
        self.assertEqual(len(warnings), 0)

    def _generate_rfceditor_update(self, draft, state, tags=None, auth48_url=None):
        """Helper to generate fake output from rfceditor.parse_queue()"""
        return [[
            draft.name, # draft_name
            '2020-06-03',  # date_received
            state,
            tags or [],
            '1',  # missref_generation
            'ietf',  # stream
            auth48_url or '',
            '',  # cluster
            ['draft-ietf-test'],  # refs
        ]]

    def test_update_draft_auth48_url(self):
        """Test that auth48 URLs are handled correctly."""
        draft = WgDraftFactory(states=[('draft-iesg','ann')])

        # Step 1 setup: update to a state with no auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='EDIT')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNone(auth48_docurl)

        # Step 2: update to auth48 state with auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='AUTH48', auth48_url='http://www.rfc-editor.org/rfc1234')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNotNone(auth48_docurl)
        self.assertEqual(auth48_docurl.url, 'http://www.rfc-editor.org/rfc1234')

        # Step 3: update to auth48-done state without auth48 URL
        changed, warnings = rfceditor.update_drafts_from_queue(
            self._generate_rfceditor_update(draft, state='AUTH48-DONE')
        )
        self.assertEqual(len(changed), 1)
        self.assertEqual(len(warnings), 0)
        auth48_docurl = draft.documenturl_set.filter(tag_id='auth48').first()
        self.assertIsNone(auth48_docurl)


class DiscrepanciesTests(TestCase):
    def test_discrepancies(self):

        # draft approved but no RFC Editor state
        doc = Document.objects.create(name="draft-ietf-test1", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="ann"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with IANA state "In Progress" but RFC Editor state not IANA
        doc = Document.objects.create(name="draft-ietf-test2", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="rfcqueue"))
        doc.set_state(State.objects.get(used=True, type="draft-iana-action", slug="inprog"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="auth"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with IANA state "Waiting on RFC Editor" or "RFC-Ed-Ack"
        # but RFC Editor state is IANA
        doc = Document.objects.create(name="draft-ietf-test3", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="rfcqueue"))
        doc.set_state(State.objects.get(used=True, type="draft-iana-action", slug="waitrfc"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="iana"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

        # draft with state other than "RFC Ed Queue" or "RFC Published"
        # that are in RFC Editor or IANA queues
        doc = Document.objects.create(name="draft-ietf-test4", type_id="draft")
        doc.set_state(State.objects.get(used=True, type="draft-iesg", slug="ann"))
        doc.set_state(State.objects.get(used=True, type="draft-rfceditor", slug="auth"))

        r = self.client.get(urlreverse("ietf.sync.views.discrepancies"))
        self.assertContains(r, doc.name)

class RFCEditorUndoTests(TestCase):
    def test_rfceditor_undo(self):
        draft = WgDraftFactory()

        e1 = add_state_change_event(draft, Person.objects.get(name="(System)"), None,
                                   State.objects.get(used=True, type="draft-rfceditor", slug="auth"))
        e1.desc = "First"
        e1.save()

        e2 = add_state_change_event(draft, Person.objects.get(name="(System)"), None,
                                   State.objects.get(used=True, type="draft-rfceditor", slug="edit"))
        e2.desc = "Second"
        e2.save()
        
        url = urlreverse('ietf.sync.views.rfceditor_undo')
        login_testing_unauthorized(self, "rfc", url)

        # get
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, e2.doc.name)

        # delete e2
        deleted_before = DeletedEvent.objects.count()

        r = self.client.post(url, dict(event=e2.id))
        self.assertEqual(r.status_code, 302)

        self.assertEqual(StateDocEvent.objects.filter(id=e2.id).count(), 0)
        self.assertEqual(draft.get_state("draft-rfceditor").slug, "auth")
        self.assertEqual(DeletedEvent.objects.count(), deleted_before + 1)

        # delete e1
        draft.state_cache = None
        r = self.client.post(url, dict(event=e1.id))
        self.assertEqual(draft.get_state("draft-rfceditor"), None)

        # let's just test we can recover
        e = DeletedEvent.objects.all().order_by("-time", "-id")[0]

        e.content_type.model_class().objects.create(**json.loads(e.json))
        self.assertTrue(StateDocEvent.objects.filter(desc="First", doc=draft))
