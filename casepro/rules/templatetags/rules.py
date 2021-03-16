from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from casepro.rules.models import (
    ArchiveAction,
    ContainsTest,
    FieldTest,
    FlagAction,
    GroupsTest,
    LabelAction,
    WordCountTest,
)

register = template.Library()


def _render_contains_test(test):
    if len(test.keywords) > 1:
        contains = f"{str(test.quantifier)} " + ", ".join([f'<i>"{escape(w)}"</i>' for w in test.keywords])
    else:
        contains = f'<i>"{escape(test.keywords[0])}"</i>'
    return f"message contains {contains}"


def _render_groups_test(test):
    if len(test.groups) > 1:
        membership = f"{str(test.quantifier)} " + ", ".join([f"<i>{escape(g)}</i>" for g in test.groups])
    else:
        membership = f"<i>{escape(test.groups[0])}</i>"

    return f"contact belongs to {membership}"


def _render_field_test(test):
    return f"contact <i>{escape(test.key)}</i> is equal to <i>{escape(test.values[0])}</i>"


def _render_word_count_test(test):
    return f"message has at least {test.minimum} words"


def _render_label_action(action):
    return f'apply label <span class="label label-success">{escape(action.label)}</span>'


def _render_flag_action(action):
    return "flag message"


def _render_archive_action(action):
    return "archive message"


TEST_RENDERERS = {
    ContainsTest: _render_contains_test,
    GroupsTest: _render_groups_test,
    FieldTest: _render_field_test,
    WordCountTest: _render_word_count_test,
}

ACTION_RENDERERS = {
    LabelAction: _render_label_action,
    FlagAction: _render_flag_action,
    ArchiveAction: _render_archive_action,
}


@register.filter
def render_tests(rule):
    rendered_tests = []
    for test in rule.get_tests():
        renderer = TEST_RENDERERS[type(test)]
        rendered_tests.append(renderer(test))

    return mark_safe(_(", and ").join(rendered_tests))


@register.filter
def render_actions(rule):
    rendered_actions = []
    for action in rule.get_actions():
        renderer = ACTION_RENDERERS[type(action)]
        rendered_actions.append(renderer(action))

    return mark_safe(_(", and ").join(rendered_actions))
