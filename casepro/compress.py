from __future__ import unicode_literals

from compressor.filters.base import CompilerFilter
from compressor.filters.css_default import CssAbsoluteFilter


class LessFilter(CompilerFilter):
    """
    See https://stackoverflow.com/questions/10423159/django-compressor-using-lessc-in-debug-mode/14842293
    """
    def __init__(self, content, attrs, **kwargs):
        super(LessFilter, self).__init__(content, command='lessc {infile} {outfile}', **kwargs)

    def input(self, **kwargs):
        content = super(LessFilter, self).input(**kwargs)
        return CssAbsoluteFilter(content).input(**kwargs)