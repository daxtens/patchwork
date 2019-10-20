# Patchwork - automated patch tracking system
# Copyright (C) 2019, Bayerische Motoren Werke Aktiengesellschaft (BMW AG)
#
# SPDX-License-Identifier: GPL-2.0-or-later

from django.db.models import Count
from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView
from rest_framework.generics import RetrieveUpdateDestroyAPIView
from rest_framework.serializers import ModelSerializer

from patchwork.models import SubmissionRelation


class MaintainerPermission(permissions.BasePermission):

    def has_object_permission(self, request, view, submissions):
        if request.method in permissions.SAFE_METHODS:
            return True

        user = request.user
        if not user.is_authenticated:
            return False

        if isinstance(submissions, SubmissionRelation):
            submissions = list(submissions.submissions.all())
        maintaining = user.profile.maintainer_projects.all()
        return all(s.project in maintaining for s in submissions)

    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or \
               (request.user.is_authenticated and
                request.user.profile.maintainer_projects.count() > 0)


class SubmissionRelationSerializer(ModelSerializer):
    class Meta:
        model = SubmissionRelation
        fields = ('id', 'url', 'submissions',)
        read_only_fields = ('url',)
        extra_kwargs = {
            'url': {'view_name': 'api-relation-detail'},
        }


class SubmissionRelationMixin:
    serializer_class = SubmissionRelationSerializer
    permission_classes = (MaintainerPermission,)

    def get_queryset(self):
        return SubmissionRelation.objects.all() \
            .prefetch_related('submissions')


class SubmissionRelationList(SubmissionRelationMixin, ListCreateAPIView):
    ordering = 'id'
    ordering_fields = ['id', 'submission_count']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submissions = serializer.validated_data['submissions']
        self.check_object_permissions(request, submissions)
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset() \
            .annotate(submission_count=Count('submission'))


class SubmissionRelationDetail(SubmissionRelationMixin,
                               RetrieveUpdateDestroyAPIView):
    pass
