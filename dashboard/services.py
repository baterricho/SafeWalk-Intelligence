from collections import Counter

from django.contrib.auth.models import User
from django.db.models import Count
from django.utils import timezone

from accounts.models import UserProfile
from reports.models import SafetyReport
from reports.services import generate_area_clusters, time_bucket


def dashboard_summary():
    reports = SafetyReport.objects.all()
    active_reports = reports.exclude(status__in=[SafetyReport.Status.REJECTED, SafetyReport.Status.RESOLVED])
    clusters = generate_area_clusters()
    common_issue = reports.values("category").annotate(total=Count("id")).order_by("-total").first()

    time_counts = Counter(time_bucket(report.time_observed) for report in reports)
    most_dangerous_time = time_counts.most_common(1)[0][0] if time_counts else "No data"

    top_trusted = (
        UserProfile.objects.select_related("user")
        .filter(role__in=[UserProfile.ROLE_TRUSTED, UserProfile.ROLE_ADMIN])
        .order_by("-trust_score")[:5]
    )

    improving_areas = []
    worsening_areas = []
    for cluster in clusters:
        area_reports = reports.filter(location_name__icontains=cluster["location_name"]).order_by("created_at")
        if area_reports.count() >= 2:
            first_score = area_reports.first().safety_score
            last_score = area_reports.last().safety_score
            if last_score - first_score >= 8:
                improving_areas.append(cluster["location_name"])
            elif first_score - last_score >= 8:
                worsening_areas.append(cluster["location_name"])

    return {
        "total_reports": reports.count(),
        "active_critical_reports": active_reports.filter(risk_level=SafetyReport.RiskLevel.CRITICAL).count(),
        "verified_reports": reports.filter(status=SafetyReport.Status.VERIFIED).count(),
        "resolved_reports": reports.filter(status=SafetyReport.Status.RESOLVED).count(),
        "most_reported_area": clusters[0]["location_name"] if clusters else "No reports yet",
        "most_common_issue": dict(SafetyReport.Category.choices).get(common_issue["category"], "No data") if common_issue else "No data",
        "highest_risk_time_of_day": most_dangerous_time,
        "areas_improving": improving_areas[:5],
        "areas_getting_worse": worsening_areas[:5],
        "top_trusted_reporters": [
            {"username": profile.user.username, "trust_score": profile.trust_score, "role": profile.role}
            for profile in top_trusted
        ],
        "generated_at": timezone.now(),
    }
