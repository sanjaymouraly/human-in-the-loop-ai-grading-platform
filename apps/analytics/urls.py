from django.urls import path
from . import views

urlpatterns = [
    path('<int:project_pk>/', views.analytics_dashboard, name='analytics_dashboard'),
    path('<int:project_pk>/export/', views.export_report, name='export_report'),
    path('<int:project_pk>/anonymized/', views.anonymized_export, name='anonymized_export'),
    path('<int:project_pk>/calibration/', views.calibration_view, name='calibration_view'),
]
