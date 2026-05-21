from django.contrib import admin
from .models import Perfil, Plataforma, Categoria, Electrodomestico, Producto, MovimientoPercheron
from import_export.admin import ImportExportModelAdmin # Librería para carga masiva
from .models import SimulacionMercadoLibre

# 1. Configuración masiva para Plataformas (Para subir muchas tiendas de golpe)
@admin.register(Plataforma)
class PlataformaAdmin(ImportExportModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

# 2. Registros simples (Puedes convertirlos a ImportExportModelAdmin si lo necesitas luego)
admin.site.register(Categoria)
admin.site.register(Electrodomestico)

# 3. Configuración avanzada y masiva para Perfil
@admin.register(Perfil)
class PerfilAdmin(ImportExportModelAdmin): 
    # Definimos qué columnas se ven en la tabla principal
    list_display = ('usuario', 'mostrar_plataformas')

    # Añadimos un buscador por nombre de usuario
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')

    # Añadimos un filtro lateral
    list_filter = ('plataformas',)

    # El selector de dos columnas para cuando edites el perfil
    filter_horizontal = ('plataformas',)

    # Función para listar las plataformas en la tabla principal
    def mostrar_plataformas(self, obj):
        # Usamos el separador "-" 
        plataformas = [p.nombre for p in obj.plataformas.all()]
        return " - ".join(plataformas) if plataformas else "Sin plataformas"
    
    mostrar_plataformas.short_description = 'Plataformas Autorizadas'

# =========================================================
# 4. NUEVOS REGISTROS PARA EL MÓDULO PERCHERÓN (Con Carga Masiva)
# =========================================================

@admin.register(Producto)
class ProductoAdmin(ImportExportModelAdmin): 
    # Columnas que se verán en el listado del admin
    list_display = ('sku', 'modelo', 'marca', 'titulo', 'codigo_ean', 'stock_actual', 'costo_soles')
    # Barra de búsqueda para encontrar productos rápido
    search_fields = ('sku', 'modelo', 'titulo', 'codigo_ean')
    # Filtro lateral por marca y ubicación
    list_filter = ('marca', 'ubicacion')

@admin.register(MovimientoPercheron)
class MovimientoPercheronAdmin(ImportExportModelAdmin): 
    # Columnas para el historial de movimientos
    list_display = ('producto', 'tipo', 'cantidad', 'fecha', 'usuario', 'canal_venta', 'documento_salida')
    # Filtros laterales para auditar rápido por tipo, fecha o canal
    list_filter = ('tipo', 'fecha', 'canal_venta', 'usuario')
    # Buscador por el SKU del producto relacionado o por documento
    search_fields = ('producto__sku', 'producto__titulo', 'documento_salida', 'proveedor_motivo')

@admin.register(SimulacionMercadoLibre)
class SimulacionMercadoLibreAdmin(admin.ModelAdmin):
    list_display = ('producto', 'cod_publicacion', 'precio_venta', 'ganancia', 'rentabilidad_porc', 'usuario', 'fecha_registro')
    list_filter = ('item_type', 'estado_publicacion', 'tipo_publicacion', 'mpe', 'fecha_registro')
    search_fields = ('producto', 'cod_publicacion', 'cod_producto', 'usuario__username')