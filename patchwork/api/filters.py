# Patchwork - automated patch tracking system
# Copyright (C) 2017 Stephen Finucane <stephen@that.guru>
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q
from django_filters.rest_framework import FilterSet
from django_filters import IsoDateTimeFilter
from django_filters import ModelMultipleChoiceFilter
from django.forms import ModelMultipleChoiceField as BaseMultipleChoiceField
from django.forms.widgets import MultipleHiddenInput

from patchwork.compat import NAME_FIELD
from patchwork.models import Bundle
from patchwork.models import Check
from patchwork.models import Event
from patchwork.models import Patch
from patchwork.models import Person
from patchwork.models import Project
from patchwork.models import Series
from patchwork.models import State
from patchwork.models import Submission


# custom fields, filters

class ModelMultipleChoiceField(BaseMultipleChoiceField):

    def _get_filter(self, value):
        if not self.alternate_lookup:
            return 'pk', value

        try:
            return 'pk', int(value)
        except ValueError:
            return self.alternate_lookup, value

    def _check_values(self, value):
        """
        Given a list of possible PK values, returns a QuerySet of the
        corresponding objects. Raises a ValidationError if a given value is
        invalid (not a valid PK, not in the queryset, etc.)
        """
        # deduplicate given values to avoid creating many querysets or
        # requiring the database backend deduplicate efficiently.
        try:
            value = frozenset(value)
        except TypeError:
            # list of lists isn't hashable, for example
            raise ValidationError(
                self.error_messages['list'],
                code='list',
            )

        q_objects = Q()

        for pk in value:
            key, val = self._get_filter(pk)

            try:
                # NOTE(stephenfin): In contrast to the Django implementation
                # of this, we check to ensure each specified key exists and
                # fail if not. If we don't this, we can end up doing nothing
                # for the filtering which, to me, seems very confusing
                self.queryset.get(**{key: val})
            except (ValueError, TypeError, self.queryset.model.DoesNotExist):
                raise ValidationError(
                    self.error_messages['invalid_pk_value'],
                    code='invalid_pk_value',
                    params={'pk': val},
                )

            q_objects |= Q(**{key: val})

        qs = self.queryset.filter(q_objects)

        return qs


class BaseField(ModelMultipleChoiceField):

    alternate_lookup = None


class BaseFilter(ModelMultipleChoiceFilter):

    field_class = BaseField


class PersonChoiceField(ModelMultipleChoiceField):

    alternate_lookup = 'email__iexact'


class PersonFilter(ModelMultipleChoiceFilter):

    field_class = PersonChoiceField


class ProjectChoiceField(ModelMultipleChoiceField):

    alternate_lookup = 'linkname__iexact'


class ProjectFilter(ModelMultipleChoiceFilter):

    field_class = ProjectChoiceField


class StateChoiceField(ModelMultipleChoiceField):

    def _get_filter(self, value):
        try:
            return 'pk', int(value)
        except ValueError:
            return 'name__iexact', ' '.join(value.split('-'))


class StateFilter(ModelMultipleChoiceFilter):

    field_class = StateChoiceField


class UserChoiceField(ModelMultipleChoiceField):

    alternate_lookup = 'username__iexact'


class UserFilter(ModelMultipleChoiceFilter):

    field_class = UserChoiceField


# filter sets

class TimestampMixin(FilterSet):

    # TODO(stephenfin): These should filter on a 'updated_at' field instead
    before = IsoDateTimeFilter(lookup_expr='lt', **{NAME_FIELD: 'date'})
    since = IsoDateTimeFilter(lookup_expr='gte', **{NAME_FIELD: 'date'})


class SeriesFilterSet(TimestampMixin, FilterSet):

    submitter = PersonFilter(queryset=Person.objects.all())
    project = ProjectFilter(queryset=Project.objects.all())

    class Meta:
        model = Series
        fields = ('submitter', 'project')


class CoverLetterFilterSet(TimestampMixin, FilterSet):

    project = ProjectFilter(queryset=Project.objects.all())
    # NOTE(stephenfin): We disable the select-based HTML widgets for these
    # filters as the resulting query is _huge_
    series = BaseFilter(queryset=Project.objects.all(),
                        widget=MultipleHiddenInput)
    submitter = PersonFilter(queryset=Person.objects.all())

    @property
    def qs(self):
        parent = super(CoverLetterFilterSet, self).qs
        return parent.filter(diff__isnull=True, pull_url__isnull=True)

    class Meta:
        model = Submission
        fields = ('project', 'series', 'submitter')


class PatchFilterSet(TimestampMixin, FilterSet):

    project = ProjectFilter(queryset=Project.objects.all())
    # NOTE(stephenfin): We disable the select-based HTML widgets for these
    # filters as the resulting query is _huge_
    series = BaseFilter(queryset=Series.objects.all(),
                        widget=MultipleHiddenInput)
    submitter = PersonFilter(queryset=Person.objects.all())
    delegate = UserFilter(queryset=User.objects.all())
    state = StateFilter(queryset=State.objects.all())

    class Meta:
        model = Submission # TODO MIGRATE - exclude covers
        fields = ('project', 'series', 'submitter', 'delegate',
                  'state', 'archived')


class CheckFilterSet(TimestampMixin, FilterSet):

    user = UserFilter(queryset=User.objects.all())

    class Meta:
        model = Check
        fields = ('user', 'state', 'context')

def get_coverletter_qs(request):
    return Submission.cover_objects.all()

class EventFilterSet(TimestampMixin, FilterSet):

    # NOTE(stephenfin): We disable the select-based HTML widgets for these
    # filters as the resulting query is _huge_
    # TODO(stephenfin): We should really use an AJAX widget of some form here
    project = ProjectFilter(queryset=Project.objects.all(),
                            widget=MultipleHiddenInput)
    series = BaseFilter(queryset=Series.objects.all(),
                        widget=MultipleHiddenInput)
    patch = BaseFilter(queryset=Submission.patch_objects.all(),
                       widget=MultipleHiddenInput)
    cover = BaseFilter(queryset=get_coverletter_qs,
                       widget=MultipleHiddenInput)

    class Meta:
        model = Event
        fields = ('project', 'category', 'series', 'patch', 'cover')


class BundleFilterSet(FilterSet):

    project = ProjectFilter(queryset=Project.objects.all())
    owner = UserFilter(queryset=User.objects.all())

    class Meta:
        model = Bundle
        fields = ('project', 'owner', 'public')
