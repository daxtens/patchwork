# Patchwork - automated patch tracking system
# Copyright (C) 2008 Jeremy Kerr <jk@ozlabs.org>
#
# This file is part of the Patchwork package.
#
# Patchwork is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# Patchwork is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Patchwork; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from email import message_from_file
from email import message_from_string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
import os

from django.test import TestCase

from patchwork.models import Comment
from patchwork.models import Patch
from patchwork.models import Person
from patchwork.models import State
from patchwork.parser import clean_subject
from patchwork.parser import find_author
from patchwork.parser import find_content
from patchwork.parser import find_project_by_header
from patchwork.parser import parse_mail as _parse_mail
from patchwork.parser import parse_pull_request
from patchwork.parser import parse_series_marker
from patchwork.parser import split_prefixes
from patchwork.parser import subject_check
from patchwork.tests.utils import create_project
from patchwork.tests.utils import create_state
from patchwork.tests.utils import create_user
from patchwork.tests.utils import read_patch
from patchwork.tests.utils import SAMPLE_DIFF


TEST_MAIL_DIR = os.path.join(os.path.dirname(__file__), 'mail')


def read_mail(filename, project=None):
    """Read a mail from a file."""
    file_path = os.path.join(TEST_MAIL_DIR, filename)
    mail = message_from_file(open(file_path))
    if 'Message-Id' not in mail:
        mail['Message-Id'] = make_msgid()
    if project is not None:
        mail['List-Id'] = project.listid
    return mail


def _create_email(msg, msgid=None, sender=None, listid=None):
    msg['Message-Id'] = msgid or make_msgid()
    msg['Subject'] = 'Test subject'
    msg['From'] = sender or 'Test Author <test-author@example.com>'
    msg['List-Id'] = listid or 'test.example.com'

    return msg


def create_email(content, msgid=None, sender=None, listid=None):
    msg = MIMEText(content, _charset='us-ascii')

    return _create_email(msg, msgid, sender, listid)


def parse_mail(*args, **kwargs):
    create_state()
    return _parse_mail(*args, **kwargs)


class PatchTest(TestCase):

    def setUp(self):
        self.project = create_project()

    def _find_content(self, mbox_filename):
        mail = read_mail(mbox_filename, project=self.project)
        diff, message = find_content(self.project, mail)

        return diff, message


class InlinePatchTest(PatchTest):

    orig_content = 'Test for attached patch'
    orig_diff = read_patch('0001-add-line.patch')

    def setUp(self):
        email = create_email(self.orig_content + '\n' + self.orig_diff)

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)

    def test_patch_content(self):
        self.assertEqual(self.diff, self.orig_diff)

    def test_patch_diff(self):
        self.assertEqual(self.content, self.orig_content)


class AttachmentPatchTest(InlinePatchTest):

    orig_content = 'Test for attached patch'
    content_subtype = 'x-patch'

    def setUp(self):
        msg = MIMEMultipart()
        body = MIMEText(self.orig_content, _subtype='plain')
        attachment = MIMEText(self.orig_diff, _subtype=self.content_subtype)
        msg.attach(body)
        msg.attach(attachment)
        email = _create_email(msg)

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)


class AttachmentXDiffPatchTest(AttachmentPatchTest):

    content_subtype = 'x-diff'


class UTF8InlinePatchTest(InlinePatchTest):

    orig_diff = read_patch('0002-utf-8.patch', 'utf-8')

    def setUp(self):
        msg = MIMEText(self.orig_content + '\n' + self.orig_diff,
                       _charset='utf-8')
        email = _create_email(msg)

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)


class NoCharsetInlinePatchTest(InlinePatchTest):
    """Test mails with no content-type or content-encoding header."""

    def setUp(self):
        email = create_email(self.orig_content + '\n' + self.orig_diff)
        del email['Content-Type']
        del email['Content-Transfer-Encoding']

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)


class SignatureCommentTest(InlinePatchTest):

    orig_content = 'Test comment\nmore comment'

    def setUp(self):
        email = create_email(self.orig_content + '\n-- \nsig\n' +
                             self.orig_diff)

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)


class UpdateSigCommentTest(SignatureCommentTest):
    """Test for '---\nUpdate: v2' style comments to patches, with a sig."""

    patch_filename = '0001-add-line.patch'
    orig_content = 'Test comment\nmore comment\n---\nUpdate: test update'


class ListFooterTest(InlinePatchTest):

    orig_content = 'Test comment\nmore comment'

    def setUp(self):
        email = create_email('\n'.join([
            self.orig_content,
            '_______________________________________________',
            'Linuxppc-dev mailing list',
            self.orig_diff]))

        self.project = create_project()
        self.diff, self.content = find_content(self.project, email)


class DiffWordInCommentTest(InlinePatchTest):

    orig_content = 'Lines can start with words beginning in "diff"\n' + \
                   'difficult\nDifferent'


class UpdateCommentTest(InlinePatchTest):
    """Test for '---\nUpdate: v2' style comments to patches."""

    orig_content = 'Test comment\nmore comment\n---\nUpdate: test update'


class SenderEncodingTest(TestCase):
    """Validate correct handling of encoded recipients."""

    @staticmethod
    def _create_email(from_header):
        mail = 'Message-Id: %s\n' % make_msgid() + \
               'From: %s\n' % from_header + \
               'Subject: test\n\n' + \
               'test'
        return message_from_string(mail)

    def _test_encoding(self, from_header, sender_name, sender_email):
        email = self._create_email(from_header)
        person = find_author(email)
        person.save()

        # ensure it was parsed correctly
        self.assertEqual(person.name, sender_name)
        self.assertEqual(person.email, sender_email)

        # ...and that it's queryable from DB
        db_person = Person.objects.get(name=sender_name)
        self.assertEqual(person, db_person)
        db_person = Person.objects.get(email=sender_email)
        self.assertEqual(person, db_person)

    def test_empty(self):
        email = self._create_email('')
        with self.assertRaises(ValueError):
            find_author(email)

    def test_ascii_encoding(self):
        from_header = 'example user <user@example.com>'
        sender_name = u'example user'
        sender_email = 'user@example.com'
        self._test_encoding(from_header, sender_name, sender_email)

    def test_utf8qp_encoding(self):
        from_header = '=?utf-8?q?=C3=A9xample=20user?= <user@example.com>'
        sender_name = u'\xe9xample user'
        sender_email = 'user@example.com'
        self._test_encoding(from_header, sender_name, sender_email)

    def test_utf8qp_split_encoding(self):
        from_header = '=?utf-8?q?=C3=A9xample?= user <user@example.com>'
        sender_name = u'\xe9xample user'
        sender_email = 'user@example.com'
        self._test_encoding(from_header, sender_name, sender_email)

    def test_utf8b64_encoding(self):
        from_header = '=?utf-8?B?w6l4YW1wbGUgdXNlcg==?= <user@example.com>'
        sender_name = u'\xe9xample user'
        sender_email = 'user@example.com'
        self._test_encoding(from_header, sender_name, sender_email)


class SenderCorrelationTest(TestCase):
    """Validate correct behavior of the find_author case.

    Relies of checking the internal state of a Django model object.

    http://stackoverflow.com/a/19379636/613428
    """

    @staticmethod
    def _create_email(from_header):
        mail = 'Message-Id: %s\n' % make_msgid() + \
               'From: %s\n' % from_header + \
               'Subject: Tests\n\n'\
               'test\n'
        return message_from_string(mail)

    def test_non_existing_sender(self):
        sender = 'Non-existing Sender <nonexisting@example.com>'
        mail = self._create_email(sender)

        # don't create the person - attempt to find immediately
        person = find_author(mail)
        self.assertEqual(person._state.adding, True)
        self.assertEqual(person.id, None)

    def test_existing_sender(self):
        sender = 'Existing Sender <existing@example.com>'
        mail = self._create_email(sender)

        # create the person first
        person_a = find_author(mail)
        person_a.save()

        # then attempt to parse email with the same 'From' line
        person_b = find_author(mail)
        self.assertEqual(person_b._state.adding, False)
        self.assertEqual(person_b.id, person_a.id)

    def test_existing_different_format(self):
        sender = 'Existing Sender <existing@example.com>'
        mail = self._create_email(sender)

        # create the person first
        person_a = find_author(mail)
        person_a.save()

        # then attempt to parse email with a new 'From' line
        mail = self._create_email('existing@example.com')
        person_b = find_author(mail)
        self.assertEqual(person_b._state.adding, False)
        self.assertEqual(person_b.id, person_a.id)

    def test_existing_different_case(self):
        sender = 'Existing Sender <existing@example.com>'
        mail = self._create_email(sender)

        person_a = find_author(mail)
        person_a.save()

        mail = self._create_email(sender.upper())
        person_b = find_author(mail)
        self.assertEqual(person_b._state.adding, False)
        self.assertEqual(person_b.id, person_a.id)


class SubjectEncodingTest(TestCase):
    """Validate correct handling of encoded subjects."""

    @staticmethod
    def _create_email(subject):
        mail = 'Message-Id: %s\n' % make_msgid() + \
               'From: example user <user@example.com>\n' + \
               'Subject: %s\n\n' % subject + \
               'test\n\n' + SAMPLE_DIFF
        return message_from_string(mail)

    def _test_encoding(self, subject_header, parsed_subject):
        email = self._create_email(subject_header)
        name, _ = clean_subject(email.get('Subject'))
        self.assertEqual(name, parsed_subject)

    def test_subject_ascii_encoding(self):
        subject_header = 'test subject'
        subject = 'test subject'
        self._test_encoding(subject_header, subject)

    def test_subject_utf8qp_encoding(self):
        subject_header = '=?utf-8?q?test=20s=c3=bcbject?='
        subject = u'test s\xfcbject'
        self._test_encoding(subject_header, subject)

    def test_subject_utf8qp_multiple_encoding(self):
        subject_header = 'test =?utf-8?q?s=c3=bcbject?='
        subject = u'test s\xfcbject'
        self._test_encoding(subject_header, subject)


class MultipleProjectPatchTest(TestCase):
    """Test that patches sent to multiple patchwork projects are
       handled correctly."""

    orig_content = 'Test Comment'
    patch_filename = '0001-add-line.patch'
    msgid = '<1@example.com>'

    def setUp(self):
        self.p1 = create_project()
        self.p2 = create_project()

        patch = read_patch(self.patch_filename)
        email = create_email(
            content=''.join([self.orig_content, '\n', patch]),
            msgid=self.msgid,
            listid='<%s>' % self.p1.listid)
        parse_mail(email)

        del email['List-ID']
        email['List-ID'] = '<%s>' % self.p2.listid
        parse_mail(email)

    def test_parsed_projects(self):
        self.assertEqual(Patch.objects.filter(project=self.p1).count(), 1)
        self.assertEqual(Patch.objects.filter(project=self.p2).count(), 1)


class MultipleProjectPatchCommentTest(MultipleProjectPatchTest):
    """Test that followups to multiple-project patches end up on the
       correct patch."""

    comment_msgid = '<2@example.com>'
    comment_content = 'test comment'

    def setUp(self):
        super(MultipleProjectPatchCommentTest, self).setUp()

        for project in [self.p1, self.p2]:
            email = create_email(
                content=self.comment_content,
                msgid=self.comment_msgid,
                listid='<%s>' % project.listid)
            email['In-Reply-To'] = self.msgid
            parse_mail(email)

    def test_parsed_comment(self):
        for project in [self.p1, self.p2]:
            patch = Patch.objects.filter(project=project)[0]
            # we should see the reply comment only
            self.assertEqual(
                Comment.objects.filter(submission=patch).count(), 1)


class ListIdHeaderTest(TestCase):
    """Test that we parse List-Id headers from mails correctly."""

    def setUp(self):
        self.project = create_project()

    def test_no_list_id(self):
        email = MIMEText('')
        project = find_project_by_header(email)
        self.assertEqual(project, None)

    def test_blank_list_id(self):
        email = MIMEText('')
        email['List-Id'] = ''
        project = find_project_by_header(email)
        self.assertEqual(project, None)

    def test_whitespace_list_id(self):
        email = MIMEText('')
        email['List-Id'] = ' '
        project = find_project_by_header(email)
        self.assertEqual(project, None)

    def test_substring_list_id(self):
        email = MIMEText('')
        email['List-Id'] = 'example.com'
        project = find_project_by_header(email)
        self.assertEqual(project, None)

    def test_short_list_id(self):
        """Some mailing lists have List-Id headers in short formats, where it
           is only the list ID itself (without enclosing angle-brackets). """
        email = MIMEText('')
        email['List-Id'] = self.project.listid
        project = find_project_by_header(email)
        self.assertEqual(project, self.project)

    def test_long_list_id(self):
        email = MIMEText('')
        email['List-Id'] = 'Test text <%s>' % self.project.listid
        project = find_project_by_header(email)
        self.assertEqual(project, self.project)


class PatchParseTest(PatchTest):
    """Test parsing of different patch formats."""

    def _test_pull_request_parse(self, mbox_filename):
        diff, message = self._find_content(mbox_filename)
        pull_url = parse_pull_request(message)
        self.assertTrue(diff is None)
        self.assertTrue(message is not None)
        self.assertTrue(pull_url is not None)

    def test_git_pull_request(self):
        self._test_pull_request_parse('0001-git-pull-request.mbox')

    def test_git_pull_wrapped_request(self):
        self._test_pull_request_parse('0002-git-pull-request-wrapped.mbox')

    def test_git_pull_git_ssh_url(self):
        self._test_pull_request_parse('0004-git-pull-request-git+ssh.mbox')

    def test_git_pull_ssh_url(self):
        self._test_pull_request_parse('0005-git-pull-request-ssh.mbox')

    def test_git_pull_http_url(self):
        self._test_pull_request_parse('0006-git-pull-request-http.mbox')

    def test_git_pull_with_diff(self):
        diff, message = self._find_content(
            '0003-git-pull-request-with-diff.mbox')
        pull_url = parse_pull_request(message)
        self.assertEqual(
            'git://git.kernel.org/pub/scm/linux/kernel/git/tip/'
            'linux-2.6-tip.git x86-fixes-for-linus',
            pull_url)
        self.assertTrue(
            diff.startswith('diff --git a/arch/x86/include/asm/smp.h'),
            diff)

    def test_git_rename(self):
        diff, _ = self._find_content('0008-git-rename.mbox')
        self.assertTrue(diff is not None)
        self.assertEqual(diff.count("\nrename from "), 2)
        self.assertEqual(diff.count("\nrename to "), 2)

    def test_git_rename_with_diff(self):
        diff, message = self._find_content(
            '0009-git-rename-with-diff.mbox')
        self.assertTrue(diff is not None)
        self.assertTrue(message is not None)
        self.assertEqual(diff.count("\nrename from "), 2)
        self.assertEqual(diff.count("\nrename to "), 2)
        self.assertEqual(diff.count('\n-a\n+b'), 1)

    def test_cvs_format(self):
        diff, message = self._find_content('0007-cvs-format-diff.mbox')
        self.assertTrue(diff.startswith('Index'))

    def test_invalid_charset(self):
        """Validate behavior with an invalid charset name.

        Ensure that we can parse with one of the fallback encodings.
        """
        diff, message = self._find_content('0010-invalid-charset.mbox')
        self.assertTrue(diff is not None)
        self.assertTrue(message is not None)

    def test_no_newline(self):
        """Validate behavior when trailing newline is absent."""
        diff, message = self._find_content(
            '0011-no-newline-at-end-of-file.mbox')
        self.assertTrue(diff is not None)
        self.assertTrue(message is not None)
        self.assertTrue(diff.startswith(
            'diff --git a/tools/testing/selftests/powerpc/Makefile'))
        # Confirm the trailing no newline marker doesn't end up in the comment
        self.assertFalse(message.rstrip().endswith(
            '\ No newline at end of file'))
        # Confirm it's instead at the bottom of the patch
        self.assertTrue(diff.rstrip().endswith(
            '\ No newline at end of file'))
        # Confirm we got both markers
        self.assertEqual(2, diff.count('\ No newline at end of file'))


class HeaderTest(TestCase):
    def test_header_preservation(self):
        """Verify that header refactoring doesn't interfere with parsing."""
        project = create_project()
        mail = read_mail('0001-git-pull-request.mbox')
        parse_mail(mail, list_id=project.listid)
        headers = """Return-Path: <linuxppc-dev-bounces+jk=ozlabs.org@lists.ozlabs.org>
X-Spam-Checker-Version: SpamAssassin 3.3.1 (2010-03-16) on bilbo.ozlabs.org
X-Spam-Level: 
X-Spam-Status: No, score=0.0 required=3.0 tests=none autolearn=disabled
	version=3.3.1
X-Original-To: jk@ozlabs.org
Delivered-To: jk@ozlabs.org
Received: from bilbo.ozlabs.org (localhost [127.0.0.1])
	by ozlabs.org (Postfix) with ESMTP id ED4B3100937
	for <jk@ozlabs.org>; Fri, 22 Oct 2010 14:51:54 +1100 (EST)
Received: by ozlabs.org (Postfix)
	id BF799B70CB; Fri, 22 Oct 2010 14:51:50 +1100 (EST)
Delivered-To: linuxppc-dev@ozlabs.org
Received: from gate.crashing.org (gate.crashing.org [63.228.1.57])
	(using TLSv1 with cipher DHE-RSA-AES256-SHA (256/256 bits))
	(Client did not present a certificate)
	by ozlabs.org (Postfix) with ESMTPS id 94629B7043
	for <linuxppc-dev@ozlabs.org>; Fri, 22 Oct 2010 14:51:49 +1100 (EST)
Received: from [IPv6:::1] (localhost.localdomain [127.0.0.1])
	by gate.crashing.org (8.14.1/8.13.8) with ESMTP id o9M3p3SP018234;
	Thu, 21 Oct 2010 22:51:04 -0500
Subject: [git pull] Please pull powerpc.git next branch
From: Benjamin Herrenschmidt <benh@kernel.crashing.org>
To: Linus Torvalds <torvalds@linux-foundation.org>
Date: Fri, 22 Oct 2010 14:51:02 +1100
Message-ID: <1287719462.2198.37.camel@pasglop>
Mime-Version: 1.0
X-Mailer: Evolution 2.30.3 
"""
        # Ergh.
        #
        # The original mail used a single space for the continuation
        # line of Cc:. Python2 normalises this to \t (we specify that
        # as the whitespace continuation character.) Python3 does not
        # normalise it.
        #
        # It doesn't seem to have any semantic meaning, and it's not
        # clear what the 'correct' behaviour is. But the change does
        # cause the tests to fail.
        #
        # We don't want to rewrite chunks of the email module to get
        # things to be consistent. So just special case it...
        if six.PY3:
            headers += """Cc: linuxppc-dev list <linuxppc-dev@ozlabs.org>,
 Andrew Morton <akpm@linux-foundation.org>,
 Linux Kernel list <linux-kernel@vger.kernel.org>
"""
        else:
            headers += """Cc: linuxppc-dev list <linuxppc-dev@ozlabs.org>,
	Andrew Morton <akpm@linux-foundation.org>,
	Linux Kernel list <linux-kernel@vger.kernel.org>
"""

        headers += """X-BeenThere: linuxppc-dev@lists.ozlabs.org
X-Mailman-Version: 2.1.13
Precedence: list
List-Id: Linux on PowerPC Developers Mail List <cbe-oss-dev.ozlabs.org>
List-Unsubscribe: <https://lists.ozlabs.org/options/linuxppc-dev>,
	<mailto:linuxppc-dev-request@lists.ozlabs.org?subject=unsubscribe>
List-Archive: <http://lists.ozlabs.org/pipermail/linuxppc-dev>
List-Post: <mailto:linuxppc-dev@lists.ozlabs.org>
List-Help: <mailto:linuxppc-dev-request@lists.ozlabs.org?subject=help>
List-Subscribe: <https://lists.ozlabs.org/listinfo/linuxppc-dev>,
	<mailto:linuxppc-dev-request@lists.ozlabs.org?subject=subscribe>
Content-Type: text/plain;
  charset="us-ascii"
Content-Transfer-Encoding: 7bit
Sender: linuxppc-dev-bounces+jk=ozlabs.org@lists.ozlabs.org
Errors-To: linuxppc-dev-bounces+jk=ozlabs.org@lists.ozlabs.org
X-UID: 11446
X-Length: 16781
Status: R
X-Status: N
X-KMail-EncryptionState: 
X-KMail-SignatureState: 
X-KMail-MDN-Sent: 
"""
        # We also strip the newlines: it doesn't really matter if we
        # end with a trailing newline or not. (It means we can have a
        # slightly simpler parser!)
        self.assertEqual(Patch.objects.first().headers.strip('\n'),
                         headers.strip('\n'))


class DelegateRequestTest(TestCase):

    patch_filename = '0001-add-line.patch'
    msgid = '<1@example.com>'
    invalid_delegate_email = "nobody"

    def setUp(self):
        self.patch = read_patch(self.patch_filename)
        self.user = create_user()
        self.project = create_project()

    def _get_email(self):
        email = create_email(self.patch)
        del email['List-ID']
        email['List-ID'] = '<' + self.project.listid + '>'
        email['Message-Id'] = self.msgid
        return email

    def assertDelegate(self, delegate):  # noqa
        query = Patch.objects.filter(project=self.project)
        self.assertEqual(query.count(), 1)
        self.assertEqual(query[0].delegate, delegate)

    def test_delegate(self):
        email = self._get_email()
        email['X-Patchwork-Delegate'] = self.user.email
        parse_mail(email)
        self.assertDelegate(self.user)

    def test_no_delegate(self):
        email = self._get_email()
        parse_mail(email)
        self.assertDelegate(None)

    def test_invalid_delegate(self):
        email = self._get_email()
        email['X-Patchwork-Delegate'] = self.invalid_delegate_email
        parse_mail(email)
        self.assertDelegate(None)


class InitialPatchStateTest(TestCase):

    patch_filename = '0001-add-line.patch'
    msgid = '<1@example.com>'
    invalid_state_name = "Nonexistent Test State"

    def setUp(self):
        self.default_state = create_state()
        self.nondefault_state = create_state()

        self.patch = read_patch(self.patch_filename)
        self.user = create_user()
        self.project = create_project()

    def _get_email(self):
        email = create_email(
            self.patch, msgid=self.msgid, listid='<%s>' % self.project.listid)
        return email

    def assertState(self, state):  # noqa
        query = Patch.objects.filter(project=self.project)
        self.assertEqual(query.count(), 1)
        self.assertEqual(query[0].state, state)

    def test_non_default_state(self):
        self.assertNotEqual(self.default_state, self.nondefault_state)

    def test_explicit_non_default_state_request(self):
        email = self._get_email()
        email['X-Patchwork-State'] = self.nondefault_state.name
        parse_mail(email)
        self.assertState(self.nondefault_state)

    def test_explicit_default_state_request(self):
        email = self._get_email()
        email['X-Patchwork-State'] = self.default_state.name
        parse_mail(email)
        self.assertState(self.default_state)

    def test_implicit_default_state_request(self):
        email = self._get_email()
        parse_mail(email)
        self.assertState(self.default_state)

    def test_invalid_state(self):
        # make sure it's actually invalid
        with self.assertRaises(State.DoesNotExist):
            State.objects.get(name=self.invalid_state_name)

        email = self._get_email()
        email['X-Patchwork-State'] = self.invalid_state_name
        parse_mail(email)
        self.assertState(self.default_state)


class ParseInitialTagsTest(PatchTest):

    fixtures = ['default_tags']
    patch_filename = '0001-add-line.patch'
    orig_content = ('test comment\n\n' +
                    'Tested-by: Test User <test@example.com>\n' +
                    'Reviewed-by: Test User <test@example.com>\n')

    def setUp(self):
        project = create_project(listid='test.example.com')
        self.orig_diff = read_patch(self.patch_filename)
        email = create_email(self.orig_content + '\n' + self.orig_diff,
                             listid=project.listid)
        parse_mail(email)

    def test_tags(self):
        self.assertEqual(Patch.objects.count(), 1)
        patch = Patch.objects.all()[0]
        self.assertEqual(patch.patchtag_set.filter(
            tag__name='Acked-by').count(), 0)
        self.assertEqual(patch.patchtag_set.get(
            tag__name='Reviewed-by').count, 1)
        self.assertEqual(patch.patchtag_set.get(
            tag__name='Tested-by').count, 1)


class PrefixTest(TestCase):

    def test_split_prefixes(self):
        self.assertEqual(split_prefixes('PATCH'), ['PATCH'])
        self.assertEqual(split_prefixes('PATCH,RFC'), ['PATCH', 'RFC'])
        self.assertEqual(split_prefixes(''), [])
        self.assertEqual(split_prefixes('PATCH,'), ['PATCH'])
        self.assertEqual(split_prefixes('PATCH '), ['PATCH'])
        self.assertEqual(split_prefixes('PATCH,RFC'), ['PATCH', 'RFC'])
        self.assertEqual(split_prefixes('PATCH 1/2'), ['PATCH', '1/2'])

    def test_series_markers(self):
        self.assertEqual(parse_series_marker([]), (None, None))
        self.assertEqual(parse_series_marker(['bar']), (None, None))
        self.assertEqual(parse_series_marker(['bar', '1/2']), (1, 2))
        self.assertEqual(parse_series_marker(['bar', '0/12']), (0, 12))


class SubjectTest(TestCase):

    def test_clean_subject(self):
        self.assertEqual(clean_subject('meep'), ('meep', []))
        self.assertEqual(clean_subject('Re: meep'), ('meep', []))
        self.assertEqual(clean_subject('[PATCH] meep'), ('meep', []))
        self.assertEqual(clean_subject("[PATCH] meep \n meep"),
                         ('meep meep', []))
        self.assertEqual(clean_subject('[PATCH RFC] meep'),
                         ('[RFC] meep', ['RFC']))
        self.assertEqual(clean_subject('[PATCH,RFC] meep'),
                         ('[RFC] meep', ['RFC']))
        self.assertEqual(clean_subject('[PATCH,1/2] meep'),
                         ('[1/2] meep', ['1/2']))
        self.assertEqual(clean_subject('[PATCH RFC 1/2] meep'),
                         ('[RFC,1/2] meep', ['RFC', '1/2']))
        self.assertEqual(clean_subject('[PATCH] [RFC] meep'),
                         ('[RFC] meep', ['RFC']))
        self.assertEqual(clean_subject('[PATCH] [RFC,1/2] meep'),
                         ('[RFC,1/2] meep', ['RFC', '1/2']))
        self.assertEqual(clean_subject('[PATCH] [RFC] [1/2] meep'),
                         ('[RFC,1/2] meep', ['RFC', '1/2']))
        self.assertEqual(clean_subject('[PATCH] rewrite [a-z] regexes'),
                         ('rewrite [a-z] regexes', []))
        self.assertEqual(clean_subject('[PATCH] [RFC] rewrite [a-z] regexes'),
                         ('[RFC] rewrite [a-z] regexes', ['RFC']))
        self.assertEqual(clean_subject('[foo] [bar] meep', ['foo']),
                         ('[bar] meep', ['bar']))
        self.assertEqual(clean_subject('[FOO] [bar] meep', ['foo']),
                         ('[bar] meep', ['bar']))

    def test_subject_check(self):
        self.assertIsNotNone(subject_check('RE: meep'))
        self.assertIsNotNone(subject_check('Re: meep'))
        self.assertIsNotNone(subject_check('re: meep'))
        self.assertIsNotNone(subject_check('RE meep'))
        self.assertIsNotNone(subject_check('Re meep'))
        self.assertIsNotNone(subject_check('re meep'))
