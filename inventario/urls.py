from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # 1. Rutas de Acceso y Portal Público
    path('', views.selector_plataformas, name='selector'),
    path('login/', views.LoginCamaleonicoView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('loading/', views.pantalla_carga, name='pantalla_carga'),
    
    # 2. Dashboard Principal
    path('inicio/', views.inicio, name='inicio'),
    
    # 3. Inventario Global: Magazzino
    path('inventario/magazzino/', views.inventario_magazzino, name='inv_magazzino'),
    
    # 4. Inventario Global: Percherón y sus subsecciones
    path('inventario/percheron/', views.percheron_inventario, name='percheron_inventario'),
    path('inventario/percheron/ingresos/', views.percheron_ingresos, name='percheron_ingresos'),
    path('inventario/percheron/salidas/', views.percheron_salidas, name='percheron_salidas'),
    
    # 5. Reportes y Herramientas
    path('reportes/', views.reporte_ventas, name='reporte_ventas'),
    path('simulador/', views.simulador_costos, name='simulador_costos'),
]