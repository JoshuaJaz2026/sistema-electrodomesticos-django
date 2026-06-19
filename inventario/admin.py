from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import (
    Perfil, Plataforma, Categoria, Electrodomestico, Producto, 
    MovimientoPercheron, SimulacionMercadoLibre, ReferenciaComision, 
    ReferenciaCosto, ReporteMercadoLibre, IngresoPercheron, SalidaMercadoLibre
)

# =========================================================
# 1. PLATAFORMAS Y USUARIOS
# =========================================================
@admin.register(Plataforma)
class PlataformaAdmin(ImportExportModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Perfil)
class PerfilAdmin(ImportExportModelAdmin): 
    list_display = ('usuario', 'mostrar_plataformas')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')
    list_filter = ('plataformas',)
    filter_horizontal = ('plataformas',)

    def mostrar_plataformas(self, obj):
        plataformas = [p.nombre for p in obj.plataformas.all()]
        return " - ".join(plataformas) if plataformas else "Sin plataformas"
    
    mostrar_plataformas.short_description = 'Plataformas Autorizadas'

# =========================================================
# 2. REGISTROS SIMPLES
# =========================================================
admin.site.register(Categoria)
admin.site.register(Electrodomestico)

# =========================================================
# 3. MÓDULO PERCHERÓN (Inventario Maestro)
# =========================================================
@admin.register(Producto)
class ProductoAdmin(ImportExportModelAdmin): 
    list_display = ('sku', 'modelo', 'marca', 'titulo', 'codigo_ean', 'stock_actual', 'costo_soles')
    search_fields = ('sku', 'modelo', 'titulo', 'codigo_ean')
    list_filter = ('marca', 'ubicacion')

@admin.register(MovimientoPercheron)
class MovimientoPercheronAdmin(ImportExportModelAdmin): 
    list_display = ('producto', 'tipo', 'cantidad', 'fecha', 'usuario', 'canal_venta', 'documento_salida')
    list_filter = ('tipo', 'fecha', 'canal_venta', 'usuario')
    search_fields = ('producto__sku', 'producto__titulo', 'documento_salida', 'proveedor_motivo')

@admin.register(IngresoPercheron)
class IngresoPercheronAdmin(ImportExportModelAdmin):
    list_display = ('sku', 'modelo', 'titulo', 'cantidad', 'fecha_ingreso', 'creado_por')
    search_fields = ('sku', 'modelo', 'titulo', 'serie_nro')
    list_filter = ('fecha_ingreso', 'creado_por')

# =========================================================
# 4. MÓDULO MERCADO LIBRE
# =========================================================
@admin.register(SimulacionMercadoLibre)
class SimulacionMercadoLibreAdmin(ImportExportModelAdmin):
    list_display = ('producto', 'cod_publicacion', 'precio_venta', 'ganancia', 'rentabilidad_porc', 'usuario', 'fecha_registro')
    list_filter = ('item_type', 'estado_publicacion', 'tipo_publicacion', 'mpe', 'fecha_registro')
    search_fields = ('producto', 'cod_publicacion', 'cod_producto', 'usuario__username')

@admin.register(ReporteMercadoLibre)
class ReporteMercadoLibreAdmin(ImportExportModelAdmin):
    list_display = ('nro_orden', 'fecha', 'modelo', 'producto', 'cantidad', 'total_pagado', 'ganancia')
    search_fields = ('nro_orden', 'modelo', 'producto', 'sku_almacen')
    list_filter = ('fecha', 'tipo_venta', 'marca', 'categoria')

@admin.register(SalidaMercadoLibre)
class SalidaMercadoLibreAdmin(ImportExportModelAdmin):
    list_display = ('sku', 'modelo', 'nro_venta', 'fecha_salida', 'tipo_venta', 'creado_por')
    search_fields = ('sku', 'modelo', 'titulo', 'nro_venta', 'serie')
    list_filter = ('fecha_salida', 'tipo_venta')

# =========================================================
# 5. REFERENCIAS Y COSTOS
# =========================================================
@admin.register(ReferenciaComision)
class ReferenciaComisionAdmin(ImportExportModelAdmin):
    list_display = ('sub_categoria', 'categoria', 'comision')
    search_fields = ('sub_categoria', 'categoria')

@admin.register(ReferenciaCosto)
class ReferenciaCostoAdmin(ImportExportModelAdmin):
    list_display = ('codigo', 'producto', 'costo_cero', 'costo_u_dolares', 'costo_u_soles')
    search_fields = ('codigo', 'producto')