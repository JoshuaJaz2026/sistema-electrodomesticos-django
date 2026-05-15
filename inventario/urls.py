from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.selector_plataformas, name='selector'),
    path('login/', views.LoginCamaleonicoView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('inicio/', views.inicio, name='inicio'),
    
    # NUEVAS RUTAS CONECTADAS A VIEWS.PY
    path('inventario/', views.inventario_global, name='inventario_global'),
    path('reportes/', views.reporte_ventas, name='reporte_ventas'),
    path('simulador/', views.simulador_costos, name='simulador_costos'),
    path('inventario/magazzino/', views.inventario_magazzino, name='inv_magazzino'),
    path('inventario/percheron/', views.inventario_percheron, name='inv_percheron'),
]