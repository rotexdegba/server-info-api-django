from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('server/login', views.login_view, name='login'),
    path('server/logout', views.logout_view, name='logout'),
    # JSON API
    path('server/server-overview', views.api_server_overview, name='api_server_overview'),
    path('server/cpus-info', views.api_cpus_info, name='api_cpus_info'),
    path('server/hardware-info', views.api_hardware_info, name='api_hardware_info'),
    path('server/sound-card-info', views.api_sound_card_info, name='api_sound_card_info'),
    path('server/disk-drives-info', views.api_disk_drives_info, name='api_disk_drives_info'),
    path('server/disk-mounts-info', views.api_disk_mounts_info, name='api_disk_mounts_info'),
    path('server/network-info', views.api_network_info, name='api_network_info'),
    path('server/processes', views.api_processes, name='api_processes'),
    path('server/services', views.api_services, name='api_services'),
]
