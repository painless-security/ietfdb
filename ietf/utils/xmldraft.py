# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-
import os
import xml2rfc

import debug  # pyflakes: ignore

from contextlib import ExitStack

from django.conf import settings

from .draft import Draft


class XMLDraft(Draft):
    """Draft from XML source

    Currently just a holding place for get_refs() for an XML file. Can eventually expand
    to implement the other public methods of Draft as need arises.
    """
    def __init__(self, xml_file):
        """Initialize XMLDraft instance

        :parameter xml_file: path to file containing XML source
        """
        super().__init__()
        # cast xml_file to str so, e.g., this will work with a Path
        self.xmltree = self.parse_xml(str(xml_file))
        self.xmlroot = self.xmltree.getroot()

    @staticmethod
    def parse_xml(filename):
        orig_write_out = xml2rfc.log.write_out
        orig_write_err = xml2rfc.log.write_err
        orig_xml_library = os.environ.get('XML_LIBRARY', None)
        tree = None
        with ExitStack() as stack:
            @stack.callback
            def cleanup():  # called when context exited, even if there's an exception
                xml2rfc.log.write_out = orig_write_out
                xml2rfc.log.write_err = orig_write_err
                os.environ.pop('XML_LIBRARY')
                if orig_xml_library is not None:
                    os.environ['XML_LIBRARY'] = orig_xml_library

            xml2rfc.log.write_out = open(os.devnull, 'w')
            xml2rfc.log.write_err = open(os.devnull, 'w')
            os.environ['XML_LIBRARY'] = settings.XML_LIBRARY

            parser = xml2rfc.XmlRfcParser(filename, quiet=True)
            tree = parser.parse()
            xml_version = tree.getroot().get('version', '2')
            if xml_version == '2':
                v2v3 = xml2rfc.V2v3XmlWriter(tree)
                tree.tree = v2v3.convert2to3()
        return tree

    def get_refs(self):
        """Extract references from the draft"""
        # map string appearing in <references> name to REF_TYPE_*
        known_ref_types = {
            'normative': self.REF_TYPE_NORMATIVE,
            'informative': self.REF_TYPE_INFORMATIVE,
        }

        refs = {}
        # accept nested <references> sections
        ref_sections = self.xmlroot.findall('back//references')
        for section in ref_sections:
            # figure out what type of references are in this section
            ref_type = self.REF_TYPE_UNKNOWN
            name = section.findtext('name').lower()
            for substr in known_ref_types:
                if substr in name:
                    ref_type = known_ref_types[substr]
                    break

            # collect the references
            for ref in section.findall('.//reference'):
                for series_info in ref.findall('seriesInfo'):
                    series_name = series_info.get('name').lower()
                    if series_name == 'rfc':
                        rfc_number = int(series_info.get('value'))
                        ref_name = f'rfc{rfc_number}'
                    elif series_name == 'internet-draft':
                        ref_name = series_info.get('value')
                    else:
                        ref_name = None
                    if ref_name is not None:
                        refs[ref_name] = ref_type
        return refs
