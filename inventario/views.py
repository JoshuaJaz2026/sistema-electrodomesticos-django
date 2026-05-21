import json
import uuid
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
    productos = Electrodomestico.objects.all()
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/inventario_lista.html', {
        'productos': productos, 
        'canal': canal,
        'nombre_almacen': 'MAGAZZINO'
    })


# =========================================================
# 3. SECCIÓN PERCHERÓN: GLOBALES
# =========================================================
@login_required
def percheron_ingresos(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    movimientos_in = MovimientoPercheron.objects.filter(tipo='IN')
    
    return render(request, 'inventario/percheron_ingresos.html', {
        'canal': canal, 'color_actual': color, 'icono_actual': icono, 'movimientos': movimientos_in
    })

@login_required
def percheron_registros(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    movimientos = MovimientoPercheron.objects.all()
    
    return render(request, 'inventario/percheron_registros.html', {
        'canal': canal, 'color_actual': color, 'icono_actual': icono, 'movimientos': movimientos
    })

@login_required
def percheron_modelos(request):
    canal = request.session.get('canal_activo', 'Web')
    color = request.session.get('color_actual', '#3498DB')
    icono = request.session.get('icono_actual', 'fas fa-globe')
    
    return render(request, 'inventario/percheron_modelos.html', {
        'canal': canal, 'color_actual': color, 'icono_actual': icono
    })

# =========================================================
# 4. SECCIÓN PERCHERÓN: PLATAFORMAS ESPECÍFICAS
# =========================================================
@login_required
def percheron_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_mercadolibre.html', {'canal': canal})

@login_required
def percheron_mercadolibre_junior(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_mercadolibre_junior.html', {'canal': canal})

@login_required
def percheron_falabella(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_falabella.html', {'canal': canal})

@login_required
def percheron_creditienda(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_creditienda.html', {'canal': canal})

@login_required
def percheron_intercorp(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_intercorp.html', {'canal': canal})

@login_required
def percheron_tiktok(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_tiktok.html', {'canal': canal})

@login_required
def percheron_ventalibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_ventalibre.html', {'canal': canal})

@login_required
def percheron_bci(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/percheron_bci.html', {'canal': canal})

# =========================================================
# 5. APIs Y BASES DE DATOS (GUARDADO Y BÚSQUEDA)
# =========================================================

def api_buscar_producto(request):
    sku = request.GET.get('sku', '').strip()
    if not sku:
        return JsonResponse({'status': 'error', 'message': 'SKU vacío'})
    try:
        producto = Producto.objects.get(sku=sku)
        return JsonResponse({
            'status': 'ok',
            'modelo': producto.modelo,
            'titulo': producto.titulo,
            'marca': producto.marca,
            'codigo_ean': producto.codigo_ean,
            'costo_soles': producto.costo_soles,
        })
    except Producto.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Producto no encontrado'})

def guardar_nuevos_productos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            productos = data.get('productos', [])
            creados, actualizados = 0, 0

            for p in productos:
                obj, created = Producto.objects.update_or_create(
                    sku=p['sku'],
                    defaults={
                        'modelo': p.get('modelo', ''),
                        'marca': p.get('marca', ''),
                        'titulo': p.get('titulo', ''),
                        'codigo_ean': p.get('ean', ''),
                        'ubicacion': p.get('ubicacion', ''),
                        'costo_dolares': p.get('costo_dolares') or 0.00,
                        'costo_soles': p.get('costo_soles') or 0.00,
                    }
                )
                if created: creados += 1
                else: actualizados += 1
            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! {creados} creados, {actualizados} actualizados.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

@login_required
def guardar_kardex_percheron(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('filas', [])
            
            for fila in filas:
                sku = fila.get('sku', '').strip()
                val_in = int(fila.get('in', 0) or 0)
                val_out = int(fila.get('out', 0) or 0)
                modelo = fila.get('modelo', '').strip()
                titulo = fila.get('titulo', '').strip()
                
                if not sku:
                    sku = f"SIN-SKU-{uuid.uuid4().hex[:6].upper()}"
                
                producto, creado = Producto.objects.get_or_create(
                    sku=sku,
                    defaults={
                        'modelo': modelo,
                        'marca': fila.get('marca', ''),
                        'titulo': titulo if titulo else 'Fila en blanco',
                        'codigo_ean': fila.get('ean', ''),
                        'ubicacion': fila.get('ubicacion', ''),
                        'costo_soles': float(fila.get('costo', 0) or 0)
                    }
                )
                
                if not creado:
                    producto.modelo = modelo if modelo else producto.modelo
                    producto.marca = fila.get('marca', producto.marca)
                    producto.titulo = titulo if titulo else producto.titulo
                    producto.codigo_ean = fila.get('ean', producto.codigo_ean)
                    producto.ubicacion = fila.get('ubicacion', producto.ubicacion)
                    producto.costo_soles = float(fila.get('costo', 0) or 0)
                    producto.save()
                
                mov_id = fila.get('id')
                tipo_mov = 'IN' if val_in > 0 else 'OUT'
                cantidad_mov = val_in if val_in > 0 else val_out
                
                if cantidad_mov == 0 and not mov_id:
                     tipo_mov = 'IN'
                
                if mov_id:
                    try:
                        mov = MovimientoPercheron.objects.get(id=mov_id)
                        mov.producto = producto
                        mov.tipo = tipo_mov
                        mov.cantidad = cantidad_mov
                        mov.fecha = fila.get('fecha')
                        mov.serie = fila.get('serie', '')
                        mov.costo_transaccion = float(fila.get('costo', 0) or 0)
                        mov.proveedor_motivo = fila.get('proveedor', '') if tipo_mov == 'IN' else ''
                        mov.documento_salida = fila.get('proveedor', '') if tipo_mov == 'OUT' else '' 
                        mov.save()
                    except MovimientoPercheron.DoesNotExist:
                        pass
                else:
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

@login_required
def api_guardar_simulador(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plataforma = data.get('plataforma', 'Desconocida')
            datos_simulacion = data.get('datos', [])
            
            # Por ahora, solo imprimimos en la terminal para verificar que llegan los datos
            print(f"--- NUEVA SIMULACIÓN DE {plataforma.upper()} ---")
            print(f"Se recibieron {len(datos_simulacion)} filas para simular.")
            
            # Aquí irá la lógica futura para guardar en models.py
            
            return JsonResponse({
                'status': 'ok', 
                'message': f'Simulación de {plataforma} recibida correctamente (Backend en construcción).'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# =========================================================
# 6. REPORTES DE VENTAS POR PLATAFORMA
# =========================================================

@login_required
def reporte_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_mercadolibre.html', {'canal': canal})

@login_required
def reporte_mercadolibre_junior(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_mercadolibre_junior.html', {'canal': canal})

@login_required
def reporte_creditienda(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_creditienda.html', {'canal': canal})

@login_required
def reporte_falabella(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_falabella.html', {'canal': canal})

@login_required
def reporte_intercorp(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_intercorp.html', {'canal': canal})

@login_required
def reporte_tiktok(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_tiktok.html', {'canal': canal})

@login_required
def reporte_ventalibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_ventalibre.html', {'canal': canal})

@login_required
def reporte_web(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'reportes_plataformas/reporte_web.html', {'canal': canal})


# =========================================================
# 7. SIMULADORES DE COSTOS POR PLATAFORMA
# =========================================================

@login_required
def simulador_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_mercadolibre.html', {'canal': canal})

@login_required
def simulador_mercadolibre_junior(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_mercadolibre_junior.html', {'canal': canal})

@login_required
def simulador_creditienda(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_creditienda.html', {'canal': canal})

@login_required
def simulador_falabella(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_falabella.html', {'canal': canal})

@login_required
def simulador_intercorp(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_intercorp.html', {'canal': canal})

@login_required
def simulador_tiktok(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_tiktok.html', {'canal': canal})

@login_required
def simulador_ventalibre(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_ventalibre.html', {'canal': canal})

@login_required
def simulador_web(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'simuladores_plataformas/simulador_web.html', {'canal': canal})

@login_required
def pantalla_carga(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/loading.html', {'canal': canal})


# =========================================================
# 8. EL CEREBRO: Login Camaleónico
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