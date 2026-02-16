"""
URL configuration for sparql_app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from graphs.views import (
    GraphMapConfigViewSet, GraphMapPermissionViewSet, GraphMapShareViewSet, 
    GraphMapVersionViewSet, RDFGraphACLViewSet, RDFGraphPermissionViewSet
)
from graphs import auth_views
from graphs import api_views
from graphs.compare_views import compare_content, apply_choices
from graphs.api_router import api_router
from sparql_app.oauth_views import oauth_callback_redirect, cookie_token_refresh, oauth_logout
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail import urls as wagtail_urls

router = DefaultRouter()
router.register(r'graph-configs', GraphMapConfigViewSet)
router.register(r'graph-config-permissions', GraphMapPermissionViewSet)
router.register(r'graph-config-shares', GraphMapShareViewSet)
router.register(r'graph-config-versions', GraphMapVersionViewSet)
router.register(r'rdf-graph-acls', RDFGraphACLViewSet)
router.register(r'rdf-graph-permissions', RDFGraphPermissionViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/cms/', api_router.urls),
    path('cms/compare/', compare_content, name='compare_content'),
    path('cms/compare/apply/', apply_choices, name='apply_choices'),
    path('cms/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),
    
    # Authentication endpoints
    path('api/auth/login/', auth_views.login, name='login'),
    path('api/auth/register/', auth_views.register, name='register'),
    path('api/auth/logout/', auth_views.logout, name='logout'),
    path('api/auth/me/', auth_views.current_user, name='current_user'),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # OAuth callback: issues JWT and redirects to frontend
    path('api/auth/oauth/callback/', oauth_callback_redirect, name='oauth_callback'),
    # Cookie-based token refresh (reads httpOnly oauth_refresh cookie)
    path('api/auth/oauth/refresh/', cookie_token_refresh, name='oauth_cookie_refresh'),
    # OAuth logout (blacklists refresh cookie and clears it)
    path('api/auth/oauth/logout/', oauth_logout, name='oauth_logout'),
    # django-allauth (Google OAuth etc.)
    path('accounts/', include('allauth.urls')),
    
    # Graph configuration endpoints
    path('api/user-graph-configs/', auth_views.user_graphs, name='user_graph_configs'),
    path('api/graph-configs/<int:graph_id>/share/', auth_views.share_graph, name='share_graph_config'),
    path('api/graph-configs/<int:graph_id>/permissions/', auth_views.graph_permissions, name='graph_config_permissions'),
    
    # API endpoints
    path('api/', include(router.urls)),
    path('graphs/', include('graphs.urls')),
    
    # Multi-source data management endpoints
    path('api/datasources/', api_views.data_sources_list, name='data_sources_list'),
    path('api/datasources/<int:source_id>/', api_views.data_source_detail, name='data_source_detail'),
    path('api/datasources/<int:source_id>/permissions/', api_views.data_source_permissions, name='data_source_permissions'),
    path('api/datasources/<int:source_id>/config/', api_views.data_source_update, name='data_source_update'),
    
    # Write-back endpoints
    path('api/write-back-requests/', api_views.create_write_back_request, name='create_write_back_request'),
    path('api/write-back-requests/list/', api_views.write_back_requests_list, name='write_back_requests_list'),
    path('api/write-back-requests/<int:request_id>/', api_views.write_back_request_detail, name='write_back_request_detail'),
    path('api/write-back-requests/<int:request_id>/approve/', api_views.approve_write_back_request, name='approve_write_back_request'),
    
    # Internal API endpoints (for FastAPI)
    path('api/internal/', include('graphs.internal_urls')),
    # Simple status endpoint
    path('status/', lambda request: HttpResponse("Django API running")),

    # Wagtail-powered front-end (catch-all)
    path('', include(wagtail_urls)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
