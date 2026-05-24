from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import user_is_admin
from notifications.services import notify_new_report, notify_report_comment, notify_report_update
from .filters import SafetyReportFilter
from .forms import SafetyReportForm
from .models import ReportConfirmation, SafetyReport
from .permissions import IsConfirmationOwnerOrAdmin, IsOwnerOrAdminOrReadOnly
from .serializers import AreaClusterSerializer, ReportConfirmationSerializer, SafetyReportSerializer
from .services import (
    calculate_evidence_score,
    calculate_report_decay,
    calculate_safety_score,
    detect_duplicate_report,
    generate_area_clusters,
    generate_area_summary,
    generate_location_timeline,
    refresh_report_intelligence,
    suggest_admin_status,
    update_user_trust_score,
)


def visible_reports_for_user(user):
    qs = SafetyReport.objects.select_related("user", "user__profile").prefetch_related("confirmations")
    if user_is_admin(user):
        return qs
    public_filter = ~Q(visibility_level=SafetyReport.VisibilityLevel.ADMIN_ONLY)
    if user and user.is_authenticated:
        return qs.filter(public_filter | Q(user=user))
    return qs.filter(public_filter)


class SafetyReportViewSet(viewsets.ModelViewSet):
    serializer_class = SafetyReportSerializer
    permission_classes = [IsOwnerOrAdminOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SafetyReportFilter
    search_fields = ["title", "description", "location_name"]
    ordering_fields = ["created_at", "updated_at", "safety_score", "risk_level"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return visible_reports_for_user(self.request.user)

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        duplicates = detect_duplicate_report(serializer.validated_data)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        data = serializer.data
        if duplicates:
            data["duplicate_warning"] = "Possible duplicate report found. You may support the existing report instead."
            data["possible_duplicates"] = duplicates
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        report = serializer.save(user=self.request.user)
        refresh_report_intelligence(report)
        notify_new_report(report)

    def perform_update(self, serializer):
        report = serializer.save()
        refresh_report_intelligence(report)
        notify_report_update(report, self.request.user, "The report details were updated.")

    @action(detail=True, methods=["get"], url_path="intelligence")
    def intelligence(self, request, pk=None):
        report = self.get_object()
        refresh_report_intelligence(report)
        data = {
            "report_id": report.id,
            "safety_score": calculate_safety_score(report),
            "score_label": report.score_label,
            "evidence": calculate_evidence_score(report),
            "decay_factor": calculate_report_decay(report),
            "suggested_status": suggest_admin_status(report),
            "timeline": generate_location_timeline(report.location_name),
        }
        return Response(data)

    @action(detail=False, methods=["get"], url_path="duplicates/check")
    def check_duplicates(self, request):
        duplicates = detect_duplicate_report(request.query_params)
        return Response(
            {
                "warning": "Possible duplicate report found. You may support the existing report instead."
                if duplicates
                else None,
                "duplicates": duplicates,
            }
        )

    @action(detail=True, methods=["get", "post"], url_path="confirmations")
    def confirmations(self, request, pk=None):
        report = self.get_object()
        if request.method == "GET":
            serializer = ReportConfirmationSerializer(report.confirmations.select_related("user"), many=True)
            return Response(serializer.data)

        if not request.user.is_authenticated:
            return Response({"detail": "Authentication is required."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = ReportConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        confirmation, created = ReportConfirmation.objects.update_or_create(
            report=report,
            user=request.user,
            defaults={
                "confirmation_type": serializer.validated_data["confirmation_type"],
                "comment": serializer.validated_data.get("comment", ""),
            },
        )
        refresh_report_intelligence(report)
        if created and confirmation.confirmation_type == ReportConfirmation.ConfirmationType.CONFIRMED:
            update_user_trust_score(report.user, "community_confirmed")
        if confirmation.comment:
            notify_report_comment(report, request.user, confirmation.comment)
        return Response(ReportConfirmationSerializer(confirmation).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConfirmationDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsConfirmationOwnerOrAdmin]

    def delete(self, request, pk):
        confirmation = get_object_or_404(ReportConfirmation, pk=pk)
        self.check_object_permissions(request, confirmation)
        report = confirmation.report
        confirmation.delete()
        refresh_report_intelligence(report)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AreaClustersAPIView(APIView):
    def get(self, request):
        serializer = AreaClusterSerializer(generate_area_clusters(), many=True)
        return Response(serializer.data)


class AreaTimelineAPIView(APIView):
    def get(self, request, location_name):
        return Response({"location_name": location_name, "timeline": generate_location_timeline(location_name)})


class AreaSummaryAPIView(APIView):
    def get(self, request, location_name):
        return Response(generate_area_summary(location_name))


def report_list_page(request):
    reports = visible_reports_for_user(request.user)
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
    context = {
        "reports": reports,
        "category_choices": SafetyReport.Category.choices,
        "risk_choices": SafetyReport.RiskLevel.choices,
        "status_choices": SafetyReport.Status.choices,
        "filters": {"q": query, "category": category, "risk_level": risk_level, "status": status_value},
    }
    return render(request, "reports/report_list.html", context)


def report_feedback_counts(report):
    confirmations = report.confirmations.all()
    return {
        "confirmation_count": confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.CONFIRMED).count(),
        "dispute_count": confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.DISPUTED).count(),
        "resolved_count": confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.RESOLVED).count(),
        "evidence_needed_count": confirmations.filter(confirmation_type=ReportConfirmation.ConfirmationType.NEEDS_MORE_EVIDENCE).count(),
        "comment_count": confirmations.exclude(comment__exact="").count(),
    }


def report_detail_page(request, pk):
    report = get_object_or_404(visible_reports_for_user(request.user), pk=pk)
    if request.method == "POST" and request.user.is_authenticated:
        confirmation_type = request.POST.get("confirmation_type") or ReportConfirmation.ConfirmationType.COMMENT
        comment = request.POST.get("comment", "").strip()
        valid_types = dict(ReportConfirmation.ConfirmationType.choices)
        if confirmation_type in valid_types and (
            confirmation_type != ReportConfirmation.ConfirmationType.COMMENT or comment
        ):
            confirmation, _ = ReportConfirmation.objects.update_or_create(
                report=report,
                user=request.user,
                defaults={"confirmation_type": confirmation_type, "comment": comment[:500]},
            )
            refresh_report_intelligence(report)
            if confirmation.comment:
                notify_report_comment(report, request.user, confirmation.comment)
            messages.success(request, "Your community feedback was recorded.")
        return redirect("report_detail", pk=report.pk)
    confirmations = report.confirmations.select_related("user").order_by("-created_at")
    comments = confirmations.exclude(comment__exact="")
    return render(
        request,
        "reports/report_detail.html",
        {
            "report": report,
            "reporter_display": report.user.username if user_is_admin(request.user) and report.user else report.public_reporter_name,
            "confirmations": confirmations,
            "comments": comments,
            "feedback_counts": report_feedback_counts(report),
            "timeline": generate_location_timeline(report.location_name),
            "is_admin_viewer": user_is_admin(request.user),
        },
    )


@login_required
def report_create_page(request):
    form = SafetyReportForm(request.POST or None, request.FILES or None)
    duplicates = []
    if request.method == "POST" and form.is_valid():
        duplicates = detect_duplicate_report(form.cleaned_data)
        report = form.save(commit=False)
        report.user = request.user
        report.save()
        refresh_report_intelligence(report)
        notify_new_report(report)
        if duplicates:
            messages.warning(request, "Possible duplicate report found. You may support the existing report instead.")
        else:
            messages.success(request, "Safety report submitted.")
        return redirect("report_detail", pk=report.pk)
    return render(request, "reports/report_form.html", {"form": form, "duplicates": duplicates, "mode": "Create"})


@login_required
def report_update_page(request, pk):
    report = get_object_or_404(SafetyReport, pk=pk)
    if report.user != request.user and not user_is_admin(request.user):
        messages.error(request, "You can only edit your own reports.")
        return redirect("report_detail", pk=pk)
    if report.user != request.user:
        messages.error(request, "Admins can moderate report status, but cannot edit user report content.")
        return redirect("report_detail", pk=pk)
    form = SafetyReportForm(request.POST or None, request.FILES or None, instance=report)
    if request.method == "POST" and form.is_valid():
        report = form.save()
        refresh_report_intelligence(report)
        notify_report_update(report, request.user, "The report details were updated.")
        messages.success(request, "Safety report updated.")
        return redirect("report_detail", pk=report.pk)
    return render(request, "reports/report_form.html", {"form": form, "report": report, "mode": "Edit"})


@login_required
def report_delete_page(request, pk):
    report = get_object_or_404(SafetyReport, pk=pk)
    if report.user != request.user and not user_is_admin(request.user):
        messages.error(request, "You can only delete your own reports.")
        return redirect("report_detail", pk=pk)
    if request.method == "POST":
        report.delete()
        messages.info(request, "Safety report deleted.")
        return redirect("report_list")
    return render(request, "reports/report_confirm_delete.html", {"report": report})


def area_summary_page(request, location_name):
    return render(request, "reports/area_summary.html", generate_area_summary(location_name))
