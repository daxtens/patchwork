# Patchwork - automated patch tracking system
# Copyright (C) 2016 Stephen Finucane <stephen@that.guru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django import http
from django import shortcuts
from django.urls import reverse

from patchwork import models


def comment(request, comment_id):
    submission = shortcuts.get_object_or_404(models.Comment,
                                             id=comment_id).submission
    if submission.is_patch():
        url = 'patch-detail'
    else:
        url = 'cover-detail'

    return http.HttpResponseRedirect('%s#%s' % (
        reverse(url, kwargs={'project_id': submission.project.linkname,
                             'msgid': submission.url_msgid}), comment_id))
