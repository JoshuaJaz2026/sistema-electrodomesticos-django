from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .models import Electrodomestico, Plataforma # Asegúrate de tener tus modelos listos

# 1. El Pre-Login (Portal público)
def selector_plataformas(request):
    plataformas = [
        {"nombre": "Mercado Libre", "icono": "fas fa-handshake", "color": "#F1C40F"},
        {"nombre": "Mercado Libre - Junior", "icono": "fas fa-seedling", "color": "#F39C12"},
        {"nombre": "Creditienda", "icono": "fas fa-credit-card", "color": "#E74C3C"},
        {"nombre": "Falabella", "icono": "fas fa-store", "color": "#2ECC71"},
        {"nombre": "Intercorp", "icono": "fas fa-building", "color": "#2980B9"},
        {"nombre": "Venta Libre", "icono": "fas fa-tags", "color": "#9B59B6"},
        {"nombre": "Tik tok", "icono": "fab fa-tiktok", "color": "#2C3E50"},
        {"nombre": "Web", "icono": "fas fa-globe", "color": "#3498DB"}
    ]
    return render(request, 'inventario/selector.html', {'plataformas': plataformas})

# ---------------------------------------------------------
# 2. VISTAS DEL SISTEMA (Post-Login)
# ---------------------------------------------------------

@login_required
def inicio(request):
    # Recuperamos la plataforma de la sesión para personalizar el inicio
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/inicio.html', {'canal': canal})

# VENTANA GLOBAL: Inventario (Todos ven lo mismo)
@login_required
def inventario_global(request):
    productos = Electrodomestico.objects.all()
    return render(request, 'inventario/inventario.html', {'productos': productos})

# VENTANA PRIVADA: Reporte de Ventas (Filtrado por plataforma)
@login_required
def reporte_ventas(request):
    canal = request.session.get('canal_activo')
    # Aquí filtrarás tus ventas por la plataforma activa
    # ventas = Venta.objects.filter(plataforma__nombre=canal) 
    return render(request, 'inventario/reportes.html', {'canal': canal})

# VENTANA PRIVADA: Simulador de Costos (Único por plataforma)
@login_required
def simulador_costos(request):
    canal = request.session.get('canal_activo')
    return render(request, 'inventario/simulador.html', {'canal': canal})


# ---------------------------------------------------------
# 3. EL CEREBRO: Login Camaleónico
# ---------------------------------------------------------
class LoginCamaleonicoView(LoginView):
    template_name = 'inventario/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        canal = self.request.GET.get('canal', 'Web') 
        
        estilos = {
            "Mercado Libre": {"color": "#F1C40F", "icono": "fas fa-handshake"},
            "Mercado Libre - Junior": {"color": "#F39C12", "icono": "fas fa-seedling"},
            "Creditienda": {"color": "#E74C3C", "icono": "fas fa-credit-card"},
            "Falabella": {"color": "#2ECC71", "icono": "fas fa-store"},
            "Intercorp": {"color": "#2980B9", "icono": "fas fa-building"},
            "Venta Libre": {"color": "#9B59B6", "icono": "fas fa-tags"},
            "Tik tok": {"color": "#2C3E50", "icono": "fab fa-tiktok"},
            "Web": {"color": "#3498DB", "icono": "fas fa-globe"}
        }
        
        tema_actual = estilos.get(canal, estilos["Web"])
        context['nombre_canal'] = canal
        context['color_principal'] = tema_actual['color']
        context['icono_canal'] = tema_actual['icono']
        return context

    def form_valid(self, form):
        usuario = form.get_user()
        canal_solicitado = self.request.GET.get('canal', 'Web')

        if not usuario.is_superuser:
            if hasattr(usuario, 'perfil'):
                permitido = usuario.perfil.plataformas.filter(nombre=canal_solicitado).exists()
                if not permitido:
                    form.add_error(None, f"Acceso denegado: Tu usuario no tiene permiso para {canal_solicitado}.")
                    return self.form_invalid(form)
            else:
                form.add_error(None, "Usuario sin perfil asignado.")
                return self.form_invalid(form)

        # GUARDAMOS EL CANAL EN LA SESIÓN: 
        # Esto permite que las demás ventanas sepan de qué plataforma viene el usuario
        self.request.session['canal_activo'] = canal_solicitado
        
        return super().form_valid(form)