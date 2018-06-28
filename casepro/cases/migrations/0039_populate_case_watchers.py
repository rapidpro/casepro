# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from django.db import migrations, models


def populate_case_watchers(apps, schema_editor):
    Case = apps.get_model("cases", "Case")

    cases = Case.objects.all()

    for case in cases:
        # get all users who have sent replies in this case
        repliers = {o.created_by for o in case.outgoing_messages.all()}

        # get all users who have acted on this case in a way that would now make them a watcher
        actors = {a.created_by for a in case.actions.filter(action__in=("O", "R", "N"))}

        watchers = repliers.union(actors)

        for user in watchers:
            case.watchers.add(user)

    if cases:
        print("Populated watchers for %d cases" % len(cases))


class Migration(migrations.Migration):

    dependencies = [("cases", "0038_case_watchers"), ("msgs", "0049_remove_label_tests")]

    operations = [migrations.RunPython(populate_case_watchers)]
