from django.urls import path
from . import views, api_views

urlpatterns = [
    path('queue/', views.reviewer_queue, name='reviewer_queue'),
    path('projects/<int:project_pk>/assignments/', views.assignment_list, name='assignment_list'),
    path('projects/<int:project_pk>/assignments/create/', views.assignment_create, name='assignment_create'),
    path('assignments/<int:assignment_pk>/review/', views.review_workspace, name='review_workspace'),
    path('assignments/<int:assignment_pk>/autosave/', api_views.api_autosave, name='api_autosave'),
    path('assignments/<int:assignment_pk>/issues/create/', views.issue_create, name='issue_create'),
    path('assignments/<int:assignment_pk>/issues/<int:issue_pk>/delete/', views.issue_delete, name='issue_delete'),
    path('projects/<int:project_pk>/disagreements/', views.disagreement_list, name='disagreement_list'),
    path('projects/<int:project_pk>/items/<int:item_pk>/adjudicate/', views.adjudication_view, name='adjudication_view'),
    path('reviews/<int:review_pk>/', views.review_detail, name='review_detail'),
    
    # Secured API
    path('api/projects/', api_views.api_project_list, name='api_project_list'),
    path('api/projects/<int:project_pk>/ingest/', api_views.api_dataset_ingest, name='api_dataset_ingest'),
    path('api/projects/<int:project_pk>/report/', api_views.api_report, name='api_report'),
]
