from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def current_local_time():
    return timezone.localtime().time()


class SafetyReport(models.Model):
    class Category(models.TextChoices):
        DARK_AREA = "dark_area", "Dark Area"
        BROKEN_STREET_LIGHT = "broken_street_light", "Broken Street Light"
        FLOODED_ROAD = "flooded_road", "Flooded Road"
        STRAY_DOGS = "stray_dogs", "Stray Dogs"
        ACCIDENT_PRONE = "accident_prone_area", "Accident-Prone Area"
        SUSPICIOUS_ACTIVITY = "suspicious_activity", "Suspicious Activity"
        BROKEN_SIDEWALK = "broken_sidewalk", "Broken Sidewalk"
        UNSAFE_SHORTCUT = "unsafe_shortcut", "Unsafe Shortcut"
        HARASSMENT_CONCERN = "harassment_concern", "Harassment Concern"
        POOR_VISIBILITY = "poor_visibility", "Poor Visibility"
        NO_PEDESTRIAN_LANE = "no_pedestrian_lane", "No Pedestrian Lane"
        OTHER = "other", "Other"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        IN_PROGRESS = "in_progress", "In Progress"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    class LightingCondition(models.TextChoices):
        BRIGHT = "bright", "Bright"
        MODERATE = "moderate", "Moderate"
        DIM = "dim", "Dim"
        NO_LIGHT = "no_light", "No Light"

    class CrowdLevel(models.TextChoices):
        CROWDED = "crowded", "Crowded"
        MODERATE = "moderate", "Moderate"
        FEW = "few_people", "Few People"
        EMPTY = "empty", "Empty"

    class DayType(models.TextChoices):
        WEEKDAY = "weekday", "Weekday"
        WEEKEND = "weekend", "Weekend"

    class VisibilityLevel(models.TextChoices):
        PUBLIC = "public", "Public"
        ANONYMOUS_PUBLIC = "anonymous_public", "Anonymous Public"
        ADMIN_ONLY = "admin_only", "Admin Only"

    class CredibilityLabel(models.TextChoices):
        UNVERIFIED = "unverified", "Unverified"
        COMMUNITY_SUPPORTED = "community_supported", "Community Supported"
        STRONG_EVIDENCE = "strong_evidence", "Strong Evidence"
        ADMIN_VERIFIED = "admin_verified", "Admin Verified"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_reports",
    )
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=40, choices=Category.choices)
    description = models.TextField(max_length=2000)
    location_name = models.CharField(max_length=160)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    time_observed = models.TimeField(default=current_local_time)
    day_type = models.CharField(max_length=16, choices=DayType.choices, default=DayType.WEEKDAY)
    lighting_condition = models.CharField(
        max_length=20,
        choices=LightingCondition.choices,
        default=LightingCondition.MODERATE,
    )
    crowd_level = models.CharField(max_length=20, choices=CrowdLevel.choices, default=CrowdLevel.MODERATE)
    is_anonymous = models.BooleanField(default=False)
    visibility_level = models.CharField(
        max_length=24,
        choices=VisibilityLevel.choices,
        default=VisibilityLevel.PUBLIC,
    )
    photo = models.ImageField(upload_to="report_photos/", blank=True, null=True, max_length=500)
    safety_score = models.PositiveSmallIntegerField(
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    evidence_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    credibility_label = models.CharField(
        max_length=32,
        choices=CredibilityLabel.choices,
        default=CredibilityLabel.UNVERIFIED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["location_name"]),
            models.Index(fields=["category", "risk_level"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.title} - {self.location_name}"

    @property
    def score_label(self):
        if self.safety_score <= 30:
            return "Dangerous"
        if self.safety_score <= 60:
            return "Caution"
        if self.safety_score <= 80:
            return "Moderately Safe"
        return "Safe"

    @property
    def public_reporter_name(self):
        if self.is_anonymous or self.visibility_level == self.VisibilityLevel.ANONYMOUS_PUBLIC:
            return "Anonymous reporter"
        return self.user.username if self.user else "Unknown reporter"

    @property
    def confirmation_count(self):
        return self.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED).count()

    @property
    def dispute_count(self):
        return self.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.DISPUTED).count()

    @property
    def resolved_count(self):
        return self.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.RESOLVED).count()

    @property
    def comment_count(self):
        return self.confirmations.exclude(comment__exact="").count()


class ReportConfirmation(models.Model):
    class ConfirmationType(models.TextChoices):
        COMMENT = "comment", "Comment"
        CONFIRMED = "confirmed", "Confirmed"
        DISPUTED = "disputed", "Disputed"
        RESOLVED = "resolved_by_community", "Resolved by Community"

    report = models.ForeignKey(SafetyReport, on_delete=models.CASCADE, related_name="confirmations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_confirmations")
    confirmation_type = models.CharField(max_length=32, choices=ConfirmationType.choices)
    comment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["report", "user"], name="unique_confirmation_per_user_report")
        ]

    def __str__(self):
        return f"{self.user} - {self.get_confirmation_type_display()} - {self.report}"

    @property
    def feedback_label(self):
        labels = {
            self.ConfirmationType.COMMENT: "Community update",
            self.ConfirmationType.CONFIRMED: "I also saw this",
            self.ConfirmationType.RESOLVED: "Marked as resolved",
            self.ConfirmationType.DISPUTED: "Reported as inaccurate",
        }
        return labels.get(self.confirmation_type, self.get_confirmation_type_display())


class ReportStatusHistory(models.Model):
    report = models.ForeignKey(SafetyReport, on_delete=models.CASCADE, related_name="status_history")
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_status_updates",
    )
    old_status = models.CharField(max_length=32, choices=SafetyReport.Status.choices)
    new_status = models.CharField(max_length=32, choices=SafetyReport.Status.choices)
    admin_note = models.CharField(max_length=700, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.report} changed from {self.old_status} to {self.new_status}"
