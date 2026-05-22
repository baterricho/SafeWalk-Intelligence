from rest_framework import serializers

from .models import RouteNote, SavedRoute


class RouteNoteSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = RouteNote
        fields = [
            "id",
            "user",
            "user_display",
            "location_name",
            "latitude",
            "longitude",
            "note",
            "safety_tip_type",
            "created_at",
        ]
        read_only_fields = ["user", "created_at"]

    def validate_location_name(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError("Location name must be at least 3 characters long.")
        return value

    def validate_note(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Note must be at least 10 characters long.")
        if len(value) > 1000:
            raise serializers.ValidationError("Note must be 1,000 characters or fewer.")
        return value

    def validate(self, attrs):
        latitude = attrs.get("latitude", getattr(self.instance, "latitude", None))
        longitude = attrs.get("longitude", getattr(self.instance, "longitude", None))
        if latitude is None or not (-90 <= float(latitude) <= 90):
            raise serializers.ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if longitude is None or not (-180 <= float(longitude) <= 180):
            raise serializers.ValidationError({"longitude": "Longitude must be between -180 and 180."})
        return attrs


class SavedRouteSerializer(serializers.ModelSerializer):
    user_display = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = SavedRoute
        fields = [
            "id",
            "user",
            "user_display",
            "route_name",
            "start_location",
            "end_location",
            "start_latitude",
            "start_longitude",
            "end_latitude",
            "end_longitude",
            "usual_time",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["user", "created_at", "updated_at"]

    def validate(self, attrs):
        for field in ["route_name", "start_location", "end_location"]:
            value = attrs.get(field, getattr(self.instance, field, "")).strip()
            if len(value) < 3:
                raise serializers.ValidationError({field: "This field must be at least 3 characters long."})
            attrs[field] = value
        coordinate_fields = ["start_latitude", "start_longitude", "end_latitude", "end_longitude"]
        missing = [field for field in coordinate_fields if attrs.get(field, getattr(self.instance, field, None)) is None]
        if missing:
            raise serializers.ValidationError("Start and end points must be pinned on the map.")
        return attrs
