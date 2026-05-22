from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import redirect, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import user_is_admin
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
        reports = visible_reports_for_user(request.user).filter(
            Q(location_name__icontains=saved_route.start_location)
            | Q(location_name__icontains=saved_route.end_location)
            | Q(description__icontains=saved_route.start_location)
            | Q(description__icontains=saved_route.end_location)
        )
        if all([saved_route.start_latitude, saved_route.start_longitude, saved_route.end_latitude, saved_route.end_longitude]):
            nearby_ids = []
            for report in visible_reports_for_user(request.user)[:250]:
                start_distance = distance_km(saved_route.start_latitude, saved_route.start_longitude, report.latitude, report.longitude)
                end_distance = distance_km(saved_route.end_latitude, saved_route.end_longitude, report.latitude, report.longitude)
                if min(start_distance, end_distance) <= 0.75:
                    nearby_ids.append(report.id)
            reports = visible_reports_for_user(request.user).filter(Q(id__in=nearby_ids) | Q(id__in=reports.values("id")))[:20]
        else:
            reports = reports[:20]
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
