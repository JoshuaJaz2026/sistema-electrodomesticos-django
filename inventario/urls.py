from django.urls import path
from . import views

urlpatterns = [
    # El portal de plataformas será la página principal
    path('', views.selector_plataformas, name='selector'),
    
    # El panel de inicio protegido
    path('panel/', views.inicio, name='inicio'), 
]