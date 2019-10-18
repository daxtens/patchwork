# Patchwork - automated patch tracking system
# Copyright (C) 2019 IBM Corporation
# Author: Daniel Axtens <dja@axtens.net>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.shortcuts import render


def xmlrpc_removed(request, project_id=None):
    return render(request, 'patchwork/xmlrpc-removed.html', {}, status=410)
