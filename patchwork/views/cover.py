# Patchwork - automated patch tracking system
# Copyright (C) 2016 Intel Corporation
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse

from patchwork.models import Patch
from patchwork.models import Project
from patchwork.models import Submission
from patchwork.views.utils import cover_to_mbox


def cover_detail(request, project_id, msgid):
    project = get_object_or_404(Project, linkname=project_id)
    db_msgid = ('<%s>' % msgid)

    # redirect to patches where necessary
    try: #TODO MIGRATE CLEAN
        patch = get_object_or_404(Submission, project_id=project.id,
                                  msgid=db_msgid)
        if patch.is_patch():
            return HttpResponseRedirect(
                reverse('patch-detail',
                        kwargs={'project_id': project.linkname,
                                'msgid': msgid}))
    except Http404:
        pass

    cover = get_object_or_404(Submission, project_id=project.id,
                              msgid=db_msgid)

    context = {
        'submission': cover,
        'project': cover.project,
    }

    comments = cover.comments.all()
    comments = comments.select_related('submitter')
    comments = comments.only('submitter', 'date', 'id', 'content',
                             'submission')
    context['comments'] = comments
    context['series'] = cover.cl_series

    return render(request, 'patchwork/submission.html', context)


def cover_mbox(request, project_id, msgid):
    db_msgid = ('<%s>' % msgid)
    project = get_object_or_404(Project, linkname=project_id)

    # check if we should redirect to patch
    try:
        patch = get_object_or_404(Patch, project_id=project.id,
                              msgid=db_msgid)
        if patch:
            return HttpResponseRedirect(
                reverse('patch-mbox', kwargs={'project_id': project.linkname,
                                              'msgid': msgid}))
    except Http404:
        pass

    cover = get_object_or_404(Submission, project_id=project.id,
                              msgid=db_msgid)

    response = HttpResponse(content_type='text/plain')
    response.write(cover_to_mbox(cover))
    response['Content-Disposition'] = 'attachment; filename=%s.mbox' % (
        cover.filename)

    return response


def cover_by_id(request, cover_id):
    cover = get_object_or_404(Submission, id=cover_id)

    url = reverse('cover-detail', kwargs={'project_id': cover.project.linkname,
                                          'msgid': cover.url_msgid})

    return HttpResponseRedirect(url)


def cover_mbox_by_id(request, cover_id):
    cover = get_object_or_404(Submission, id=cover_id)

    url = reverse('cover-mbox', kwargs={'project_id': cover.project.linkname,
                                        'msgid': cover.url_msgid})

    return HttpResponseRedirect(url)
