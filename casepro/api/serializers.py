import pytz

from rest_framework import serializers

from casepro.cases.models import Case, CaseAction, Partner


def label_ref(l):
    return {"id": l.id, "name": l.name}


def partner_ref(p):
    return {"id": p.id, "name": p.name}


def contact_ref(c):
    return {"id": c.id, "uuid": str(c.uuid)}


def case_ref(c):
    return {"id": c.id, "summary": c.summary}


class CaseSerializer(serializers.ModelSerializer):
    labels = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    contact = serializers.SerializerMethodField()
    opened_on = serializers.DateTimeField(default_timezone=pytz.UTC)
    closed_on = serializers.DateTimeField(default_timezone=pytz.UTC)

    def get_labels(self, obj):
        return [label_ref(l) for l in obj.labels.all()]

    def get_assignee(self, obj):
        return partner_ref(obj.assignee)

    def get_contact(self, obj):
        return contact_ref(obj.contact)

    class Meta:
        model = Case
        fields = ("id", "summary", "labels", "assignee", "contact", "opened_on", "closed_on")


class CaseActionSerializer(serializers.ModelSerializer):
    TYPES = {
        CaseAction.OPEN: "open",
        CaseAction.ADD_NOTE: "add_note",
        CaseAction.REASSIGN: "reassign",
        CaseAction.LABEL: "label",
        CaseAction.UNLABEL: "unlabel",
        CaseAction.CLOSE: "close",
        CaseAction.REOPEN: "reopen",
    }

    case = serializers.SerializerMethodField()
    type = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    label = serializers.SerializerMethodField()
    created_on = serializers.DateTimeField(default_timezone=pytz.UTC)

    def get_case(self, obj):
        return case_ref(obj.case)

    def get_type(self, obj):
        return self.TYPES[obj.action]

    def get_assignee(self, obj):
        return partner_ref(obj.assignee) if obj.assignee else None

    def get_label(self, obj):
        return label_ref(obj.label) if obj.label else None

    class Meta:
        model = CaseAction
        fields = ("id", "case", "type", "assignee", "note", "label", "created_on")


class PartnerSerializer(serializers.ModelSerializer):
    labels = serializers.SerializerMethodField()

    def get_labels(self, obj):
        return [label_ref(l) for l in obj.labels.all()]

    class Meta:
        model = Partner
        fields = ("id", "name", "description", "labels")
