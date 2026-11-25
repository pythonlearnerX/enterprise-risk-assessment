from django.urls import path

from django.shortcuts import redirect

from . import auth_views, views

app_name = "risk_app"


def login_typo(request, rest):
    """地址栏把说明文字粘进 URL 时的兜底：/login/xxx → /login/。"""
    return redirect("risk_app:login")

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", auth_views.login_view, name="login"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("health/", views.health, name="health"),
    path("enterprise/list/", views.enterprise_list, name="enterprise_list"),
    path("enterprise/detail/<int:pk>/", views.enterprise_detail, name="enterprise_detail"),
    path("risk/list/", views.risk_list, name="risk_list"),
    path("risk/detail/<int:pk>/", views.risk_detail, name="risk_detail"),
    path("settings/ai/", views.ai_settings, name="ai_settings"),
    path("predict/", views.predict_page, name="predict"),
    path("predict/api/", views.predict_api, name="predict_api"),
    path("api/ai/test/", views.ai_test, name="ai_test"),
    path("api/ai/analyze/", views.ai_analyze, name="ai_analyze"),
    path("api/ai/explain/", views.ai_explain, name="ai_explain"),
    path("manage/ai-insights/", views.ai_insights, name="ai_insights"),
    path("model/show/", views.model_show, name="model_show"),
    path("model/analyze/", views.model_analyze, name="model_analyze"),
    path("console/", views.console, name="console"),
    path("manage/users/", views.manage_users, name="manage_users"),
    path("chart/compare/", views.chart_compare, name="chart_compare"),
    path("alerts/", views.alerts, name="alerts"),
    path("ab/", views.ab_dashboard, name="ab_dashboard"),
    path("ab/<int:pk>/", views.ab_detail, name="ab_detail"),
    path("ab/<int:pk>/toggle/", views.ab_toggle, name="ab_toggle"),
    path("api/ab/event/", views.ab_event, name="ab_event"),
    path("enterprise/<int:pk>/report.pdf", views.enterprise_report_pdf, name="enterprise_report_pdf"),
    path("login/<path:rest>", login_typo),
    path("chart/enterprise/", views.chart_enterprise, name="chart_enterprise"),
    path("chart/risk/", views.chart_risk, name="chart_risk"),
    path("chart/analysis/", views.chart_analysis, name="chart_analysis"),
    path("chart/map/", views.chart_map, name="chart_map"),
    path("api/chart/map/", views.chart_data_map, name="chart_data_map"),
    path("chart/image/<str:kind>.svg", views.chart_image, name="chart_image"),
    path("api/chart/enterprise/", views.chart_data_enterprise, name="chart_data_enterprise"),
    path("api/chart/risk/", views.chart_data_risk, name="chart_data_risk"),
    path("api/chart/analysis/", views.chart_data_analysis, name="chart_data_analysis"),
]