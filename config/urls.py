from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('lotto/', include('lotto.urls')),
    path('accounts/', include('accounts.urls')),
    path('admin-panel/', include('lotto.admin_urls')),
    path('', include('lotto.urls')),
]