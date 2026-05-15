from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.selector_plataformas, name='selector'),
    path('login/', views.LoginCamaleonicoView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('loading/', views.pantalla_carga, name='pantalla_carga'),
    path('inicio/', views.inicio, name='inicio'),
    
    # ESTAS SON LAS RUTAS QUE DEBEN COINCIDIR CON TU VIEWS.PY ACTUAL
    path('inventario/magazzino/', views.inventario_magazzino, name='inv_magazzino'),
    path('inventario/percheron/', views.inventario_percheron, name='inv_percheron'),
    path('reportes/', views.reporte_ventas, name='reporte_ventas'),
    path('simulador/', views.simulador_costos, name='simulador_costos'),
]