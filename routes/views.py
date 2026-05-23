import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import user_is_admin
from dashboard.weather_service import get_weather_data
from reports.models import SafetyReport
from reports.serializers import SafetyReportSerializer
from reports.services import distance_km
from reports.views import visible_reports_for_user
from .forms import RouteNoteForm, SavedRouteForm
from .models import RouteNote, SavedRoute
from .serializers import RouteNoteSerializer, SavedRouteSerializer


class IsRouteOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return user_is_admin(request.user) or obj.user == request.user


class RouteNoteViewSet(viewsets.ModelViewSet):
    serializer_class = RouteNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsRouteOwnerOrAdmin]

    def get_queryset(self):
        if user_is_admin(self.request.user):
            return RouteNote.objects.select_related("user")
        return RouteNote.objects.select_related("user").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SavedRouteViewSet(viewsets.ModelViewSet):
    serializer_class = SavedRouteSerializer
    permission_classes = [permissions.IsAuthenticated, IsRouteOwnerOrAdmin]

    def get_queryset(self):
        if user_is_admin(self.request.user):
            return SavedRoute.objects.select_related("user")
        return SavedRoute.objects.select_related("user").filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=["get"], url_path="nearby-reports")
    def nearby_reports(self, request, pk=None):
        saved_route = self.get_object()
        reports = nearby_reports_for_route(saved_route, request.user)
        return Response(SafetyReportSerializer(reports, many=True, context={"request": request}).data)


@login_required
def my_routes_page(request):
    form = SavedRouteForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            route = form.save(commit=False)
            route.user = request.user
            route.save()
            messages.success(request, "Saved route added.")
            return redirect("my_routes")
        messages.error(request, "Please fix the route details and try again.")
    return render(request, "routes/my_routes.html", {"form": form, "routes": SavedRoute.objects.filter(user=request.user)})


def route_has_coordinates(route):
    return all(
        value is not None
        for value in [route.start_latitude, route.start_longitude, route.end_latitude, route.end_longitude]
    )


def point_to_route_distance_km(route, report):
    start_lat = float(route.start_latitude)
    start_lng = float(route.start_longitude)
    end_lat = float(route.end_latitude)
    end_lng = float(route.end_longitude)
    point_lat = float(report.latitude)
    point_lng = float(report.longitude)

    average_lat = math.radians((start_lat + end_lat + point_lat) / 3)
    lat_scale = 111.32
    lng_scale = 111.32 * math.cos(average_lat)

    sx, sy = start_lng * lng_scale, start_lat * lat_scale
    ex, ey = end_lng * lng_scale, end_lat * lat_scale
    px, py = point_lng * lng_scale, point_lat * lat_scale

    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return distance_km(start_lat, start_lng, point_lat, point_lng)

    t = max(0, min(1, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    nearest_x = sx + t * dx
    nearest_y = sy + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def point_to_segment_distance_km(start, end, point):
    start_lat, start_lng = map(float, start)
    end_lat, end_lng = map(float, end)
    point_lat, point_lng = map(float, point)

    average_lat = math.radians((start_lat + end_lat + point_lat) / 3)
    lat_scale = 111.32
    lng_scale = 111.32 * math.cos(average_lat)

    sx, sy = start_lng * lng_scale, start_lat * lat_scale
    ex, ey = end_lng * lng_scale, end_lat * lat_scale
    px, py = point_lng * lng_scale, point_lat * lat_scale

    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return distance_km(start_lat, start_lng, point_lat, point_lng)

    t = max(0, min(1, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    nearest_x = sx + t * dx
    nearest_y = sy + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def point_to_route_geometry_distance_km(route_geometry, report):
    if not isinstance(route_geometry, list) or len(route_geometry) < 2:
        return None

    report_point = [float(report.latitude), float(report.longitude)]
    distances = []
    for index in range(len(route_geometry) - 1):
        start = route_geometry[index]
        end = route_geometry[index + 1]
        if (
            isinstance(start, list)
            and isinstance(end, list)
            and len(start) == 2
            and len(end) == 2
        ):
            distances.append(point_to_segment_distance_km(start, end, report_point))
    return min(distances) if distances else None


def nearby_reports_for_route(saved_route, user, radius_km=1.0):
    reports = visible_reports_for_user(user).exclude(status=SafetyReport.Status.REJECTED)
    keyword_matches = reports.filter(
        Q(location_name__icontains=saved_route.start_location)
        | Q(location_name__icontains=saved_route.end_location)
        | Q(description__icontains=saved_route.start_location)
        | Q(description__icontains=saved_route.end_location)
    )

    if not route_has_coordinates(saved_route):
        return keyword_matches[:20]

    nearby_ids = []
    for report in reports[:500]:
        start_distance = distance_km(saved_route.start_latitude, saved_route.start_longitude, report.latitude, report.longitude)
        end_distance = distance_km(saved_route.end_latitude, saved_route.end_longitude, report.latitude, report.longitude)
        routed_distance = point_to_route_geometry_distance_km(saved_route.route_geometry, report)
        route_distance = routed_distance if routed_distance is not None else point_to_route_distance_km(saved_route, report)
        if min(start_distance, end_distance, route_distance) <= radius_km:
            nearby_ids.append(report.id)

    return reports.filter(Q(id__in=nearby_ids) | Q(id__in=keyword_matches.values("id"))).distinct()[:20]


@login_required
def saved_route_detail_page(request, pk):
    saved_route = get_object_or_404(SavedRoute, pk=pk, user=request.user)
    nearby_reports = nearby_reports_for_route(saved_route, request.user)
    weather = None
    if saved_route.start_latitude is not None and saved_route.start_longitude is not None:
        try:
            weather = get_weather_data(
                lat=float(saved_route.start_latitude),
                lon=float(saved_route.start_longitude),
                location_name=saved_route.start_location,
            )
        except Exception:
            weather = None
    return render(
        request,
        "routes/saved_route_detail.html",
        {
            "route": saved_route,
            "nearby_reports": nearby_reports,
            "weather": weather,
        },
    )


@login_required
def saved_route_delete_page(request, pk):
    saved_route = get_object_or_404(SavedRoute, pk=pk, user=request.user)
    if request.method == "POST":
        saved_route.delete()
        messages.info(request, "Saved route deleted.")
        return redirect("my_routes")
    return render(request, "routes/saved_route_confirm_delete.html", {"route": saved_route})


@login_required
def route_notes_page(request):
    form = RouteNoteForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, "Route note added.")
            return redirect("route_notes")
        messages.error(request, "Please fix the route note details and try again.")
    return render(
        request,
        "routes/route_notes.html",
        {"form": form, "notes": RouteNote.objects.filter(user=request.user), "tip_choices": RouteNote.SafetyTipType.choices},
    )
