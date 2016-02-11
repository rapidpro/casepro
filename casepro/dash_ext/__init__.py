from __future__ import unicode_literals

"""
A holding pen for code that will be merged into Dash
"""

import itertools
import six


class MockClientQuery(six.Iterator):
    """
    Mock for APIv2 client get_xxxxx return values. Pass lists of temba objects to mock each fetch the client would make.

    For example:
        mock_get_contacts.return_value = MockClientQuery(
            [TembaContact.create(...), TembaContact.create(...), TembaContact.create(...)]
            [TembaContact.create(...)]
        )

    Will return the three contacts on the first call to iterfetches, and one on the second call.

    """
    def __init__(self, *fetches):
        self.fetches = list(fetches)

    def iterfetches(self, retry_on_rate_exceed=False):
        return self

    def all(self, retry_on_rate_exceed=False):
        return list(itertools.chain.from_iterable(self.fetches))

    def first(self, retry_on_rate_exceed=False):
        return self.fetches[0][0] if self.fetches[0] else None

    def __iter__(self):
        return self

    def __next__(self):
        if not self.fetches:
            raise StopIteration()

        return self.fetches.pop(0)
