from django.contrib import admin
from .models import Perfil, Plataforma, Categoria, Electrodomestico

# Registros simples
admin.site.register(Plataforma)
admin.site.register(Categoria)
admin.site.register(Electrodomestico)

# Configuración avanzada para Perfil
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    # 1. Definimos qué columnas se ven en la tabla principal
    # 'usuario' muestra el nombre del empleado
    # 'mostrar_plataformas' ejecutará la función que definimos abajo
    list_display = ('usuario', 'mostrar_plataformas')

    # 2. Añadimos un buscador por nombre de usuario
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')

    # 3. Añadimos un filtro lateral por si quieres ver quién tiene acceso a X plataforma
    list_filter = ('plataformas',)

    # 4. El selector de dos columnas para cuando edites el perfil
    filter_horizontal = ('plataformas',)

    # 5. Función mágica para listar las plataformas en la tabla principal
    def mostrar_plataformas(self, obj):
        # Tomamos todos los nombres de las plataformas y los unimos con un guion
        # Usamos el separador "-" como habías preferido para tus listas
        plataformas = [p.nombre for p in obj.plataformas.all()]
        return " - ".join(plataformas) if plataformas else "Sin plataformas"
    
    # Le ponemos un encabezado elegante a la columna
    mostrar_plataformas.short_description = 'Plataformas Autorizadas'