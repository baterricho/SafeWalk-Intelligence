from rest_framework import serializers

from accounts.permissions import user_is_admin
from .forms import ALLOWED_PHOTO_TYPES, MAX_PHOTO_SIZE
from .models import ReportConfirmation, ReportStatusHistory, SafetyReport
from .services import calculate_report_decay, suggest_admin_status


class SafetyReportSerializer(serializers.ModelSerializer):
    reporter_name = serializers.SerializerMethodField()
    reporter_username = serializers.SerializerMethodField()
    score_label = serializers.CharField(read_only=True)
    confirmations_count = serializers.SerializerMethodField()
    disputes_count = serializers.SerializerMethodField()
    resolved_confirmations_count = serializers.SerializerMethodField()
    needs_review_count = serializers.SerializerMethodField()
    confirmation_count = serializers.SerializerMethodField()
    dispute_count = serializers.SerializerMethodField()
    resolved_count = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    decay_factor = serializers.SerializerMethodField()
    suggested_status = serializers.SerializerMethodField()

    class Meta:
        model = SafetyReport
        fields = [
            "id",
            "user",
            "reporter_name",
            "reporter_username",
            "title",
            "category",
            "description",
            "location_name",
            "latitude",
            "longitude",
            "risk_level",
            "status",
            "time_observed",
            "day_type",
            "lighting_condition",
            "crowd_level",
            "is_anonymous",
            "visibility_level",
            "photo",
            "safety_score",
            "score_label",
            "evidence_score",
            "credibility_label",
            "confirmations_count",
            "disputes_count",
            "resolved_confirmations_count",
            "confirmation_count",
            "dispute_count",
            "resolved_count",
            "needs_review_count",
            "comment_count",
            "decay_factor",
            "suggested_status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "user",
            "status",
            "safety_score",
            "evidence_score",
            "credibility_label",
            "created_at",
            "updated_at",
        ]

    def get_reporter_name(self, obj):
        request = self.context.get("request")
        if request and user_is_admin(request.user):
            return obj.user.username if obj.user else "Unknown reporter"
        return obj.public_reporter_name

    def get_reporter_username(self, obj):
        request = self.context.get("request")
        if obj.user and request and user_is_admin(request.user):
            return obj.user.username
        if obj.is_anonymous or obj.visibility_level == SafetyReport.VisibilityLevel.ANONYMOUS_PUBLIC:
            return None
        return obj.user.username if obj.user else None

    def get_confirmations_count(self, obj):
        return obj.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED).count()

    def get_confirmation_count(self, obj):
        return self.get_confirmations_count(obj)

    def get_disputes_count(self, obj):
        return obj.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.DISPUTED).count()

    def get_dispute_count(self, obj):
        return self.get_disputes_count(obj)

    def get_resolved_confirmations_count(self, obj):
        return obj.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.RESOLVED).count()

    def get_resolved_count(self, obj):
        return self.get_resolved_confirmations_count(obj)

    def get_needs_review_count(self, obj):
        return obj.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.NEEDS_REVIEW).count()

    def get_comment_count(self, obj):
        return obj.confirmations.exclude(comment__exact="").count()

    def get_decay_factor(self, obj):
        return calculate_report_decay(obj)

    def get_suggested_status(self, obj):
        return suggest_admin_status(obj)

    def validate_title(self, value):
        value = value.strip()
        if len(value) < 6:
            raise serializers.ValidationError("Title must be at least 6 characters long.")
        if len(value) > 120:
            raise serializers.ValidationError("Title must be 120 characters or fewer.")
        return value

    def validate_description(self, value):
        value = value.strip()
        if len(value) < 20:
            raise serializers.ValidationError("Description must be at least 20 characters long.")
        if len(value) > 2000:
            raise serializers.ValidationError("Description must be 2,000 characters or fewer.")
        return value

    def validate_location_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Location details must be at least 3 characters long.")
        if len(value) > 160:
            raise serializers.ValidationError("Location details must be 160 characters or fewer.")
        return value

    def validate_photo(self, value):
        if not value:
            return value
        if getattr(value, "content_type", "") not in ALLOWED_PHOTO_TYPES:
            raise serializers.ValidationError("Upload a JPG, JPEG, PNG, or WEBP image.")
        if value.size > MAX_PHOTO_SIZE:
            raise serializers.ValidationError("Photo must be 5MB or smaller.")
        return value

    def validate(self, attrs):
        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if latitude is None or not (-90 <= float(latitude) <= 90):
            raise serializers.ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if longitude is None or not (-180 <= float(longitude) <= 180):
            raise serializers.ValidationError({"longitude": "Longitude must be between -180 and 180."})
        if attrs.get("is_anonymous") and attrs.get("visibility_level") == SafetyReport.VisibilityLevel.PUBLIC:
            attrs["visibility_level"] = SafetyReport.VisibilityLevel.ANONYMOUS_PUBLIC
        return attrs


class ReportConfirmationSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = ReportConfirmation
        fields = ["id", "report", "user", "user_display", "confirmation_type", "comment", "created_at"]
        read_only_fields = ["report", "user", "created_at"]

    def get_user_display(self, obj):
        return obj.user.username

    def validate_comment(self, value):
        if len(value) > 500:
            raise serializers.ValidationError("Comment must be 500 characters or fewer.")
        return value.strip()


class ReportStatusHistorySerializer(serializers.ModelSerializer):
    admin_username = serializers.CharField(source="admin.username", read_only=True)

    class Meta:
        model = ReportStatusHistory
        fields = ["id", "report", "admin", "admin_username", "old_status", "new_status", "admin_note", "created_at"]
        read_only_fields = ["report", "admin", "old_status", "new_status", "created_at"]


class AreaClusterSerializer(serializers.Serializer):
    location_name = serializers.CharField()
    total_reports = serializers.IntegerField()
    highest_risk_level = serializers.CharField()
    most_common_category = serializers.CharField()
    average_safety_score = serializers.FloatField()
    active_critical_reports = serializers.IntegerField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
