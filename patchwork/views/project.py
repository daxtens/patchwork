# Patchwork - automated patch tracking system
# Copyright (C) 2009 Jeremy Kerr <jk@ozlabs.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.urls import reverse

from patchwork.models import Patch
from patchwork.models import Project

from django.db import connection


def project_list(request):
    projects = Project.objects.all()

    if projects.count() == 1:
        return HttpResponseRedirect(
            reverse('patch-list',
                    kwargs={'project_id': projects[0].linkname}))

    context = {
        'projects': projects,
    }
    return render(request, 'patchwork/projects.html', context)


def project_detail(request, project_id):
    project = get_object_or_404(Project, linkname=project_id)

    # TODO MIGRATE CLEANUP
    n_patches = {
        archived: Patch.objects.filter(
           patch_project_id=project.id, archived=archived).count()
        for archived in [True, False]
    }

    context = {
        'project': project,
        'maintainers': User.objects.filter(
            profile__maintainer_projects=project).select_related('profile'),
        'n_patches': n_patches[False],
        'n_archived_patches': n_patches[True],
        'enable_xmlrpc': settings.ENABLE_XMLRPC,
    }
    return render(request, 'patchwork/project.html', context)
