from datetime import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import UserProfile
from reports.models import ReportConfirmation, ReportStatusHistory, SafetyReport
from reports.services import refresh_report_intelligence
from routes.models import RouteNote, SavedRoute


class Command(BaseCommand):
    help = "Create sample SafeWalk users, reports, route notes, and confirmations."

    def handle(self, *args, **options):
        admin = self.create_user(
            username="admin",
            email="admin@safewalk.com",
            password="admin123",
            role=UserProfile.ROLE_ADMIN,
            trust_score=95,
            is_staff=True,
            is_superuser=True,
        )
        user = self.create_user(
            username="user",
            email="user@safewalk.com",
            password="user123",
            role=UserProfile.ROLE_USER,
            trust_score=50,
        )
        trusted = self.create_user(
            username="trusted",
            email="trusted@safewalk.com",
            password="trusted123",
            role=UserProfile.ROLE_TRUSTED,
            trust_score=88,
        )

        reports = [
            {
                "user": trusted,
                "title": "Dark road near school gate",
                "category": SafetyReport.Category.DARK_AREA,
                "description": "The road beside the school gate becomes very dark after evening classes and students avoid walking alone.",
                "location_name": "PSU Main Gate Road",
                "latitude": 9.741850,
                "longitude": 118.735080,
                "risk_level": SafetyReport.RiskLevel.HIGH,
                "status": SafetyReport.Status.VERIFIED,
                "time_observed": time(19, 30),
                "lighting_condition": SafetyReport.LightingCondition.NO_LIGHT,
                "crowd_level": SafetyReport.CrowdLevel.FEW,
            },
            {
                "user": user,
                "title": "Broken street light near boarding house",
                "category": SafetyReport.Category.BROKEN_STREET_LIGHT,
                "description": "The street light near the boarding house has been off for several nights and the sidewalk is hard to see.",
                "location_name": "Boarding House Street",
                "latitude": 9.742420,
                "longitude": 118.734540,
                "risk_level": SafetyReport.RiskLevel.MEDIUM,
                "status": SafetyReport.Status.PENDING,
                "time_observed": time(20, 15),
                "lighting_condition": SafetyReport.LightingCondition.DIM,
                "crowd_level": SafetyReport.CrowdLevel.FEW,
            },
            {
                "user": user,
                "title": "Flooded sidewalk near market",
                "category": SafetyReport.Category.FLOODED_ROAD,
                "description": "The sidewalk near the public market floods after rain and pedestrians walk on the road instead.",
                "location_name": "Public Market Sidewalk",
                "latitude": 9.743180,
                "longitude": 118.736510,
                "risk_level": SafetyReport.RiskLevel.MEDIUM,
                "status": SafetyReport.Status.IN_PROGRESS,
                "time_observed": time(16, 45),
                "lighting_condition": SafetyReport.LightingCondition.MODERATE,
                "crowd_level": SafetyReport.CrowdLevel.CROWDED,
            },
            {
                "user": trusted,
                "title": "Stray dogs near shortcut path",
                "category": SafetyReport.Category.STRAY_DOGS,
                "description": "Several stray dogs chase commuters using the shortcut path behind the stores during early morning walks.",
                "location_name": "Shortcut Path Behind Stores",
                "latitude": 9.740920,
                "longitude": 118.733870,
                "risk_level": SafetyReport.RiskLevel.HIGH,
                "status": SafetyReport.Status.PENDING,
                "time_observed": time(5, 40),
                "lighting_condition": SafetyReport.LightingCondition.DIM,
                "crowd_level": SafetyReport.CrowdLevel.EMPTY,
            },
            {
                "user": trusted,
                "title": "Accident-prone crossing near highway",
                "category": SafetyReport.Category.ACCIDENT_PRONE,
                "description": "Vehicles move fast near the highway crossing and there is no working pedestrian signal for students.",
                "location_name": "Highway Crossing",
                "latitude": 9.744050,
                "longitude": 118.737140,
                "risk_level": SafetyReport.RiskLevel.CRITICAL,
                "status": SafetyReport.Status.VERIFIED,
                "time_observed": time(7, 10),
                "lighting_condition": SafetyReport.LightingCondition.BRIGHT,
                "crowd_level": SafetyReport.CrowdLevel.CROWDED,
            },
            {
                "user": user,
                "title": "Suspicious activity near empty lot",
                "category": SafetyReport.Category.SUSPICIOUS_ACTIVITY,
                "description": "People have been loitering near the empty lot at night and several workers now avoid this path.",
                "location_name": "Empty Lot Corner",
                "latitude": 9.741160,
                "longitude": 118.737740,
                "risk_level": SafetyReport.RiskLevel.HIGH,
                "status": SafetyReport.Status.PENDING,
                "time_observed": time(22, 0),
                "lighting_condition": SafetyReport.LightingCondition.NO_LIGHT,
                "crowd_level": SafetyReport.CrowdLevel.EMPTY,
                "is_anonymous": True,
                "visibility_level": SafetyReport.VisibilityLevel.ANONYMOUS_PUBLIC,
            },
            {
                "user": trusted,
                "title": "No pedestrian lane near terminal",
                "category": SafetyReport.Category.NO_PEDESTRIAN_LANE,
                "description": "Commuters cross between vehicles near the terminal because there is no clear pedestrian lane.",
                "location_name": "Transport Terminal",
                "latitude": 9.745210,
                "longitude": 118.735760,
                "risk_level": SafetyReport.RiskLevel.MEDIUM,
                "status": SafetyReport.Status.PENDING,
                "time_observed": time(17, 20),
                "lighting_condition": SafetyReport.LightingCondition.MODERATE,
                "crowd_level": SafetyReport.CrowdLevel.CROWDED,
            },
            {
                "user": user,
                "title": "Poor visibility near campus back gate",
                "category": SafetyReport.Category.POOR_VISIBILITY,
                "description": "Bushes and parked tricycles block visibility near the campus back gate, especially before sunrise.",
                "location_name": "Campus Back Gate",
                "latitude": 9.740280,
                "longitude": 118.735930,
                "risk_level": SafetyReport.RiskLevel.MEDIUM,
                "status": SafetyReport.Status.PENDING,
                "time_observed": time(5, 25),
                "lighting_condition": SafetyReport.LightingCondition.DIM,
                "crowd_level": SafetyReport.CrowdLevel.FEW,
            },
        ]

        created_reports = []
        for item in reports:
            report, _ = SafetyReport.objects.update_or_create(
                title=item["title"],
                defaults={
                    "user": item["user"],
                    "category": item["category"],
                    "description": item["description"],
                    "location_name": item["location_name"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "risk_level": item["risk_level"],
                    "status": item["status"],
                    "time_observed": item["time_observed"],
                    "day_type": item.get("day_type", SafetyReport.DayType.WEEKDAY),
                    "lighting_condition": item["lighting_condition"],
                    "crowd_level": item["crowd_level"],
                    "is_anonymous": item.get("is_anonymous", False),
                    "visibility_level": item.get("visibility_level", SafetyReport.VisibilityLevel.PUBLIC),
                },
            )
            created_reports.append(report)

        for index, report in enumerate(created_reports):
            ReportConfirmation.objects.update_or_create(
                report=report,
                user=trusted if report.user == user else user,
                defaults={
                    "confirmation_type": ReportConfirmation.ConfirmationType.CONFIRMED
                    if index % 3 != 0
                    else ReportConfirmation.ConfirmationType.DISPUTED,
                    "comment": "Sample community feedback for seed data.",
                },
            )
            if report.status in [SafetyReport.Status.VERIFIED, SafetyReport.Status.IN_PROGRESS]:
                ReportStatusHistory.objects.get_or_create(
                    report=report,
                    admin=admin,
                    old_status=SafetyReport.Status.PENDING,
                    new_status=report.status,
                    defaults={"admin_note": "Seeded admin verification history."},
                )
            refresh_report_intelligence(report)

        RouteNote.objects.update_or_create(
            user=trusted,
            location_name="PSU Main Gate Road",
            defaults={
                "latitude": 9.741850,
                "longitude": 118.735080,
                "note": "Use the left side because it has more lights and nearby stores.",
                "safety_tip_type": RouteNote.SafetyTipType.BETTER_LIGHTING,
            },
        )
        RouteNote.objects.update_or_create(
            user=user,
            location_name="Shortcut Path Behind Stores",
            defaults={
                "latitude": 9.740920,
                "longitude": 118.733870,
                "note": "Avoid this shortcut after 8 PM and use the main road instead.",
                "safety_tip_type": RouteNote.SafetyTipType.AVOID_AT_NIGHT,
            },
        )
        SavedRoute.objects.update_or_create(
            user=user,
            route_name="Dorm to Campus",
            defaults={
                "start_location": "Boarding House Street",
                "end_location": "PSU Main Gate Road",
                "start_latitude": 9.742420,
                "start_longitude": 118.734540,
                "end_latitude": 9.741850,
                "end_longitude": 118.735080,
                "usual_time": time(7, 30),
                "notes": "Morning class route.",
            },
        )

        self.stdout.write(self.style.SUCCESS("SafeWalk sample data created successfully."))

    def create_user(self, username, email, password, role, trust_score, is_staff=False, is_superuser=False):
        user, _ = User.objects.update_or_create(
            username=username,
            defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser, "is_active": True},
        )
        user.set_password(password)
        user.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.trust_score = trust_score
        profile.save()
        return user
