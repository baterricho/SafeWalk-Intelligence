from django.contrib import admin, messages
from django.utils.html import format_html

from .models import ReportConfirmation, ReportStatusHistory, SafetyReport
from .services import refresh_report_intelligence, update_user_trust_score


@admin.register(SafetyReport)
class SafetyReportAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "category",
        "risk_level",
        "status",
        "location_name",
        "safety_score",
        "credibility_label",
        "photo",
        "created_at",
    ]
    list_filter = ["category", "risk_level", "status", "lighting_condition", "crowd_level", "created_at"]
    search_fields = ["title", "description", "location_name", "user__username"]
    base_readonly_fields = [
        "safety_score",
        "evidence_score",
        "credibility_label",
        "photo_preview",
        "created_at",
        "updated_at",
    ]
    moderated_readonly_fields = [
        "user",
        "title",
        "category",
        "description",
        "location_name",
        "latitude",
        "longitude",
        "risk_level",
        "time_observed",
        "day_type",
        "lighting_condition",
        "crowd_level",
        "is_anonymous",
        "visibility_level",
        "photo",
        *base_readonly_fields,
    ]
    actions = ["mark_verified", "mark_rejected", "mark_resolved"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.moderated_readonly_fields
        return self.base_readonly_fields

    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-width: 220px; border-radius: 8px;" alt="Report photo">', obj.photo.url)
        return "No photo uploaded."

    def save_model(self, request, obj, form, change):
        old_status = None
        if change and obj.pk:
            old_status = SafetyReport.objects.get(pk=obj.pk).status
        super().save_model(request, obj, form, change)
        if old_status and old_status != obj.status:
            ReportStatusHistory.objects.create(
                report=obj,
                admin=request.user,
                old_status=old_status,
                new_status=obj.status,
                admin_note="Changed in Django admin.",
            )
            if obj.status == SafetyReport.Status.VERIFIED:
                update_user_trust_score(obj.user, "verified_report")
            elif obj.status == SafetyReport.Status.REJECTED:
                update_user_trust_score(obj.user, "rejected_report")
            elif obj.status == SafetyReport.Status.RESOLVED:
                update_user_trust_score(obj.user, "resolved_report")
        refresh_report_intelligence(obj)

    @admin.action(description="Mark selected reports as verified")
    def mark_verified(self, request, queryset):
        self._bulk_status_update(request, queryset, SafetyReport.Status.VERIFIED)

    @admin.action(description="Mark selected reports as rejected")
    def mark_rejected(self, request, queryset):
        self._bulk_status_update(request, queryset, SafetyReport.Status.REJECTED)

    @admin.action(description="Mark selected reports as resolved")
    def mark_resolved(self, request, queryset):
        self._bulk_status_update(request, queryset, SafetyReport.Status.RESOLVED)

    def _bulk_status_update(self, request, queryset, new_status):
        count = 0
        for report in queryset:
            old_status = report.status
            if old_status == new_status:
                continue
            report.status = new_status
            report.save()
            ReportStatusHistory.objects.create(
                report=report,
                admin=request.user,
                old_status=old_status,
                new_status=new_status,
                admin_note="Bulk action in Django admin.",
            )
            refresh_report_intelligence(report)
            count += 1
        messages.success(request, f"{count} report(s) updated.")


@admin.register(ReportConfirmation)
class ReportConfirmationAdmin(admin.ModelAdmin):
    list_display = ["report", "user", "confirmation_type", "created_at"]
    list_filter = ["confirmation_type", "created_at"]
    search_fields = ["report__title", "user__username", "comment"]
    readonly_fields = ["created_at"]


@admin.register(ReportStatusHistory)
class ReportStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ["report", "admin", "old_status", "new_status", "created_at"]
    list_filter = ["old_status", "new_status", "created_at"]
    search_fields = ["report__title", "admin__username", "admin_note"]
    readonly_fields = ["created_at"]
