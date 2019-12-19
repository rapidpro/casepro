from django import template
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from casepro.rules.models import ContainsTest, FieldTest, GroupsTest, WordCountTest

register = template.Library()


def render_contains_test(test):
    if len(test.keywords) > 1:
        contains = f"{str(test.quantifier)} " + ", ".join([f'<i>"{w}"</i>' for w in test.keywords])
    else:
        contains = f'<i>"{test.keywords[0]}"</i>'
    return f"message contains {contains}"


def render_groups_test(test):
    if len(test.groups) > 1:
        membership = f"{str(test.quantifier)} " + ", ".join([f"<i>{g}</i>" for g in test.groups])
    else:
        membership = f"<i>{test.groups[0]}</i>"

    return f"contact belongs to {membership}"


def render_field_test(test):
    return f"contact <i>{test.key}</i> is equal to <i>{test.values[0]}</i>"


def render_word_count_test(test):
    return f"message has at least {test.minimum} words"


TEST_RENDERERS = {
    ContainsTest: render_contains_test,
    GroupsTest: render_groups_test,
    FieldTest: render_field_test,
    WordCountTest: render_word_count_test,
}


@register.filter
def render_tests(rule):
    rendered_tests = []
    for test in rule.get_tests():
        renderer = TEST_RENDERERS[type(test)]
        rendered_tests.append(renderer(test))

    return mark_safe(_(", and ").join(rendered_tests))
