import math
import re
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import UserProfile
from .models import ReportConfirmation, SafetyReport


RISK_WEIGHTS = {
    SafetyReport.RiskLevel.LOW: 12,
    SafetyReport.RiskLevel.MEDIUM: 30,
    SafetyReport.RiskLevel.HIGH: 52,
    SafetyReport.RiskLevel.CRITICAL: 72,
}


def clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, value))


def normalize_text(value):
    value = (value or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def token_set(*values):
    stop_words = {"the", "near", "at", "in", "on", "a", "an", "and", "to", "of", "road", "street"}
    tokens = set()
    for value in values:
        tokens.update(word for word in normalize_text(value).split() if len(word) > 2 and word not in stop_words)
    return tokens


def distance_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def calculate_report_decay(report):
    age_days = max((timezone.now() - report.created_at).days, 0) if report.created_at else 0
    decay = max(0.25, 1 - (age_days / 120))

    recent_cutoff = timezone.now() - timedelta(days=14)
    recent_confirmations = report.confirmations.filter(
        created_at__gte=recent_cutoff,
        confirmation_type__in=[
            ReportConfirmation.ConfirmationType.CONFIRMED,
            ReportConfirmation.ConfirmationType.NEEDS_REVIEW,
        ],
    ).count()
    decay += min(0.25, recent_confirmations * 0.05)

    if report.status in [SafetyReport.Status.RESOLVED, SafetyReport.Status.REJECTED]:
        decay *= 0.35

    return round(min(decay, 1.0), 2)


def calculate_evidence_score(report):
    score = 10
    if len((report.description or "").strip()) >= 40:
        score += 20
    if report.photo:
        score += 20

    confirmations = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED).count()
    resolved_votes = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.RESOLVED).count()
    disputes = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.DISPUTED).count()

    score += min(25, confirmations * 7)
    score += min(8, resolved_votes * 2)
    score -= min(25, disputes * 8)

    if report.status == SafetyReport.Status.VERIFIED:
        score += 30
    elif report.status == SafetyReport.Status.REJECTED:
        score -= 30

    score = int(clamp(score))
    if report.status == SafetyReport.Status.VERIFIED:
        label = SafetyReport.CredibilityLabel.ADMIN_VERIFIED
    elif score >= 75:
        label = SafetyReport.CredibilityLabel.STRONG_EVIDENCE
    elif confirmations >= 2:
        label = SafetyReport.CredibilityLabel.COMMUNITY_SUPPORTED
    else:
        label = SafetyReport.CredibilityLabel.UNVERIFIED

    return {"score": score, "label": label}


def calculate_safety_score(report):
    decay = calculate_report_decay(report)
    evidence = calculate_evidence_score(report)["score"]
    confirmations = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED).count()
    disputes = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.DISPUTED).count()
    resolved_votes = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.RESOLVED).count()
    needs_review = report.confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.NEEDS_REVIEW).count()

    related_reports = SafetyReport.objects.filter(
        status__in=[SafetyReport.Status.PENDING, SafetyReport.Status.VERIFIED, SafetyReport.Status.IN_PROGRESS, SafetyReport.Status.NEEDS_REVIEW],
        category=report.category,
    ).exclude(pk=report.pk)
    nearby_count = 0
    for related in related_reports[:200]:
        if normalize_text(related.location_name) == normalize_text(report.location_name):
            nearby_count += 1
        elif distance_km(report.latitude, report.longitude, related.latitude, related.longitude) <= 0.35:
            nearby_count += 1

    penalty = RISK_WEIGHTS.get(report.risk_level, 30)
    penalty += min(15, nearby_count * 4)
    penalty += min(20, confirmations * 5)
    penalty += min(10, needs_review * 3)
    penalty -= min(18, disputes * 6)
    penalty -= min(18, resolved_votes * 6)

    if report.status == SafetyReport.Status.VERIFIED:
        penalty += 12
    elif report.status == SafetyReport.Status.NEEDS_REVIEW:
        penalty += 6
    elif report.status == SafetyReport.Status.IN_PROGRESS:
        penalty -= 8
    elif report.status == SafetyReport.Status.RESOLVED:
        penalty -= 35
    elif report.status == SafetyReport.Status.REJECTED:
        penalty -= 55

    if report.lighting_condition == SafetyReport.LightingCondition.NO_LIGHT:
        penalty += 14
    elif report.lighting_condition == SafetyReport.LightingCondition.DIM:
        penalty += 8
    elif report.lighting_condition == SafetyReport.LightingCondition.BRIGHT:
        penalty -= 7

    if report.crowd_level == SafetyReport.CrowdLevel.EMPTY:
        penalty += 10
    elif report.crowd_level == SafetyReport.CrowdLevel.FEW:
        penalty += 6
    elif report.crowd_level == SafetyReport.CrowdLevel.CROWDED:
        penalty -= 7

    hour = report.time_observed.hour if report.time_observed else 12
    if hour >= 18 or hour < 5:
        penalty += 11
    elif 5 <= hour < 11:
        penalty -= 5

    trust_score = getattr(getattr(report.user, "profile", None), "trust_score", 50) if report.user else 50
    penalty += ((trust_score - 50) / 50) * 9
    penalty += ((evidence - 50) / 50) * 8

    decayed_penalty = max(0, penalty) * decay
    score = 100 - decayed_penalty
    return int(round(clamp(score)))


def refresh_report_intelligence(report, save=True):
    evidence = calculate_evidence_score(report)
    report.evidence_score = evidence["score"]
    report.credibility_label = evidence["label"]
    report.safety_score = calculate_safety_score(report)
    if save:
        SafetyReport.objects.filter(pk=report.pk).update(
            evidence_score=report.evidence_score,
            credibility_label=report.credibility_label,
            safety_score=report.safety_score,
            updated_at=timezone.now(),
        )
    return report


def detect_duplicate_report(report_data):
    category = report_data.get("category")
    location_name = report_data.get("location_name", "")
    title = report_data.get("title", "")
    description = report_data.get("description", "")
    latitude = report_data.get("latitude")
    longitude = report_data.get("longitude")
    candidate_tokens = token_set(title, description, location_name)

    candidates = SafetyReport.objects.filter(
        category=category,
        status__in=[SafetyReport.Status.PENDING, SafetyReport.Status.VERIFIED, SafetyReport.Status.IN_PROGRESS, SafetyReport.Status.NEEDS_REVIEW],
    ).select_related("user")[:250]

    duplicates = []
    for report in candidates:
        score = 0
        same_location = normalize_text(report.location_name) == normalize_text(location_name)
        if same_location:
            score += 35

        try:
            distance = distance_km(latitude, longitude, report.latitude, report.longitude)
            if distance <= 0.15:
                score += 35
            elif distance <= 0.35:
                score += 20
        except (TypeError, ValueError):
            distance = None

        existing_tokens = token_set(report.title, report.description, report.location_name)
        overlap = len(candidate_tokens & existing_tokens)
        if overlap >= 4:
            score += 25
        elif overlap >= 2:
            score += 12

        if score >= 45:
            duplicates.append(
                {
                    "id": report.id,
                    "title": report.title,
                    "location_name": report.location_name,
                    "risk_level": report.risk_level,
                    "status": report.status,
                    "safety_score": report.safety_score,
                    "distance_km": round(distance, 3) if distance is not None else None,
                    "similarity_score": score,
                }
            )

    return sorted(duplicates, key=lambda item: item["similarity_score"], reverse=True)[:5]


def update_user_trust_score(user, action):
    if not user or not user.is_authenticated:
        return None

    profile, _ = UserProfile.objects.get_or_create(user=user)
    deltas = {
        "verified_report": 10,
        "resolved_report": 5,
        "community_confirmed": 2,
        "admin_adjust_up": 5,
        "rejected_report": -15,
        "false_report": -20,
        "admin_adjust_down": -5,
    }
    profile.trust_score = clamp(profile.trust_score + deltas.get(action, 0))
    profile.save()
    return profile


def suggest_admin_status(report):
    counts = report.confirmations.values("confirmation_type").annotate(total=Count("id"))
    counter = {item["confirmation_type"]: item["total"] for item in counts}
    confirmed = counter.get(ReportConfirmation.ConfirmationType.CONFIRMED, 0)
    disputed = counter.get(ReportConfirmation.ConfirmationType.DISPUTED, 0)
    resolved = counter.get(ReportConfirmation.ConfirmationType.RESOLVED, 0)
    needs_review = counter.get(ReportConfirmation.ConfirmationType.NEEDS_REVIEW, 0)

    if resolved >= 3:
        return SafetyReport.Status.RESOLVED
    if disputed >= 3 or needs_review >= 2:
        return SafetyReport.Status.NEEDS_REVIEW
    if confirmed >= 3 and report.evidence_score >= 55:
        return SafetyReport.Status.VERIFIED
    if report.safety_score <= 30 and report.status == SafetyReport.Status.PENDING:
        return SafetyReport.Status.NEEDS_REVIEW
    return report.status


def highest_risk_level(reports):
    order = {
        SafetyReport.RiskLevel.LOW: 1,
        SafetyReport.RiskLevel.MEDIUM: 2,
        SafetyReport.RiskLevel.HIGH: 3,
        SafetyReport.RiskLevel.CRITICAL: 4,
    }
    return max((report.risk_level for report in reports), key=lambda risk: order.get(risk, 0), default=SafetyReport.RiskLevel.LOW)


def generate_area_clusters():
    active_reports = list(
        SafetyReport.objects.exclude(status__in=[SafetyReport.Status.REJECTED]).exclude(
            visibility_level=SafetyReport.VisibilityLevel.ADMIN_ONLY
        )
    )
    grouped = defaultdict(list)
    for report in active_reports:
        key = normalize_text(report.location_name) or f"{round(float(report.latitude), 3)},{round(float(report.longitude), 3)}"
        grouped[key].append(report)

    clusters = []
    for reports in grouped.values():
        categories = Counter(report.category for report in reports)
        avg_score = sum(report.safety_score for report in reports) / len(reports)
        location_name = Counter(report.location_name for report in reports).most_common(1)[0][0]
        clusters.append(
            {
                "location_name": location_name,
                "total_reports": len(reports),
                "highest_risk_level": highest_risk_level(reports),
                "most_common_category": categories.most_common(1)[0][0],
                "average_safety_score": round(avg_score, 1),
                "active_critical_reports": sum(
                    1
                    for report in reports
                    if report.risk_level == SafetyReport.RiskLevel.CRITICAL
                    and report.status not in [SafetyReport.Status.RESOLVED, SafetyReport.Status.REJECTED]
                ),
                "latitude": round(sum(float(report.latitude) for report in reports) / len(reports), 6),
                "longitude": round(sum(float(report.longitude) for report in reports) / len(reports), 6),
            }
        )

    return sorted(clusters, key=lambda item: (item["active_critical_reports"], item["total_reports"]), reverse=True)


def risk_label_from_score(score):
    if score <= 30:
        return "High Risk"
    if score <= 60:
        return "Medium Risk"
    if score <= 80:
        return "Low Risk"
    return "Safe"


def time_bucket(time_value):
    hour = time_value.hour if time_value else 12
    if 5 <= hour < 12:
        return "Morning"
    if 12 <= hour < 18:
        return "Afternoon"
    return "Night"


def generate_location_timeline(location_name):
    qs = SafetyReport.objects.filter(location_name__icontains=location_name).exclude(status=SafetyReport.Status.REJECTED)
    buckets = {
        "Morning": [],
        "Afternoon": [],
        "Night": [],
    }
    for report in qs:
        buckets[time_bucket(report.time_observed)].append(report.safety_score)

    timeline = []
    for bucket, scores in buckets.items():
        if scores:
            average_score = round(sum(scores) / len(scores), 1)
            risk = risk_label_from_score(average_score)
            total_reports = len(scores)
        else:
            average_score = None
            risk = "No Data"
            total_reports = 0
        timeline.append(
            {
                "time_period": bucket,
                "risk_label": risk,
                "average_safety_score": average_score,
                "total_reports": total_reports,
            }
        )
    return timeline


def generate_area_summary(location_name):
    qs = SafetyReport.objects.filter(location_name__icontains=location_name).exclude(status=SafetyReport.Status.REJECTED)
    total = qs.count()
    if total == 0:
        return {
            "location_name": location_name,
            "total_reports": 0,
            "average_safety_score": None,
            "highest_risk_level": None,
            "most_common_category": None,
            "active_critical_reports": 0,
            "timeline": generate_location_timeline(location_name),
        }
    reports = list(qs)
    categories = Counter(report.category for report in reports)
    return {
        "location_name": location_name,
        "total_reports": total,
        "average_safety_score": round(qs.aggregate(avg=Avg("safety_score"))["avg"], 1),
        "highest_risk_level": highest_risk_level(reports),
        "most_common_category": categories.most_common(1)[0][0],
        "active_critical_reports": qs.filter(risk_level=SafetyReport.RiskLevel.CRITICAL).exclude(
            status__in=[SafetyReport.Status.RESOLVED, SafetyReport.Status.REJECTED]
        ).count(),
        "confirmed_reports": qs.filter(confirmations__confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED)
        .distinct()
        .count(),
        "resolved_reports": qs.filter(status=SafetyReport.Status.RESOLVED).count(),
        "timeline": generate_location_timeline(location_name),
    }
