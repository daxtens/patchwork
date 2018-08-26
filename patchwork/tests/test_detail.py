# Patchwork - automated patch tracking system
# Copyright (C) 2016 Intel Corporation
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.test import TestCase
from django.urls import reverse

from patchwork.tests.utils import create_comment
from patchwork.tests.utils import create_cover
from patchwork.tests.utils import create_patch


class CoverLetterViewTest(TestCase):

    def test_redirect(self):
        patch = create_patch()

        requested_url = reverse('cover-detail',
                                kwargs={'project_id': patch.project.linkname,
                                        'msgid': patch.url_msgid})
        redirect_url = reverse('patch-detail',
                               kwargs={'project_id': patch.project.linkname,
                                       'msgid': patch.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_old_detail_url(self):
        cover = create_cover()

        requested_url = reverse('cover-id-redirect',
                                kwargs={'cover_id': cover.id,
                                        'target': ''})
        redirect_url = reverse('cover-detail',
                               kwargs={'project_id': cover.project.linkname,
                                       'msgid': cover.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_old_mbox_url(self):
        cover = create_cover()

        requested_url = reverse('cover-id-redirect',
                                kwargs={'cover_id': cover.id,
                                        'target': '/mbox'})
        self.assertEqual(requested_url[-6:], '/mbox/')
        redirect_url = reverse('cover-mbox',
                               kwargs={'project_id': cover.project.linkname,
                                       'msgid': cover.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)


class PatchViewTest(TestCase):

    def test_redirect(self):
        cover = create_cover()

        requested_url = reverse('patch-detail',
                                kwargs={'project_id': cover.project.linkname,
                                        'msgid': cover.url_msgid})
        redirect_url = reverse('cover-detail',
                               kwargs={'project_id': cover.project.linkname,
                                       'msgid': cover.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_old_detail_url(self):
        patch = create_patch()

        requested_url = reverse('patch-id-redirect',
                                kwargs={'patch_id': patch.id,
                                        'target': ''})
        redirect_url = reverse('patch-detail',
                               kwargs={'project_id': patch.project.linkname,
                                       'msgid': patch.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_old_mbox_url(self):
        patch = create_patch()

        requested_url = reverse('patch-id-redirect',
                                kwargs={'patch_id': patch.id,
                                        'target': '/mbox'})
        self.assertEqual(requested_url[-6:], '/mbox/')
        redirect_url = reverse('patch-mbox',
                               kwargs={'project_id': patch.project.linkname,
                                       'msgid': patch.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_old_raw_url(self):
        patch = create_patch()

        requested_url = reverse('patch-id-redirect',
                                kwargs={'patch_id': patch.id,
                                        'target': '/raw'})
        self.assertEqual(requested_url[-5:], '/raw/')
        redirect_url = reverse('patch-raw',
                               kwargs={'project_id': patch.project.linkname,
                                       'msgid': patch.url_msgid})

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)


class CommentRedirectTest(TestCase):

    def _test_redirect(self, submission, submission_url):
        comment_id = create_comment(submission=submission).id

        requested_url = reverse('comment-redirect',
                                kwargs={'comment_id': comment_id})
        redirect_url = '%s#%d' % (
            reverse(submission_url,
                    kwargs={'project_id': submission.project.linkname,
                            'msgid': submission.url_msgid}),
            comment_id)

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def _test_msgid_redirect(self, submission, submission_url):
        comment = create_comment(submission=submission)

        requested_url = reverse(
            'comment-msgid-redirect',
            kwargs={'msgid': comment.url_msgid,
                    'project_id': submission.project.linkname})

        redirect_url = '%s#%d' % (
            reverse(submission_url,
                    kwargs={'project_id': submission.project.linkname,
                            'msgid': submission.url_msgid}),
            comment.id)

        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_patch_redirect(self):
        patch = create_patch()
        self._test_redirect(patch, 'patch-detail')
        self._test_msgid_redirect(patch, 'patch-detail')

    def test_cover_redirect(self):
        cover = create_cover()
        self._test_redirect(cover, 'cover-detail')
        self._test_msgid_redirect(cover, 'cover-detail')


class GenericRedirectTest(TestCase):

    def _test_redirect(self, message, view):
        requested_url = reverse('msgid-redirect',
                                kwargs={'msgid': message.url_msgid})

        redirect_url = reverse(view,
                               kwargs={'project_id': message.project.linkname,
                                       'msgid': message.url_msgid})
        response = self.client.get(requested_url)
        self.assertRedirects(response, redirect_url)

    def test_patch(self):
        patch = create_patch()
        self._test_redirect(patch, 'patch-detail')

    def test_cover(self):
        cover = create_cover()
        self._test_redirect(cover, 'cover-detail')

    def test_comment(self):
        comment = create_comment()
        requested_url = reverse('msgid-redirect',
                                kwargs={'msgid': comment.url_msgid})

        redirect_url = '%s#%d' % (
            reverse('patch-detail',
                    kwargs={'project_id': comment.submission.project.linkname,
                            'msgid': comment.submission.url_msgid}),
            comment.id)

        # this will redirect twice - once to the comment form, and then
        # once to the final destination. Hence follow=True.
        response = self.client.get(requested_url, follow=True)
        self.assertRedirects(response, redirect_url)
