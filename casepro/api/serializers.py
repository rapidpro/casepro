from rest_framework import serializers

from casepro.cases.models import Case

class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = ('summary', 'opened_on', 'closed_on')
