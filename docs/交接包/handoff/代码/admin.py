from django.contrib import admin

from .models import AlertRule, AuditLog, Enterprise, RiskIndicator, RiskSnapshot, UserProfile


@admin.register(Enterprise)
class EnterpriseAdmin(admin.ModelAdmin):
    list_display = ("firm_name", "usc_code", "ope_status", "reg_cap", "est_date")
    search_fields = ("firm_name", "usc_code", "legal_rep")
    list_filter = ("ope_status", "firm_category")
    list_per_page = 20
    ordering = ("-update_time",)


@admin.register(RiskIndicator)
class RiskIndicatorAdmin(admin.ModelAdmin):
    list_display = ("name", "total_risk_score", "risk_level", "create_time")
    search_fields = ("name",)
    list_filter = ("risk_level",)
    list_per_page = 20
    ordering = ("-total_risk_score",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "phone")
    list_filter = ("role",)
    search_fields = ("user__username", "department")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "target", "ip", "create_time")
    list_filter = ("action",)
    search_fields = ("target", "detail")

@admin.register(RiskSnapshot)
class RiskSnapshotAdmin(admin.ModelAdmin):
    list_display = ("enterprise", "year", "total_score", "level", "note")
    list_filter = ("year", "level")
    search_fields = ("enterprise__firm_name",)


@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "metric", "threshold", "level", "enabled")
    list_filter = ("metric", "enabled")
    search_fields = ("name", "user__username")
