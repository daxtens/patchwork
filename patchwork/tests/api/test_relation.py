# Patchwork - automated patch tracking system
# Copyright (C) 2019, Bayerische Motoren Werke Aktiengesellschaft (BMW AG)
#
# SPDX-License-Identifier: GPL-2.0-or-later

import unittest
from enum import Enum
from enum import auto

import six
from django.conf import settings
from django.urls import reverse

from patchwork.models import SubmissionRelation
from patchwork.tests.api import utils
from patchwork.tests.utils import create_maintainer
from patchwork.tests.utils import create_patches
from patchwork.tests.utils import create_project
from patchwork.tests.utils import create_relation
from patchwork.tests.utils import create_user

if settings.ENABLE_REST_API:
    from rest_framework import status


class UserType(Enum):
    ANONYMOUS = auto()
    NON_MAINTAINER = auto()
    MAINTAINER = auto()

@unittest.skipUnless(settings.ENABLE_REST_API, 'requires ENABLE_REST_API')
class TestRelationAPI(utils.APITestCase):
    fixtures = ['default_tags']

    @staticmethod
    def api_url(item=None):
        kwargs = {}
        if item is None:
            return reverse('api-relation-list', kwargs=kwargs)
        kwargs['pk'] = item
        return reverse('api-relation-detail', kwargs=kwargs)

    def request_restricted(self, method, user_type: UserType):
        # setup

        project = create_project()

        if user_type == UserType.ANONYMOUS:
            expected_status = status.HTTP_403_FORBIDDEN
        elif user_type == UserType.NON_MAINTAINER:
            expected_status = status.HTTP_403_FORBIDDEN
            self.client.force_authenticate(user=create_user())
        elif user_type == UserType.MAINTAINER:
            if method == 'post':
                expected_status = status.HTTP_201_CREATED
            elif method == 'delete':
                expected_status = status.HTTP_204_NO_CONTENT
            else:
                expected_status = status.HTTP_200_OK
            user = create_maintainer(project)
            self.client.force_authenticate(user=user)
        else:
            raise ValueError

        resource_id = None
        send = None

        if method == 'delete':
            resource_id = create_relation(project=project).id
        elif method == 'post':
            patch_ids = [p.id for p in create_patches(2, project=project)]
            send = {'submissions': patch_ids}
        elif method == 'patch':
            resource_id = create_relation(project=project).id
            patch_ids = [p.id for p in create_patches(2, project=project)]
            send = {'submissions': patch_ids}
        else:
            raise ValueError

        # request

        resp = getattr(self.client, method)(self.api_url(resource_id), send)

        # check

        self.assertEqual(expected_status, resp.status_code)

        if resp.status_code not in range(200, 202):
            return

        if resource_id:
            self.assertEqual(resource_id, resp.data['id'])

        send_ids = send['submissions']
        resp_ids = resp.data['submissions']
        six.assertCountEqual(self, resp_ids, send_ids)

    def assertSerialized(self, obj: SubmissionRelation, resp: dict):
        self.assertEqual(obj.id, resp['id'])
        obj = [s.id for s in obj.submissions.all()]
        six.assertCountEqual(self, obj, resp['submissions'])

    def test_list_empty(self):
        """List relation when none are present."""
        resp = self.client.get(self.api_url())
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(0, len(resp.data))

    @utils.store_samples('relation-list')
    def test_list(self):
        """List relations."""
        relation = create_relation()

        resp = self.client.get(self.api_url())
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertEqual(1, len(resp.data))
        self.assertSerialized(relation, resp.data[0])

    def test_detail(self):
        """Show relation."""
        relation = create_relation()

        resp = self.client.get(self.api_url(relation.id))
        self.assertEqual(status.HTTP_200_OK, resp.status_code)
        self.assertSerialized(relation, resp.data)

    @utils.store_samples('relation-update-error-forbidden')
    def test_update_anonymous(self):
        """Update relation as anonymous user.

        Ensure updates can be performed by maintainers.
        """
        self.request_restricted('patch', UserType.ANONYMOUS)

    def test_update_non_maintainer(self):
        """Update relation as non-maintainer.

        Ensure updates can be performed by maintainers.
        """
        self.request_restricted('patch', UserType.NON_MAINTAINER)

    @utils.store_samples('relation-update')
    def test_update_maintainer(self):
        """Update relation as maintainer.

        Ensure updates can be performed by maintainers.
        """
        self.request_restricted('patch', UserType.MAINTAINER)

    @utils.store_samples('relation-delete-error-forbidden')
    def test_delete_anonymous(self):
        """Delete relation as anonymous user.

        Ensure deletes can be performed by maintainers.
        """
        self.request_restricted('delete', UserType.ANONYMOUS)

    def test_delete_non_maintainer(self):
        """Delete relation as non-maintainer.

        Ensure deletes can be performed by maintainers.
        """
        self.request_restricted('delete', UserType.NON_MAINTAINER)

    @utils.store_samples('relation-update')
    def test_delete_maintainer(self):
        """Delete relation as maintainer.

        Ensure deletes can be performed by maintainers.
        """
        self.request_restricted('delete', UserType.MAINTAINER)

    @utils.store_samples('relation-create-error-forbidden')
    def test_create_anonymous(self):
        """Create relation as anonymous user.

        Ensure creates can be performed by maintainers.
        """
        self.request_restricted('post', UserType.ANONYMOUS)

    def test_create_non_maintainer(self):
        """Create relation as non-maintainer.

        Ensure creates can be performed by maintainers.
        """
        self.request_restricted('post', UserType.NON_MAINTAINER)

    @utils.store_samples('relation-create')
    def test_create_maintainer(self):
        """Create relation as maintainer.

        Ensure creates can be performed by maintainers.
        """
        self.request_restricted('post', UserType.MAINTAINER)
