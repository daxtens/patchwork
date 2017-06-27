# Patchwork - automated patch tracking system
# Copyright (C) 2016 Stephen Finucane <stephen@that.guru>
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

import email
import logging

from django.core.management import base
from django.utils import six

from patchwork.models import Person
from patchwork.models import Patch
from patchwork.models import Series
from patchwork.models import CoverLetter
from patchwork.models import Comment
from patchwork.models import SeriesReference
from patchwork.parser import parse_mail
from patchwork.parser import BrokenEmailException

import afl
afl.init()

logger = logging.getLogger(__name__)


class Command(base.BaseCommand):
    help = 'Parse an mbox file and store any patch/comment found.'

    def add_arguments(self, parser):
        parser.add_argument(
            'infile',
            nargs=1,
            type=str,
            help='input mbox file')
        parser.add_argument(
            '--list-id',
            help='mailing list ID. If not supplied, this will be '
            'extracted from the mail headers.')

    def cleanup(self):
        Series.objects.all().delete()
        SeriesReference.objects.all().delete()
        Patch.objects.all().delete()
        Comment.objects.all().delete()
        CoverLetter.objects.all().delete()
        Person.objects.all().delete()

    def handle(self, *args, **options):
        infile = options['infile'][0]

        logger.info('Parsing mail loaded by filename')
        try:
            if six.PY3:
                with open(infile, 'rb') as file_:
                    mail = email.message_from_binary_file(file_)
            else:
                with open(infile) as file_:
                    mail = email.message_from_file(file_)
        except AttributeError:
            logger.warning("Broken email ignored")
            return

        try:
            parse_mail(mail, options['list_id'])
            self.cleanup()
        except BrokenEmailException:
            logger.warning("Broken email ignored")
            self.cleanup()
        except Exception as E:
            logger.exception('Error when parsing incoming email',
                             extra={'mail': mail.as_string()})
            self.cleanup()
            raise E
