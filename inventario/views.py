import json
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .models import Electrodomestico, Plataforma, Producto, MovimientoPercheron

# =========================================================
# 1. EL PRE-LOGIN (Portal público)
# =========================================================
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


# =========================================================
# 2. VISTAS DEL SISTEMA (Post-Login)
# =========================================================

@login_required
def inicio(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/inicio.html', {'canal': canal})

# INVENTARIO GLOBAL: MAGAZZINO
@login_required
def inventario_magazzino(request):
    productos = Electrodomestico.objects.all()  # Aquí podrás filtrar por almacén luego
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/inventario_lista.html', {
        'productos': productos, 
        'canal': canal,
        'nombre_almacen': 'MAGAZZINO'
    })

# =========================================================
# SUBSECCIONES ESPECÍFICAS DEL MÓDULO PERCHERÓN (GLOBALES)
# =========================================================
@login_required
def percheron_inventario(request):
    productos = Electrodomestico.objects.all()  # Filtrar por almacén o lógica global
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_inventario.html', {
        'productos': productos,
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono,
        'nombre_almacen': 'PERCHERON'
    })

@login_required
def percheron_ingresos(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_ingresos.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono
    })

@login_required
def percheron_salidas(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_salidas.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono
    })

@login_required
def percheron_buscador(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_buscador.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono
    })

@login_required
def percheron_consulta_rapida(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_consulta_rapida.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono
    })

@login_required
def percheron_costos_general(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_costos_general.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono
    })

@login_required
def percheron_registros(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    # Jalamos TODOS los movimientos reales ordenados por fecha de la BD
    movimientos = MovimientoPercheron.objects.all()
    
    return render(request, 'inventario/percheron_registros.html', {
        'canal': canal,
        'color_actual': color,
        'icono_actual': icono,
        'movimientos': movimientos
    })

# NUEVA FUNCIÓN PARA GUARDAR LOS DATOS DE LA TABLA ESTILO EXCEL
@login_required
def guardar_kardex_percheron(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('filas', [])
            
            for fila in filas:
                sku = fila.get('sku', '').strip()
                if not sku:
                    continue # Si no hay SKU, saltamos la fila
                
                # 1. Buscamos el producto por SKU. Si no existe, lo creamos con los datos de la celda
                producto, creado = Producto.objects.get_or_create(
                    sku=sku,
                    defaults={
                        'modelo': fila.get('modelo', ''),
                        'marca': fila.get('marca', ''),
                        'titulo': fila.get('titulo', 'Producto sin título'),
                        'codigo_ean': fila.get('ean', ''),
                        'ubicacion': fila.get('ubicacion', ''),
                        'costo_soles': float(fila.get('costo', 0) or 0)
                    }
                )
                
                # Si el producto ya existía, actualizamos sus datos base por si el usuario los editó en el Excel
                if not creado:
                    producto.modelo = fila.get('modelo', producto.modelo)
                    producto.marca = fila.get('marca', producto.marca)
                    producto.titulo = fila.get('titulo', producto.titulo)
                    producto.codigo_ean = fila.get('ean', producto.codigo_ean)
                    producto.ubicacion = fila.get('ubicacion', producto.ubicacion)
                    producto.costo_soles = float(fila.get('costo', 0) or 0)
                    producto.save()
                
                # 2. Procesamos los Movimientos (IN y OUT)
                val_in = int(fila.get('in', 0) or 0)
                val_out = int(fila.get('out', 0) or 0)
                mov_id = fila.get('id') # ID del movimiento si ya existía en la BD
                
                # Determinamos el tipo de movimiento preponderante de la fila
                tipo_mov = 'IN' if val_in > 0 else 'OUT'
                cantidad_mov = val_in if val_in > 0 else val_out
                
                if cantidad_mov > 0:
                    if mov_id:
                        # Si tiene ID, es un movimiento existente que se está editando
                        try:
                            mov = MovimientoPercheron.objects.get(id=mov_id)
                            mov.producto = producto
                            mov.tipo = tipo_mov
                            mov.cantidad = cantidad_mov
                            mov.fecha = fila.get('fecha')
                            mov.serie = fila.get('serie', '')
                            mov.costo_transaccion = float(fila.get('costo', 0) or 0)
                            # Se asume que el campo "proveedor" del excel puede ser Proveedor (IN) o Documento (OUT)
                            mov.proveedor_motivo = fila.get('proveedor', '') if tipo_mov == 'IN' else ''
                            mov.documento_salida = fila.get('proveedor', '') if tipo_mov == 'OUT' else '' 
                            mov.save()
                        except MovimientoPercheron.DoesNotExist:
                            pass
                    else:
                        # Si no tiene ID, es una fila nueva insertada por el usuario. La creamos de cero.
                        canal_activo = request.session.get('canal_activo', 'Web')
                        MovimientoPercheron.objects.create(
                            producto=producto,
                            tipo=tipo_mov,
                            cantidad=cantidad_mov,
                            fecha=fila.get('fecha'),
                            serie=fila.get('serie', ''),
                            costo_transaccion=float(fila.get('costo', 0) or 0),
                            proveedor_motivo=fila.get('proveedor', '') if tipo_mov == 'IN' else '',
                            documento_salida=fila.get('proveedor', '') if tipo_mov == 'OUT' else '',
                            canal_venta=canal_activo if tipo_mov == 'OUT' else '',
                            usuario=request.user
                        )
            
            return JsonResponse({'status': 'ok', 'message': '¡Sincronización con la Base de Datos exitosa!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


# =========================================================
# REPORTES Y HERRAMIENTAS
# =========================================================
@login_required
def reporte_ventas(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/reportes_ventas.html', {'canal': canal})

@login_required
def simulador_costos(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/simulador_costos.html', {'canal': canal})

@login_required
def pantalla_carga(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/loading.html', {'canal': canal})


# =========================================================
# 3. EL CEREBRO: Login Camaleónico
# =========================================================
class LoginCamaleonicoView(LoginView):
    template_name = 'inventario/login.html'
    
    estilos = {
        "Mercado Libre": {"color": "#F1C40F", "icono": "fa-handshake"},
        "Mercado Libre - Junior": {"color": "#F39C12", "icono": "fa-seedling"},
        "Creditienda": {"color": "#E74C3C", "icono": "fa-credit-card"},
        "Falabella": {"color": "#2ECC71", "icono": "fa-store"},
        "Intercorp": {"color": "#2980B9", "icono": "fa-building"},
        "Venta Libre": {"color": "#9B59B6", "icono": "fa-tags"},
        "Tik tok": {"color": "#2C3E50", "icono": "fa-tiktok"},
        "Web": {"color": "#3498DB", "icono": "fa-globe"}
    }

    def get_success_url(self):
        return '/loading/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        canal = self.request.GET.get('canal', 'Web') 
        tema_actual = self.estilos.get(canal, self.estilos["Web"])
        context['nombre_canal'] = canal
        context['color_principal'] = tema_actual['color']
        
        icon_prefix = "fab" if "tiktok" in tema_actual['icono'] else "fas"
        context['icono_canal'] = f"{icon_prefix} {tema_actual['icono']}"
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

        tema = self.estilos.get(canal_solicitado, self.estilos["Web"])
        self.request.session['canal_activo'] = canal_solicitado
        self.request.session['color_actual'] = tema['color']
        
        icon_prefix = "fab" if "tiktok" in tema['icono'] else "fas"
        self.request.session['icono_actual'] = f"{icon_prefix} {tema['icono']}"
        
        return super().form_valid(form)