from django.urls import path

from apps.tenants.views import ApplicationDetailView

urlpatterns = [
    path("applications/<str:app_id>/", ApplicationDetailView.as_view(), name="application-detail"),
]
