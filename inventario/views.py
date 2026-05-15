from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView # Importamos la vista oficial de Login

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

# 2. El Panel Principal (Protegido con contraseña)
@login_required
def inicio(request):
    return render(request, 'inventario/inicio.html')

# 3. EL CEREBRO: Login Camaleónico
class LoginCamaleonicoView(LoginView):
    template_name = 'inventario/login.html'
    
    def get_context_data(self, **kwargs):
        # Esta función prepara los datos antes de enviarlos al HTML
        context = super().get_context_data(**kwargs)
        
        # Atrapamos el nombre de la plataforma desde la URL (ej: ?canal=Falabella)
        canal = self.request.GET.get('canal', 'Web') 
        
        # Nuestro diccionario de temas
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
        
        # Si alguien altera la URL, por seguridad cargamos el estilo "Web" por defecto
        tema_actual = estilos.get(canal, estilos["Web"])
        
        # Empaquetamos las variables para mandarlas al HTML
        context['nombre_canal'] = canal
        context['color_principal'] = tema_actual['color']
        context['icono_canal'] = tema_actual['icono']
        
        return context

    # ------ NUEVO: EL ESCUDO DE SEGURIDAD ACTUALIZADO ------
    def form_valid(self, form):
        usuario = form.get_user() # Obtenemos al usuario que acaba de poner bien su clave
        canal_solicitado = self.request.GET.get('canal', 'Web')

        # Regla 1: El dueño (Superusuario) puede entrar a donde quiera para supervisar
        if usuario.is_superuser:
            return super().form_valid(form)

        # Regla 2: Revisar si la plataforma solicitada está en la lista permitida del empleado
        if hasattr(usuario, 'perfil'):
            # Filtramos en su lista de plataformas para ver si existe la que está solicitando
            permitido = usuario.perfil.plataformas.filter(nombre=canal_solicitado).exists()
            
            if not permitido:
                # Si no está en su lista, arrojamos un error y no lo dejamos entrar
                form.add_error(None, f"Acceso denegado: No tienes permisos para ingresar a {canal_solicitado}.")
                return self.form_invalid(form)
        else:
            # Si es un usuario viejo que no tiene tarjeta asignada
            form.add_error(None, "Acceso denegado: Comunícate con el administrador para que te asigne una plataforma.")
            return self.form_invalid(form)

        # Si todo está bien, lo dejamos pasar
        return super().form_valid(form)