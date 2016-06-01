from __future__ import unicode_literals

from django.db import transaction
from django.utils.decorators import method_decorator


class NonAtomicMixin(object):
    """
    Mixin to configure a view to be handled without a transaction
    """
    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, request, *args, **kwargs):
        return super(NonAtomicMixin, self).dispatch(request, *args, **kwargs)
