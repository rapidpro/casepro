from casepro.utils import parse_csv

from .models import ContainsTest, GroupsTest, Quantifier, WordCountTest


class RuleFormMixin(object):
    def derive_initial(self):
        initial = super(RuleFormMixin, self).derive_initial()

        if self.object:
            tests_by_type = {t.TYPE: t for t in self.object.get_tests()}
            contains_test = tests_by_type.get("contains")
            groups_test = tests_by_type.get("groups")
            field_test = tests_by_type.get("field")
            words_test = tests_by_type.get("words")

            if contains_test:
                initial["keywords"] = ", ".join(contains_test.keywords)
            if groups_test:
                initial["groups"] = groups_test.groups
            if field_test:
                initial["field_test"] = field_test
            if words_test:
                initial["ignore_single_words"] = True

        return initial

    def construct_tests(self):
        """
        Constructs tests from form field values
        """
        data = self.form.cleaned_data

        keywords = parse_csv(data["keywords"])
        groups = data["groups"]
        field_test = data["field_test"]
        ignore_single_words = data["ignore_single_words"]

        tests = []
        if keywords:
            tests.append(ContainsTest(keywords, Quantifier.ANY))
        if groups:
            tests.append(GroupsTest(groups, Quantifier.ANY))
        if field_test:
            tests.append(field_test)
        if ignore_single_words:
            tests.append(WordCountTest(2))

        return tests
