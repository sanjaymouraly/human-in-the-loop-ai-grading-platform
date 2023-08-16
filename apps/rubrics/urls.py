from django.urls import path
from . import views

urlpatterns = [
    path('<int:project_pk>/', views.rubric_list, name='rubric_list'),
    path('<int:project_pk>/create/', views.rubric_create, name='rubric_create'),
    path('<int:project_pk>/<int:pk>/', views.rubric_detail, name='rubric_detail'),
    path('<int:project_pk>/<int:pk>/edit/', views.rubric_edit, name='rubric_edit'),
    path('<int:project_pk>/<int:pk>/clone/', views.rubric_clone, name='rubric_clone'),
    path('<int:project_pk>/<int:rubric_pk>/dimensions/create/', views.dimension_create, name='dimension_create'),
    path('<int:project_pk>/<int:rubric_pk>/dimensions/<int:pk>/edit/', views.dimension_edit, name='dimension_edit'),
    path('<int:project_pk>/<int:rubric_pk>/dimensions/<int:pk>/delete/', views.dimension_delete, name='dimension_delete'),
]
