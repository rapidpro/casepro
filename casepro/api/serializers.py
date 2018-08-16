import pytz

from rest_framework import serializers

from casepro.cases.models import Case, Partner


class CaseSerializer(serializers.ModelSerializer):
    labels = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    opened_on = serializers.DateTimeField(default_timezone=pytz.UTC)
    closed_on = serializers.DateTimeField(default_timezone=pytz.UTC)

    def get_labels(self, obj):
        return [{"id": l.id, "name": l.name} for l in obj.labels.all()]

    def get_assignee(self, obj):
        return {"id": obj.assignee.id, "name": obj.assignee.name}

    def get_contact(self, obj):
        return {"id": obj.contact.id, "uuid": str(obj.contact.uuid)}

    class Meta:
        model = Case
        fields = ("id", "summary", "labels", "assignee", "contact", "opened_on", "closed_on")


class PartnerSerializer(serializers.ModelSerializer):
    labels = serializers.SerializerMethodField()

    def get_labels(self, obj):
        return [{"id": l.id, "name": l.name} for l in obj.labels.all()]

    class Meta:
        model = Partner
        fields = ("id", "name", "description", "labels")
