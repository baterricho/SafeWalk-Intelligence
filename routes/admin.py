from django.contrib import admin

from .models import RouteNote, SavedRoute


@admin.register(RouteNote)
class RouteNoteAdmin(admin.ModelAdmin):
    list_display = ["user", "location_name", "safety_tip_type", "latitude", "longitude", "created_at"]
    list_filter = ["safety_tip_type", "created_at"]
    search_fields = ["location_name", "note", "user__username"]
    readonly_fields = ["created_at"]


@admin.register(SavedRoute)
class SavedRouteAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "route_name",
        "start_location",
        "end_location",
        "usual_time",
        "start_latitude",
        "start_longitude",
        "end_latitude",
        "end_longitude",
        "selected_route_type",
        "route_distance_km",
        "route_duration_min",
        "created_at",
    ]
    list_filter = ["created_at", "updated_at"]
    search_fields = ["route_name", "start_location", "end_location", "user__username"]
    readonly_fields = ["created_at", "updated_at"]
