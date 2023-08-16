from django.urls import path
from . import views

urlpatterns = [
    path('<int:project_pk>/', views.dataset_list, name='dataset_list'),
    path('<int:project_pk>/upload/', views.dataset_upload, name='dataset_upload'),
    path('<int:project_pk>/<int:pk>/', views.dataset_detail, name='dataset_detail'),
    path('<int:project_pk>/<int:pk>/export/', views.dataset_export, name='dataset_export'),
]
