# Patchwork - automated patch tracking system
# Copyright (C) 2019 IBM Corporation
#  Author: Daniel Axtens <dja@axtens.net>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.core.management.base import BaseCommand
from django.db.models import Q

from patchwork.models import Patch
from patchwork.models import Submission


class Command(BaseCommand):
    help = 'Do the live migration for flattening patches'

    def handle(self, *args, **options):

        if not hasattr(Submission, 'new_diff'):
            print("Submission model is missing 'new_diff'. Have you applied the migration to add it?")
            return

        diffs = Q(diff__isnull=False, submission_ptr__new_diff__isnull=True)
        pull_urls = Q(pull_url__isnull=False, submission_ptr__new_pull_url__isnull=True)
        archived = Q(archived__isnull=False, submission_ptr__new_archived__isnull=True)
        commit_ref = Q(commit_ref__isnull=False, submission_ptr__new_commit_ref__isnull=True)
        hashq = Q(hash__isnull=False, submission_ptr__new_hash__isnull=True)
        delegate = Q(delegate__isnull=False, submission_ptr__new_delegate__isnull=True)
        state = Q(state__isnull=False, submission_ptr__new_state__isnull=True)
        query = Patch.objects.filter(diffs | pull_urls | archived | commit_ref | hashq | delegate | state)

        count = query.count()

        for i, patch in enumerate(query.iterator()):
            # save does the migration
            patch.save()
            if (i % 10) == 0:
                self.stdout.write('%06d/%06d\r' % (i, count), ending='')
                self.stdout.flush()
        self.stdout.write('\ndone')
