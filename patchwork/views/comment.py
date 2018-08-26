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
    if models.Patch.objects.filter(id=submission.id).exists():
        url = 'patch-detail'
    else:
        url = 'cover-detail'

    return http.HttpResponseRedirect('%s#%s' % (
        reverse(url, kwargs={'project_id': submission.project.linkname,
                             'msgid': submission.url_msgid}), comment_id))


def comment_by_msgid(request, project_id, msgid):
    db_msgid = ('<%s>' % msgid)
    project = shortcuts.get_object_or_404(models.Project, linkname=project_id)
    comment = shortcuts.get_object_or_404(
        models.Comment,
        submission__project_id=project.id,
        msgid=db_msgid)
    if models.Patch.objects.filter(id=comment.submission.id).exists():
        url = 'patch-detail'
    else:
        url = 'cover-detail'

    return http.HttpResponseRedirect('%s#%s' % (
        reverse(url, kwargs={'project_id': project.linkname,
                             'msgid': comment.submission.url_msgid}),
        comment.id))
