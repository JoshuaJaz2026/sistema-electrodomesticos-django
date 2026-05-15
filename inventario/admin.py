from django.contrib import admin
from .models import Perfil, Plataforma, Categoria, Electrodomestico

admin.site.register(Plataforma)
admin.site.register(Categoria)
admin.site.register(Electrodomestico)

# Le damos un diseño especial e intuitivo al Perfil
@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    # Esto crea dos columnas hermosas para pasar elementos de un lado a otro
    filter_horizontal = ('plataformas',)