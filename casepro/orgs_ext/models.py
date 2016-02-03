from __future__ import unicode_literals

import json

from dash.orgs.models import Org
from django.db import models
from django.utils import timezone


class OrgTaskState(models.Model):
    """
    Holds org specific state for a scheduled org task
    """
    org = models.ForeignKey(Org, related_name='task_states')

    task_key = models.CharField(max_length=32)

    started_on = models.DateTimeField(null=True)

    ended_on = models.DateTimeField(null=True)

    results = models.TextField(null=True)

    is_failing = models.BooleanField(default=False)

    @classmethod
    def get_or_create(cls, org, task_key):
        existing = cls.objects.filter(org=org, task_key=task_key).first()
        if existing:
            return existing

        return cls.objects.create(org=org, task_key=task_key)

    @classmethod
    def get_failing(cls):
        return cls.objects.filter(org__is_active=True, is_failing=True)

    def is_running(self):
        return self.started_on and not self.ended_on

    def has_ever_run(self):
        return self.started_on is not None

    def get_last_results(self):
        return json.loads(self.results) if self.results else None

    def get_time_taken(self):
        until = self.ended_on if self.ended_on else timezone.now()
        return (until - self.started_on).total_seconds()

    class Meta:
        unique_together = ('org', 'task_key')
