from django.urls import path
from household import views
from shopping import views as shopping
from presence import views as presence
from planning import views as planning

urlpatterns = [
    path('', views.personal, name='home'),
    path('setup/', views.setup, name='setup'),
    path('login/', views.sign_in, name='login'),
    path('logout/', views.sign_out, name='logout'),
    path('settings/', views.settings_page, name='settings'),
    path('appearance.css', views.appearance_css, name='appearance_css'),
    path('appearance-display.css', views.appearance_display_css, name='appearance_display_css'),
    path('profile/', views.profile, name='profile'),
    path('plan/', planning.planner, name='planner'),
    path('display/', views.display, name='display'),
    path('display/preview/', views.display_preview, name='display_preview'),
    path('display/pair/', views.pair_display, name='pair_display'),
    path('display/offline/', views.offline_display, name='offline_display'),
    path('display/sw.js', views.display_worker, name='display_worker'),
    path('api/state/', shopping.state, name='state'),
    path('api/shopping/', shopping.mutate, name='mutate'),
    path('api/shopping/export/', shopping.export, name='export'),
    path('api/presence/', presence.mutate, name='presence_mutate'),
    path('health/', views.health, name='health'),
]
