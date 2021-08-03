# Copyright The IETF Trust 2021, All Rights Reserved
# -*- coding: utf-8 -*-

from django import template

import debug                            # pyflakes:ignore

register = template.Library()


@register.filter
def merge_media(forms, arg=None):
    """Merge media for a list of forms
    
    Usage: {{ form_list|merge_media }}
      * With no arg, returns all media from all forms with duplicates removed
    
    Usage: {{ form_list|merge_media:'media_type' }}
      * With an arg, returns only media of that type. Types 'css' and 'js' are common.
        See Django documentation for more information about form media.
    """
    if len(forms) == 0:
        return ''
    combined = forms[0].media
    if len(forms) > 1:
        for val in forms[1:]:
            combined += val.media
    if arg is None:
        return str(combined)
    return str(combined[arg])


@register.filter
def keep_only(items, arg):
    """Filter list of items based on an attribute

    Usage: {{ item_list|keep_only:'attribute' }}
      Returns the list, keeping only those whose where item[attribute] or item.attribute is
      present and truthy. The attribute can be an int or a string.
    """
    def _test(item):
        try:
            return item[arg]
        except TypeError:
            return getattr(item, arg, False)

    return [item for item in items if _test(item)]
