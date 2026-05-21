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
    # 5. REPORTES DE VENTAS POR PLATAFORMA
    # ==========================================
    path('reportes/creditienda/', views.reporte_creditienda, name='reporte_creditienda'),
    path('reportes/falabella/', views.reporte_falabella, name='reporte_falabella'),
    path('reportes/intercorp/', views.reporte_intercorp, name='reporte_intercorp'),
    path('reportes/mercado-libre-junior/', views.reporte_mercadolibre_junior, name='reporte_mercadolibre_junior'),
    path('reportes/mercado-libre/', views.reporte_mercadolibre, name='reporte_mercadolibre'),
    path('reportes/tiktok/', views.reporte_tiktok, name='reporte_tiktok'),
    path('reportes/venta-libre/', views.reporte_ventalibre, name='reporte_ventalibre'),
    path('reportes/web/', views.reporte_web, name='reporte_web'),

    # ==========================================
    # 6. SIMULADORES DE COSTOS POR PLATAFORMA
    # ==========================================
    path('simulador/creditienda/', views.simulador_creditienda, name='simulador_creditienda'),
    path('simulador/falabella/', views.simulador_falabella, name='simulador_falabella'),
    path('simulador/intercorp/', views.simulador_intercorp, name='simulador_intercorp'),
    path('simulador/mercado-libre-junior/', views.simulador_mercadolibre_junior, name='simulador_mercadolibre_junior'),
    path('simulador/mercado-libre/', views.simulador_mercadolibre, name='simulador_mercadolibre'),
    path('simulador/tiktok/', views.simulador_tiktok, name='simulador_tiktok'),
    path('simulador/venta-libre/', views.simulador_ventalibre, name='simulador_ventalibre'),
    path('simulador/web/', views.simulador_web, name='simulador_web'),
    
    # ==========================================
    # 7. APIs Y GUARDADO DE DATOS (AJAX)
    # ==========================================
    path('api/buscar-producto/', views.api_buscar_producto, name='api_buscar_producto'),
    path('api/guardar-productos/', views.guardar_nuevos_productos, name='guardar_nuevos_productos'),
    path('api/guardar-kardex/', views.guardar_kardex_percheron, name='guardar_kardex_percheron'),
    path('api/guardar-simulador/', views.api_guardar_simulador, name='api_guardar_simulador'),

    path('referencia-comisiones/', views.referencia_comisiones, name='referencia_comisiones'),
    path('guardar-comisiones/', views.guardar_comisiones, name='guardar_comisiones'), # <--- ESTA FALTA
]