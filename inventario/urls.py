from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # ==========================================
    # 1. RUTAS DE ACCESO Y PORTAL PÚBLICO
    # ==========================================
    path('', views.selector_plataformas, name='selector'),
    path('login/', views.LoginCamaleonicoView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('loading/', views.pantalla_carga, name='pantalla_carga'),
    
    # ==========================================
    # 2. DASHBOARD PRINCIPAL Y MAGAZZINO
    # ==========================================
    path('inicio/', views.inicio, name='inicio'),
    path('inventario/magazzino/', views.inventario_magazzino, name='inv_magazzino'),
    
    # ==========================================
    # 3. SECCIÓN PERCHERÓN: GLOBALES
    # ==========================================
    path('percheron/ingresos/', views.percheron_ingresos, name='percheron_ingresos'),
    path('percheron/registros/', views.percheron_registros, name='percheron_registros'),
    path('percheron/modelos/', views.percheron_modelos, name='percheron_modelos'),

    # ==========================================
    # 4. SECCIÓN PERCHERÓN: PLATAFORMAS ESPECÍFICAS
    # ==========================================
    path('percheron/mercado-libre/', views.percheron_mercadolibre, name='percheron_mercadolibre'),
    path('percheron/mercado-libre-junior/', views.percheron_mercadolibre_junior, name='percheron_mercadolibre_junior'),
    path('percheron/falabella/', views.percheron_falabella, name='percheron_falabella'),
    path('percheron/creditienda/', views.percheron_creditienda, name='percheron_creditienda'),
    path('percheron/intercorp/', views.percheron_intercorp, name='percheron_intercorp'),
    path('percheron/tiktok/', views.percheron_tiktok, name='percheron_tiktok'),
    path('percheron/venta-libre/', views.percheron_ventalibre, name='percheron_ventalibre'),
    path('percheron/bci/', views.percheron_bci, name='percheron_bci'),

    # ==========================================
    # 5. REPORTES Y HERRAMIENTAS
    # ==========================================
    path('reportes/', views.reporte_ventas, name='reporte_ventas'),
    path('simulador/', views.simulador_costos, name='simulador_costos'),
    
    # ==========================================
    # 6. APIs Y GUARDADO DE DATOS (AJAX)
    # ==========================================
    path('api/buscar-producto/', views.api_buscar_producto, name='api_buscar_producto'),
    path('api/guardar-productos/', views.guardar_nuevos_productos, name='guardar_nuevos_productos'),
    path('api/guardar-kardex/', views.guardar_kardex_percheron, name='guardar_kardex_percheron'),
]