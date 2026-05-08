from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from .auth_views import (
    LoginView,
    MeView,
    LogoutView,
    UpdateRoleView,
    ProfileView,
    ProfileByUsernameView,
    ProfileUpdateView,
    NotificationListView,
    NotificationReadView,
    NotificationUnreadView,
    NotificationDeleteView,
)

def api_root(request):
    return JsonResponse({
        "message": "Fusion Leave Management System API",
        "endpoints": {
            "admin": "/admin/",
            "leave_api": "/otheracademic/api/"
        }
    })

urlpatterns = [
    path('', api_root, name='api-root'),
    path('admin/', admin.site.urls),
    path('api/auth/login/', LoginView.as_view(), name='api-login'),
    path('api/auth/me', MeView.as_view(), name='api-me'),
    path('api/auth/logout/', LogoutView.as_view(), name='api-logout'),
    path('api/update-role/', UpdateRoleView.as_view(), name='api-update-role'),
    path('api/profile/', ProfileView.as_view(), name='api-profile'),
    path('api/profile_update/', ProfileUpdateView.as_view(), name='api-profile-update'),
    path('dep/api/profile/<str:username>/', ProfileByUsernameView.as_view(), name='api-profile-by-username'),
    path('api/notification/', NotificationListView.as_view(), name='api-notification-list'),
    path('api/notificationread', NotificationReadView.as_view(), name='api-notification-read'),
    path('api/notificationunread', NotificationUnreadView.as_view(), name='api-notification-unread'),
    path('api/notificationdelete', NotificationDeleteView.as_view(), name='api-notification-delete'),
    path('otheracademic/api/', include('other_academic.api.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
