from django.contrib import admin
from .models import Perfil, Plataforma, Categoria, Electrodomestico
from import_export.admin import ImportExportModelAdmin # Librería para carga masiva

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
class PerfilAdmin(ImportExportModelAdmin): # Cambiamos a ImportExportModelAdmin
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
        # Usamos el separador "-" como habías preferido
        plataformas = [p.nombre for p in obj.plataformas.all()]
        return " - ".join(plataformas) if plataformas else "Sin plataformas"
    
    mostrar_plataformas.short_description = 'Plataformas Autorizadas'