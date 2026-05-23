from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class RouteNote(models.Model):
    class SafetyTipType(models.TextChoices):
        BETTER_LIGHTING = "better_lighting", "Better Lighting"
        MORE_PEOPLE = "more_people", "More People"
        CCTV_NEARBY = "cctv_nearby", "CCTV Nearby"
        AVOID_AT_NIGHT = "avoid_at_night", "Avoid at Night"
        SAFER_ALTERNATIVE = "safer_alternative_path", "Safer Alternative Path"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="route_notes")
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
    note = models.TextField(max_length=1000)
    safety_tip_type = models.CharField(max_length=40, choices=SafetyTipType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.location_name} - {self.get_safety_tip_type_display()}"


class SavedRoute(models.Model):
    class RouteType(models.TextChoices):
        SHORTCUT_LANE = "shortcut_lane", "Shortcut Lane"
        MAIN_ROAD = "main_road", "Main Road"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_routes")
    route_name = models.CharField(max_length=120)
    start_location = models.CharField(max_length=160)
    end_location = models.CharField(max_length=160)
    start_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    start_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    end_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-90")), MaxValueValidator(Decimal("90"))],
    )
    end_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("-180")), MaxValueValidator(Decimal("180"))],
    )
    usual_time = models.TimeField()
    notes = models.TextField(max_length=1000, blank=True)
    selected_route_type = models.CharField(max_length=32, choices=RouteType.choices, default=RouteType.MAIN_ROAD)
    route_geometry = models.JSONField(null=True, blank=True)
    route_distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    route_duration_min = models.PositiveIntegerField(null=True, blank=True)
    shortcut_geometry = models.JSONField(null=True, blank=True)
    shortcut_distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    shortcut_duration_min = models.PositiveIntegerField(null=True, blank=True)
    main_road_geometry = models.JSONField(null=True, blank=True)
    main_road_distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    main_road_duration_min = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["route_name"]

    def __str__(self):
        return f"{self.route_name}: {self.start_location} to {self.end_location}"
