import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole, user_is_admin
from reports.models import ReportStatusHistory, SafetyReport
from reports.serializers import ReportStatusHistorySerializer, SafetyReportSerializer
from reports.services import generate_area_clusters, refresh_report_intelligence, update_user_trust_score
from reports.views import visible_reports_for_user
from notifications.weather import build_period_weather_cards
from notifications.services import notify_report_update
from .serializers import DashboardSummarySerializer
from .services import dashboard_summary
from .weather_service import get_weather_data


def serialize_report_for_dashboard(report):
    return {
        "id": report.id,
        "title": report.title,
        "description": report.description,
        "location_name": report.location_name,
        "latitude": float(report.latitude) if report.latitude is not None else 0.0,
        "longitude": float(report.longitude) if report.longitude is not None else 0.0,
        "category": report.category,
        "category_display": report.get_category_display(),
        "risk_level": report.risk_level,
        "risk_display": report.get_risk_level_display(),
        "status": report.status,
        "status_display": report.get_status_display(),
        "safety_score": report.safety_score,
        "score_label": report.score_label,
        "credibility_label": report.get_credibility_label_display(),
        "comment_count": report.comment_count,
        "confirmation_count": report.confirmation_count,
        "detail_url": f"/reports/{report.id}/",
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


def home_page(request):
    try:
        summary = dashboard_summary()
    except Exception:
        summary = {"total_reports": 0, "active_hazards": 0, "communities_active": 0, "safety_score_average": 70}
        
    try:
        clusters = generate_area_clusters()[:6]
    except Exception:
        clusters = []
        
    try:
        weather = get_weather_data()
    except Exception:
        from .weather_service import sample_weather_data
        weather = sample_weather_data()
        
    return render(
        request,
        "home.html",
        {
            "summary": summary,
            "clusters": clusters,
            "weather": weather,
            "weather_today": weather.get("weather_today", weather.get("current", {})),
            "daily_forecast": weather.get("daily_forecast", weather.get("forecast", [])),
        },
    )


def weather_api(request):
    try:
        lat = float(request.GET.get("lat", 9.7786))
        lon = float(request.GET.get("lon", 118.7353))
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid coordinates."}, status=400)

    location_name = request.GET.get("location") or None
    return JsonResponse(get_weather_data(lat=lat, lon=lon, location_name=location_name))


@login_required
@ensure_csrf_cookie
def user_dashboard_page(request):
    reports = visible_reports_for_user(request.user).exclude(status=SafetyReport.Status.REJECTED)[:300]
    report_data = [serialize_report_for_dashboard(report) for report in reports]
    user_reports = SafetyReport.objects.filter(user=request.user)
    
    # Get weather for the user's location if provided, else default
    lat = request.GET.get("lat")
    lng = request.GET.get("lng")
    
    try:
        if lat and lng:
            weather = get_weather_data(lat=float(lat), lon=float(lng))
        else:
            weather = get_weather_data()
    except (ValueError, TypeError):
        weather = get_weather_data()
    
    context = {
        "summary": dashboard_summary(),
        "reports": reports,
        "reports_json": json.dumps(report_data),
        "category_choices": SafetyReport.Category.choices,
        "risk_choices": SafetyReport.RiskLevel.choices,
        "status_choices": SafetyReport.Status.choices,
        "user_report_count": user_reports.count(),
        "user_average_score": round(sum(r.safety_score for r in user_reports) / user_reports.count(), 1)
        if user_reports.exists()
        else None,
        "clusters": generate_area_clusters()[:8],
        "weather": weather,
        "weather_today": weather.get("weather_today", weather.get("current", {})),
        "daily_forecast": weather.get("daily_forecast", weather.get("forecast", [])),
        "weather_period_cards": build_period_weather_cards(weather),
    }
    return render(request, "dashboard.html", context)


@login_required
def dashboard_reports_api(request):
    reports = visible_reports_for_user(request.user).exclude(status=SafetyReport.Status.REJECTED)[:300]
    user_reports = SafetyReport.objects.filter(user=request.user)
    return JsonResponse(
        {
            "reports": [serialize_report_for_dashboard(report) for report in reports],
            "summary": dashboard_summary(),
            "user_report_count": user_reports.count(),
        }
    )


def admin_required(user):
    return user_is_admin(user)


@user_passes_test(admin_required, login_url="login")
@ensure_csrf_cookie
def admin_dashboard_page(request):
    reports = SafetyReport.objects.select_related("user", "user__profile").prefetch_related("confirmations")[:300]
    context = {
        "summary": dashboard_summary(),
        "reports": reports,
        "status_choices": SafetyReport.Status.choices,
        "category_choices": SafetyReport.Category.choices,
        "risk_choices": SafetyReport.RiskLevel.choices,
    }
    return render(request, "dashboard/admin_dashboard.html", context)


@user_passes_test(admin_required, login_url="login")
@ensure_csrf_cookie
def admin_reports_page(request):
    reports = SafetyReport.objects.select_related("user", "user__profile").prefetch_related("confirmations")
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    risk_level = request.GET.get("risk_level", "")
    status_value = request.GET.get("status", "")
    if query:
        reports = reports.filter(Q(title__icontains=query) | Q(description__icontains=query) | Q(location_name__icontains=query))
    if category:
        reports = reports.filter(category=category)
    if risk_level:
        reports = reports.filter(risk_level=risk_level)
    if status_value:
        reports = reports.filter(status=status_value)
    return render(
        request,
        "dashboard/admin_reports.html",
        {
            "reports": reports,
            "status_choices": SafetyReport.Status.choices,
            "category_choices": SafetyReport.Category.choices,
            "risk_choices": SafetyReport.RiskLevel.choices,
            "filters": {"q": query, "category": category, "risk_level": risk_level, "status": status_value},
        },
    )


class AdminDashboardAPIView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        serializer = DashboardSummarySerializer(dashboard_summary())
        return Response(serializer.data)


class AdminReportsAPIView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        reports = SafetyReport.objects.select_related("user", "user__profile").prefetch_related("confirmations")
        serializer = SafetyReportSerializer(reports, many=True, context={"request": request})
        return Response(serializer.data)


class AdminReportStatusAPIView(APIView):
    permission_classes = [IsAdminRole]

    def patch(self, request, pk):
        report = get_object_or_404(SafetyReport, pk=pk)
        new_status = request.data.get("status")
        admin_note = request.data.get("admin_note", "")
        valid_statuses = dict(SafetyReport.Status.choices)
        if new_status not in valid_statuses:
            return Response({"status": "Invalid status value."}, status=status.HTTP_400_BAD_REQUEST)

        old_status = report.status
        if old_status != new_status:
            report.status = new_status
            report.save(update_fields=["status", "updated_at"])
            ReportStatusHistory.objects.create(
                report=report,
                admin=request.user,
                old_status=old_status,
                new_status=new_status,
                admin_note=admin_note[:700],
            )
            if new_status == SafetyReport.Status.VERIFIED:
                update_user_trust_score(report.user, "verified_report")
            elif new_status == SafetyReport.Status.REJECTED:
                update_user_trust_score(report.user, "rejected_report")
            elif new_status == SafetyReport.Status.RESOLVED:
                update_user_trust_score(report.user, "resolved_report")
            refresh_report_intelligence(report)
            notify_report_update(report, request.user, f"Status changed to {report.get_status_display()}.")

        return Response(
            {
                "id": report.id,
                "status": report.status,
                "status_display": report.get_status_display(),
                "safety_score": report.safety_score,
                "credibility_label": report.get_credibility_label_display(),
            }
        )


class AdminReportHistoryAPIView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, pk):
        report = get_object_or_404(SafetyReport, pk=pk)
        serializer = ReportStatusHistorySerializer(report.status_history.select_related("admin"), many=True)
        return Response(serializer.data)


class AdminReportDeleteAPIView(APIView):
    permission_classes = [IsAdminRole]

    def delete(self, request, pk):
        report = get_object_or_404(SafetyReport, pk=pk)
        report.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
