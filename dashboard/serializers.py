from rest_framework import serializers


class DashboardSummarySerializer(serializers.Serializer):
    total_reports = serializers.IntegerField()
    active_critical_reports = serializers.IntegerField()
    verified_reports = serializers.IntegerField()
    resolved_reports = serializers.IntegerField()
    most_reported_area = serializers.CharField()
    most_common_issue = serializers.CharField()
    highest_risk_time_of_day = serializers.CharField()
    areas_improving = serializers.ListField(child=serializers.CharField())
    areas_getting_worse = serializers.ListField(child=serializers.CharField())
    top_trusted_reporters = serializers.ListField(child=serializers.DictField())
    generated_at = serializers.DateTimeField()
