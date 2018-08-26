# Patchwork - automated patch tracking system
# Copyright (C) 2008 Jeremy Kerr <jk@ozlabs.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib import messages
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse

from patchwork.forms import CreateBundleForm
from patchwork.forms import PatchForm
from patchwork.models import Comment
from patchwork.models import Bundle
from patchwork.models import Patch
from patchwork.models import Project
from patchwork.models import Submission
from patchwork.views import generic_list
from patchwork.views.utils import patch_to_mbox
from patchwork.views.utils import series_patch_to_mbox


def patch_list(request, project_id):
    project = get_object_or_404(Project, linkname=project_id)
    context = generic_list(request, project, 'patch-list',
                           view_args={'project_id': project.linkname})

    if request.user.is_authenticated:
        context['bundles'] = request.user.bundles.all()

    return render(request, 'patchwork/list.html', context)


def patch_detail(request, project_id, msgid):
    project = get_object_or_404(Project, linkname=project_id)
    db_msgid = ('<%s>' % msgid)

    # redirect to cover letters where necessary
    try:
        patch = Patch.objects.get(project_id=project.id, msgid=db_msgid)
    except Patch.DoesNotExist as exc:
        submissions = Submission.objects.filter(project_id=project.id,
                                                msgid=db_msgid)
        if submissions:
            return HttpResponseRedirect(
                reverse('cover-detail',
                        kwargs={'project_id': project.linkname,
                                'msgid': msgid}))
        raise exc

    editable = patch.is_editable(request.user)
    context = {
        'project': patch.project
    }

    form = None
    createbundleform = None

    if editable:
        form = PatchForm(instance=patch)
    if request.user.is_authenticated:
        createbundleform = CreateBundleForm()

    if request.method == 'POST':
        action = request.POST.get('action', None)
        if action:
            action = action.lower()

        if action == 'createbundle':
            bundle = Bundle(owner=request.user, project=project)
            createbundleform = CreateBundleForm(instance=bundle,
                                                data=request.POST)
            if createbundleform.is_valid():
                createbundleform.save()
                bundle.append_patch(patch)
                bundle.save()
                createbundleform = CreateBundleForm()
                messages.success(request, 'Bundle %s created' % bundle.name)
        elif action == 'addtobundle':
            bundle = get_object_or_404(
                Bundle, id=request.POST.get('bundle_id'))
            if bundle.append_patch(patch):
                messages.success(request,
                                 'Patch "%s" added to bundle "%s"' % (
                                     patch.name, bundle.name))
            else:
                messages.error(request,
                               'Failed to add patch "%s" to bundle "%s": '
                               'patch is already in bundle' % (
                                   patch.name, bundle.name))

        # all other actions require edit privs
        elif not editable:
            return HttpResponseForbidden()

        elif action is None:
            form = PatchForm(data=request.POST, instance=patch)
            if form.is_valid():
                form.save()
                messages.success(request, 'Patch updated')

    if request.user.is_authenticated:
        context['bundles'] = request.user.bundles.all()

    comments = patch.comments.all()
    comments = comments.select_related('submitter')
    comments = comments.only('submitter', 'date', 'id', 'content',
                             'submission')

    context['comments'] = comments
    context['checks'] = patch.check_set.all().select_related('user')
    context['submission'] = patch
    context['patchform'] = form
    context['createbundleform'] = createbundleform
    context['project'] = patch.project

    return render(request, 'patchwork/submission.html', context)


def patch_raw(request, project_id, msgid):
    db_msgid = ('<%s>' % msgid)
    project = get_object_or_404(Project, linkname=project_id)
    patch = get_object_or_404(Patch, project_id=project.id, msgid=db_msgid)

    response = HttpResponse(content_type="text/x-patch")
    response.write(patch.diff)
    response['Content-Disposition'] = 'attachment; filename=%s.diff' % (
        patch.filename)

    return response


def patch_mbox(request, project_id, msgid):
    db_msgid = ('<%s>' % msgid)
    project = get_object_or_404(Project, linkname=project_id)
    patch = get_object_or_404(Patch, project_id=project.id, msgid=db_msgid)
    series_id = request.GET.get('series')

    response = HttpResponse(content_type='text/plain')
    if series_id:
        if not patch.series:
            raise Http404('Patch does not have an associated series. This is '
                          'because the patch was processed with an older '
                          'version of Patchwork. It is not possible to '
                          'provide dependencies for this patch.')
        response.write(series_patch_to_mbox(patch, series_id))
    else:
        response.write(patch_to_mbox(patch))
    response['Content-Disposition'] = 'attachment; filename=%s.patch' % (
        patch.filename)

    return response


def patch_by_id(request, patch_id, target):
    patch = get_object_or_404(Patch, id=patch_id)

    url = reverse('patch-detail', kwargs={'project_id': patch.project.linkname,
                                          'msgid': patch.url_msgid})

    if target:
        if target[0] == '/':
            # strip the leading slash as we get a slash from the reverse()
            target = target[1:]
        url += target + '/'

    return HttpResponseRedirect(url)


def patch_by_msgid(request, msgid):
    db_msgid = ('<%s>' % msgid)

    patches = Patch.objects.filter(msgid=db_msgid)
    if patches:
        patch = patches.first()
        return HttpResponseRedirect(
            reverse('patch-detail',
                    kwargs={'project_id': patch.project.linkname,
                            'msgid': patch.url_msgid}))

    subs = Submission.objects.filter(msgid=db_msgid)
    if subs:
        cover = subs.first()
        return HttpResponseRedirect(
            reverse('cover-detail',
                    kwargs={'project_id': cover.project.linkname,
                            'msgid': cover.url_msgid}))

    comments = Comment.objects.filter(msgid=db_msgid)
    if comments:
        return HttpResponseRedirect(comments.first().get_absolute_url())

    raise Http404("No patch, cover letter of comment matching %s found."
                  % msgid)
