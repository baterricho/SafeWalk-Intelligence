import django_filters

from .models import SafetyReport


class SafetyReportFilter(django_filters.FilterSet):
    location_name = django_filters.CharFilter(field_name="location_name", lookup_expr="icontains")
    date_from = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    date_to = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")

    class Meta:
        model = SafetyReport
        fields = [
            "category",
            "risk_level",
            "status",
            "lighting_condition",
            "crowd_level",
            "location_name",
            "date_from",
            "date_to",
        ]
