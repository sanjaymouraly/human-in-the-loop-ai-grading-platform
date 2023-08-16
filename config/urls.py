from django.contrib import admin
from django.urls import path, include
from apps.core.views import landing_view, dashboard_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('projects/', include('apps.projects.urls')),
    path('datasets/', include('apps.datasets.urls')),
    path('rubrics/', include('apps.rubrics.urls')),
    path('evaluations/', include('apps.evaluations.urls')),
    path('analytics/', include('apps.analytics.urls')),
    path('', landing_view, name='landing'),
    path('dashboard/', dashboard_view, name='dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
