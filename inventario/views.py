import json
import uuid
import csv
import os
from datetime import datetime
from functools import wraps
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# Importación corregida de SimulacionMercadoLibreJunior
from .models import Electrodomestico, Plataforma, Producto, MovimientoPercheron, SimulacionMercadoLibre, ReferenciaComision, ReferenciaCosto, ReporteMercadoLibre, IngresoPercheron, SalidaMercadoLibre, ReporteMercadoLibreJunior, SimulacionMercadoLibreJunior, SalidaMercadoLibreJunior, SimulacionMercadoLibreJunior, SalidaMercadoLibreJunior, SalidaFalabella, SalidaCreditienda, SalidaIntercorp, SalidaTiktok, SalidaVentaLibre, ReporteCreditienda, ReporteFalabella, DirectorioProducto, ReporteIntercorp, ComisionIntercorp

# =========================================================
# CONFIGURACIÓN MAESTRA DE ESTILOS Y COLORES
# =========================================================
ESTILOS_PLATAFORMAS = {
    "Mercado Libre": {"color": "#F1C40F", "icono": "fa-handshake"},
    "Mercado Libre - Junior": {"color": "#F39C12", "icono": "fa-seedling"},
    "Creditienda": {"color": "#E74C3C", "icono": "fa-credit-card"},
    "Falabella": {"color": "#2ECC71", "icono": "fa-store"},
    "Intercorp": {"color": "#2980B9", "icono": "fa-building"},
    "Venta Libre": {"color": "#9B59B6", "icono": "fa-tags"},
    "Tik tok": {"color": "#2C3E50", "icono": "fa-tiktok"},
    "Web": {"color": "#3498DB", "icono": "fa-globe"}
}

# =========================================================
# EL GUARDIA DE SEGURIDAD (DECORADOR RBAC)
# =========================================================
def verificar_acceso_plataforma(*plataformas_requeridas):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            tiene_permiso = False
            plataforma_detectada = None
            
            # Superusuario tiene acceso total a todo
            if request.user.is_superuser:
                tiene_permiso = True
                plataforma_detectada = plataformas_requeridas[0]
            # Revisar si el perfil tiene el acceso a alguna de las plataformas requeridas
            elif hasattr(request.user, 'perfil'):
                for plat in plataformas_requeridas:
                    if request.user.perfil.plataformas.filter(nombre=plat).exists():
                        tiene_permiso = True
                        plataforma_detectada = plat
                        break
                        
            if tiene_permiso:
                # Actualiza automáticamente la plataforma activa si el usuario cambia de menú
                canal_actual = request.session.get('canal_activo')
                if canal_actual not in plataformas_requeridas:
                    request.session['canal_activo'] = plataforma_detectada
                    tema = ESTILOS_PLATAFORMAS.get(plataforma_detectada, ESTILOS_PLATAFORMAS["Web"])
                    request.session['color_actual'] = tema['color']
                    prefix = "fab" if "tiktok" in tema['icono'].lower() else "fas"
                    request.session['icono_actual'] = f"{prefix} {tema['icono']}"
                
                return view_func(request, *args, **kwargs)
            
            # BLOQUEO Y EXPULSIÓN SI NO TIENE PERMISO
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Acceso denegado.'}, status=403)
            
            nombres = " o ".join(plataformas_requeridas)
            messages.error(request, f"⚠️ Acceso denegado: Tu perfil no tiene autorización para {nombres}.")
            return redirect('inicio')
        return _wrapped_view
    return decorator


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
# 8. EL CEREBRO: Login Camaleónico (Movido aquí para orden)
# =========================================================
class LoginCamaleonicoView(LoginView):
    template_name = 'inventario/login.html'

    def get_success_url(self):
        return '/loading/'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        canal = self.request.GET.get('canal', 'Web') 
        tema_actual = ESTILOS_PLATAFORMAS.get(canal, ESTILOS_PLATAFORMAS["Web"])
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

        tema = ESTILOS_PLATAFORMAS.get(canal_solicitado, ESTILOS_PLATAFORMAS["Web"])
        self.request.session['canal_activo'] = canal_solicitado
        self.request.session['color_actual'] = tema['color']
        icon_prefix = "fab" if "tiktok" in tema['icono'] else "fas"
        self.request.session['icono_actual'] = f"{icon_prefix} {tema['icono']}"
        
        return super().form_valid(form)


# =========================================================
# 2. VISTAS DEL SISTEMA (Post-Login)
# =========================================================

@login_required
def inicio(request):
    canal = request.session.get('canal_activo', 'Web')
    
    # variables por defecto por si entra a otra plataforma vacía
    ventas_totales = 0
    progreso_meta = 0
    categorias_nombres = []
    categorias_cantidades = []
    stock_labels = ['Sin datos']
    stock_data = [100]
    crecimiento_porc = 0
    tendencia_crecimiento = [0,0,0,0,0,0,0]
    clientes_promedio = 0
    tendencia_clientes = [0,0,0,0,0,0,0]
    tasa_devoluciones = 0
    tendencia_devoluciones = [0,0,0,0,0,0,0]

    if canal == 'Mercado Libre':
        hoy = timezone.now().date()
        inicio_mes = hoy.replace(day=1)
        
        # 1. ventas totales del mes
        ventas_mes = ReporteMercadoLibre.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy
        ).aggregate(total=Sum('cantidad'))
        ventas_totales = int(ventas_mes['total'] or 0)
        
        # meta del mes (puedes cambiar este 1000 por lo que te pida tu jefe)
        meta_mensual = 1000
        progreso_meta = min(int((ventas_totales / meta_mensual) * 100), 100) if ventas_totales > 0 else 0

        # 2. top 5 categorías más vendidas
        ventas_por_categoria = ReporteMercadoLibre.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy
        ).values('categoria').annotate(
            total_vendido=Sum('cantidad')
        ).order_by('-total_vendido')[:5]
        
        categorias_nombres = [v['categoria'] or 'Sin Cat' for v in ventas_por_categoria]
        categorias_cantidades = [float(v['total_vendido']) for v in ventas_por_categoria]

        # 3. distribución de stock (cruza con maestro percherón)
        stock_activo = Producto.objects.filter(activo_ml=True, stock_actual__gt=0).count()
        stock_agotado = Producto.objects.filter(activo_ml=True, stock_actual__lte=0).count()
        stock_labels = ['Con Stock (ML)', 'Agotados (ML)']
        stock_data = [stock_activo, stock_agotado]

        # 4. cálculo de tendencias de los últimos 7 días
        tendencia_crecimiento = []
        tendencia_clientes = []
        
        for i in range(6, -1, -1):
            dia = hoy - timedelta(days=i)
            
            # ventas por día para la gráfica 1
            v_dia = ReporteMercadoLibre.objects.filter(fecha=dia).aggregate(total=Sum('cantidad'))['total'] or 0
            tendencia_crecimiento.append(int(v_dia))
            
            # clientes únicos por día (usamos el celular para no repetir al mismo cliente)
            c_dia = ReporteMercadoLibre.objects.filter(fecha=dia).exclude(celular='').values('celular').distinct().count()
            tendencia_clientes.append(c_dia)
            
        # 5. porcentaje de crecimiento vs mes pasado
        try:
            inicio_mes_pasado = (inicio_mes - timedelta(days=1)).replace(day=1)
            fin_mes_pasado = inicio_mes - timedelta(days=1)
            ventas_pasadas = ReporteMercadoLibre.objects.filter(
                fecha__gte=inicio_mes_pasado, fecha__lte=fin_mes_pasado
            ).aggregate(total=Sum('cantidad'))['total'] or 0
            
            if ventas_pasadas > 0:
                crecimiento_porc = int(((ventas_totales - ventas_pasadas) / ventas_pasadas) * 100)
            else:
                crecimiento_porc = 100 if ventas_totales > 0 else 0
        except:
            pass

        # 6. promedio de clientes diarios
        dias_transcurridos = hoy.day
        total_clientes_mes = ReporteMercadoLibre.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy
        ).exclude(celular='').values('celular').distinct().count()
        clientes_promedio = int(total_clientes_mes / dias_transcurridos) if dias_transcurridos > 0 else 0

    context = {
        'canal': canal,
        'ventas_totales': ventas_totales,
        'progreso_meta': progreso_meta,
        'categorias_nombres_json': json.dumps(categorias_nombres),
        'categorias_cantidades_json': json.dumps(categorias_cantidades),
        'stock_labels_json': json.dumps(stock_labels),
        'stock_data_json': json.dumps(stock_data),
        'crecimiento_porc': crecimiento_porc,
        'tendencia_crecimiento_json': json.dumps(tendencia_crecimiento),
        'clientes_promedio': clientes_promedio,
        'tendencia_clientes_json': json.dumps(tendencia_clientes),
        'tasa_devoluciones': tasa_devoluciones,
        'tendencia_devoluciones_json': json.dumps(tendencia_devoluciones)
    }
    
    return render(request, 'inventario/inicio.html', context)

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
    canal = request.session.get('canal_activo', 'Percheron')
    
    registros_lista = IngresoPercheron.objects.all().order_by('id')
    paginator = Paginator(registros_lista, 100) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    productos_db = Producto.objects.all()
    dict_titulos = {p.modelo: p.titulo for p in productos_db if p.modelo}

    return render(request, 'inventario/percheron_ingresos.html', {
        'canal': canal,
        'page_obj': page_obj,
        'titulos_json': json.dumps(dict_titulos) 
    })


@login_required
def percheron_registros(request):
    canal = request.session.get('canal_activo', 'Percheron')
    
    ingresos_db = IngresoPercheron.objects.all().order_by('id')
    productos_db = Producto.objects.all()
    dict_productos = {p.modelo: p for p in productos_db if p.modelo}
    
    # === RECOPILACIÓN MASIVA DE TODAS LAS PLATAFORMAS ===
    out_ml_qs = SalidaMercadoLibre.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_ml = {s['sku']: s['total'] for s in out_ml_qs if s['sku']}
    
    out_ml_jr_qs = SalidaMercadoLibreJunior.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_ml_jr = {s['sku']: s['total'] for s in out_ml_jr_qs if s['sku']}

    out_fbl_qs = SalidaFalabella.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_fbl = {s['sku']: s['total'] for s in out_fbl_qs if s['sku']}

    out_cdt_qs = SalidaCreditienda.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_cdt = {s['sku']: s['total'] for s in out_cdt_qs if s['sku']}

    out_int_qs = SalidaIntercorp.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_int = {s['sku']: s['total'] for s in out_int_qs if s['sku']}

    out_tk_qs = SalidaTiktok.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_tk = {s['sku']: s['total'] for s in out_tk_qs if s['sku']}

    out_vl_qs = SalidaVentaLibre.objects.values('sku').annotate(total=Sum('descuento'))
    dict_out_vl = {s['sku']: s['total'] for s in out_vl_qs if s['sku']}
    
    registros_data = []
    
    for ing in ingresos_db:
        prod = dict_productos.get(ing.modelo)
        
        marca_val = prod.marca if prod else 'SIN MARCA'
        ubicacion_val = prod.ubicacion if prod else 'SIN UBICACIÓN'
        
        # Asignar salidas extraídas por plataforma
        out_ml = dict_out_ml.get(ing.sku, 0)
        out_ml2 = dict_out_ml_jr.get(ing.sku, 0)
        out_fbl = dict_out_fbl.get(ing.sku, 0)
        out_cdt = dict_out_cdt.get(ing.sku, 0)
        out_intcp = dict_out_int.get(ing.sku, 0)
        out_tk = dict_out_tk.get(ing.sku, 0)
        out_vl = dict_out_vl.get(ing.sku, 0)
        
        # Balance Final Automático
        total_out = out_ml + out_fbl + out_cdt + out_vl + out_tk + out_intcp + out_ml2
        stock_val = ing.cantidad - total_out
        
        registros_data.append({
            'sku': ing.sku,
            'marca': marca_val,
            'fecha_ingreso': ing.fecha_ingreso,
            'codigo_ean': ing.codigo_ean,
            'serie_nro': ing.serie_nro,
            'costo_unitario': ing.costo_unitario,
            'proveedor': ing.proveedor_motivo,
            'ubicacion': ubicacion_val,
            'registrado_por': ing.creado_por,
            'modelo': ing.modelo,
            'titulo': ing.titulo,
            'in_cant': ing.cantidad,
            'out_ml': out_ml,
            'out_fbl': out_fbl,
            'out_cdt': out_cdt,
            'out_vl': out_vl,
            'out_tk': out_tk,
            'out_intcp': out_intcp,
            'out_ml2': out_ml2,
            'stock': stock_val
        })
        
    paginator = Paginator(registros_data, 100) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventario/percheron_registros.html', {
        'canal': canal,
        'page_obj': page_obj
    })

@login_required
def percheron_modelos(request):
    canal = request.session.get('canal_activo', 'Percheron')
    query_search = request.GET.get('q', '')
    
    if query_search:
        modelos_db = Producto.objects.filter(
            modelo__icontains=query_search
        ).order_by('id')
    else:
        modelos_db = Producto.objects.all().order_by('id')
    
    paginator = Paginator(modelos_db, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventario/percheron_modelos.html', {
        'canal': canal,
        'page_obj': page_obj,
        'query_search': query_search
    })


@login_required
def exportar_registros_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Kardex_Maestro_Registros.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    
    writer.writerow([
        'SKU', 'MARCA', 'FECHA ING', 'CÓDIGO EAN', 'NRO. SERIE', 
        'COSTO', 'PROVEEDOR', 'UBICACIÓN (DEP/PROV/DIST)', 'REGIST. POR', 
        'MODELO', 'TITULO', 'IN', 'OUT (ML)', 'OUT (FBL)', 'OUT (CDT)', 
        'OUT (VL)', 'OUT (TK)', 'OUT (INTCP)', 'OUT (ML 2)', 'STOCK'
    ])
    
    registros = []
    for r in registros:
        pass
        
    return response

# =========================================================
# 4. SECCIÓN PERCHERÓN: PLATAFORMAS ESPECÍFICAS PROTEGIDAS
# =========================================================

@login_required
@verificar_acceso_plataforma('Mercado Libre')
def percheron_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Mercado Libre')
    
    skus_usados = SalidaMercadoLibre.objects.values_list('sku', flat=True)
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
    
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_skus = {}
    for ing in ingresos_db:
        mod_limpio = str(ing.modelo).strip().upper() if ing.modelo else ''
        prod = dict_prods.get(mod_limpio)
        marca_val = prod.marca if prod else 'S/N MARCA'
        stock_val = prod.stock_actual if prod else 0
        
        fecha_str = '-'
        if ing.fecha_ingreso:
            try: fecha_str = ing.fecha_ingreso.strftime('%d/%m/%Y')
            except: fecha_str = str(ing.fecha_ingreso)

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': ing.titulo or '', 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }
        
    page_obj = SalidaMercadoLibre.objects.all().order_by('-id')

    return render(request, 'inventario/percheron_mercadolibre.html', {
        'canal': canal,
        'skus_json': json.dumps(dict_skus),
        'page_obj': page_obj 
    })

@login_required
@verificar_acceso_plataforma('Mercado Libre - Junior')
def percheron_mercadolibre_junior(request):
    canal = request.session.get('canal_activo', 'Mercado Libre - Junior')
    
    skus_usados = SalidaMercadoLibreJunior.objects.values_list('sku', flat=True)
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
    
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_skus = {}
    for ing in ingresos_db:
        mod_limpio = str(ing.modelo).strip().upper() if ing.modelo else ''
        prod = dict_prods.get(mod_limpio)
        marca_val = prod.marca if prod else 'S/N MARCA'
        stock_val = prod.stock_actual if prod else 0
        
        fecha_str = '-'
        if ing.fecha_ingreso:
            try: fecha_str = ing.fecha_ingreso.strftime('%d/%m/%Y')
            except: fecha_str = str(ing.fecha_ingreso)

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': ing.titulo or '', 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }
        
    page_obj = SalidaMercadoLibreJunior.objects.all().order_by('-id')

    return render(request, 'inventario/percheron_mercadolibre_junior.html', {
        'canal': canal,
        'skus_json': json.dumps(dict_skus),
        'page_obj': page_obj 
    })

@login_required
@verificar_acceso_plataforma('Falabella')
def percheron_falabella(request):
    canal = request.session.get('canal_activo')
    return render(request, 'inventario/percheron_falabella.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Creditienda')
def percheron_creditienda(request):
    canal = request.session.get('canal_activo')
    return render(request, 'inventario/percheron_creditienda.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Intercorp')
def percheron_intercorp(request):
    canal = request.session.get('canal_activo')
    usuarios_bci = User.objects.all() 
    return render(request, 'inventario/percheron_intercorp.html', {
        'canal': canal,
        'usuarios': usuarios_bci
    })

@login_required
@verificar_acceso_plataforma('Tik tok', 'Tiktok')
def percheron_tiktok(request):
    canal = request.session.get('canal_activo')
    return render(request, 'inventario/percheron_tiktok.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Venta Libre')
def percheron_ventalibre(request):
    canal = request.session.get('canal_activo')
    return render(request, 'inventario/percheron_ventalibre.html', {'canal': canal})

@login_required
def percheron_bci(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso exclusivo para BCI Autorizados.")
        return redirect('inicio')
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
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
def api_guardar_simulador(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            plataforma = data.get('plataforma', 'Desconocida')
            datos_simulacion = data.get('datos', [])
            
            if plataforma == 'Mercado Libre':
                for fila in datos_simulacion:
                    p_venta = float(fila.get('p_venta') or 0)
                    envio = float(fila.get('envio') or 0)
                    porc_com = float(fila.get('porc_comision') or 0)
                    costo = float(fila.get('costo') or 0)
                    
                    com_soles = p_venta * (porc_com / 100)
                    pago_neto = p_venta - com_soles - envio
                    ganancia = pago_neto - costo
                    rentabilidad = (ganancia / p_venta * 100) if p_venta > 0 else 0

                    cod_pub = fila.get('cod_pub', '').strip()

                    datos_diccionario = {
                        'item_type': fila.get('item_type', ''),
                        'link': fila.get('link', ''),
                        'estado_publicacion': fila.get('estado', ''),
                        'tipo_publicacion': fila.get('tipo', ''),
                        'cod_producto': fila.get('cod_prod', ''),
                        'categoria': fila.get('categoria', ''),
                        'marca': fila.get('marca', ''),
                        'producto': fila.get('producto', ''),
                        'precio_tachado': float(fila.get('p_tachado') or 0),
                        'porc_descuento': float(fila.get('dscto') or 0),
                        'precio_venta': p_venta,
                        'costo_envio': envio,
                        'porc_comision': porc_com,
                        'comision_soles': com_soles,
                        'pago_neto': pago_neto,
                        'costo_producto': costo,
                        'ganancia': ganancia,
                        'rentabilidad_porc': rentabilidad,
                        'mpe': fila.get('mpe', False)
                    }

                    if cod_pub:
                        SimulacionMercadoLibre.objects.update_or_create(
                            usuario=request.user,
                            cod_publicacion=cod_pub,
                            defaults=datos_diccionario
                        )
                    else:
                        SimulacionMercadoLibre.objects.create(
                            usuario=request.user,
                            cod_publicacion='',
                            **datos_diccionario
                        )
            
            return JsonResponse({'status': 'ok', 'message': 'Simulación guardada/actualizada exitosamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# =========================================================
# 6. REPORTES DE VENTAS POR PLATAFORMA
# =========================================================

@login_required
@verificar_acceso_plataforma('Mercado Libre')
def reporte_mercadolibre(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    ventas_todas = ReporteMercadoLibre.objects.all().order_by('fecha', 'id')

    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(nro_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search)
        )
    
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha__lte=fecha_fin)

    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- CAMBIO APLICADO: CONEXIÓN AL DIRECTORIO DE PRODUCTOS ---
    directorio_db = DirectorioProducto.objects.all()
    diccionario_productos = {str(d.codigo).strip().upper(): d.producto for d in directorio_db if d.codigo}
    diccionario_productos_json = json.dumps(diccionario_productos)

    return render(request, 'reportes_plataformas/reporte_mercadolibre.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': diccionario_productos_json
    })

@login_required
@verificar_acceso_plataforma('Mercado Libre - Junior')
def reporte_mercadolibre_junior(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    ventas_todas = ReporteMercadoLibreJunior.objects.all().order_by('fecha', 'id')

    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(nro_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search)
        )
    
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha__lte=fecha_fin)

    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # --- CAMBIO APLICADO: CONEXIÓN AL DIRECTORIO DE PRODUCTOS ---
    directorio_db = DirectorioProducto.objects.all()
    diccionario_productos = {str(d.codigo).strip().upper(): d.producto for d in directorio_db if d.codigo}
    diccionario_productos_json = json.dumps(diccionario_productos)

    return render(request, 'reportes_plataformas/reporte_mercadolibre_junior.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': diccionario_productos_json
    })

@login_required
@verificar_acceso_plataforma('Creditienda')
def reporte_creditienda(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    ventas_todas = ReporteCreditienda.objects.all().order_by('-fecha_venta', '-id')

    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(nro_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search) |
            Q(cliente__icontains=query_search)
        )
    
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha_venta__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha_venta__lte=fecha_fin)

    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    costos_db = ReferenciaCosto.objects.all()
    diccionario_productos = {str(c.codigo).strip().upper(): c.producto for c in costos_db if c.codigo}

    return render(request, 'reportes_plataformas/reporte_creditienda.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': json.dumps(diccionario_productos)
    })

@login_required
@verificar_acceso_plataforma('Falabella')
def reporte_falabella(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    ventas_todas = ReporteFalabella.objects.all().order_by('-fecha', '-id')

    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(nro_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search) |
            Q(boleta_factura__icontains=query_search)
        )
    
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha__lte=fecha_fin)

    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    directorio_db = DirectorioProducto.objects.all()
    diccionario_productos = {str(d.codigo).strip().upper(): d.producto for d in directorio_db if d.codigo}

    return render(request, 'reportes_plataformas/reporte_falabella.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': json.dumps(diccionario_productos)
    })

@login_required
@verificar_acceso_plataforma('Intercorp')
def reporte_intercorp(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    ventas_todas = ReporteIntercorp.objects.all().order_by('-fecha', '-id')

    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(id_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search) |
            Q(comprobante_venta__icontains=query_search)
        )
    
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha__lte=fecha_fin)

    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    directorio_db = DirectorioProducto.objects.all()
    diccionario_productos = {
        str(d.codigo).strip().upper(): {
            'producto': d.producto,
            'costo': float(d.costo)
        } for d in directorio_db if d.codigo
    }

    diccionario_comisiones = {}
    try:
        from .models import ComisionIntercorp
        comisiones_db = ComisionIntercorp.objects.all()
        diccionario_comisiones = {str(c.categoria).strip().upper(): float(c.porcentaje) for c in comisiones_db if c.categoria}
    except:
        pass

    return render(request, 'reportes_plataformas/reporte_intercorp.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': json.dumps(diccionario_productos),
        'diccionario_comisiones_json': json.dumps(diccionario_comisiones)
    })

@login_required
def descargar_plantilla_reporte_intercorp(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_intercorp.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'SITIO', 'FECHA', 'MES Y AÑO', 'ID ORDEN', 'COMPROBANTE DE VENTA', 
        'SKU ALMACÉN', 'MARCA', 'CATEGORIA', 'CÓDIGO', 'PRODUCTO', 
        'UND.', 'P. DE VENTA', 'COSTO DE ENVÍO', 'MONTO TOTAL FACTURABLE', 
        'IMPUESTO', 'COBRO LOGÍSTICO', 'COSTO DE PROD.', 'GANANCIA', 
        'MONTO A PAGAR', 'FECHA DE PAGO', 'ID LIQUIDACION', 'ESTADO DE PAGO', 
        'ID DE PAGO', 'VALIDACIÓN'
    ])
    return response

@login_required
@csrf_exempt
def borrar_todos_los_reportes_intercorp(request):
    if request.method == 'POST':
        ReporteIntercorp.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': 'limpiado con exito'})
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})

@login_required
def guardar_reportes_masivos_intercorp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ReporteIntercorp.objects.filter(id__in=eliminadas).delete()

            def parse_date(date_str):
                ds = str(date_str).strip()
                if not ds: return None
                try:
                    if '/' in ds: return datetime.strptime(ds, '%d/%m/%Y').strftime('%Y-%m-%d')
                    elif '-' in ds: return datetime.strptime(ds, '%Y-%m-%d').strftime('%Y-%m-%d')
                except: return None
                return ds

            def to_float(val):
                try: return float(str(val).replace('S/', '').replace('%', '').replace(',', '').strip() or 0)
                except: return 0.00
                
            def to_int(val):
                try: return int(float(str(val).strip() or 0))
                except: return 0

            def parse_bool(val):
                if isinstance(val, bool): return val
                if str(val).lower() in ['true', '1', 'si', 'sí', 'on']: return True
                return False

            objetos_a_guardar = []
            
            for fila in filas:
                id_orden = str(fila.get('ID ORDEN', '')).strip()
                if not id_orden: continue

                obj = ReporteIntercorp(
                    usuario=request.user,
                    sitio=str(fila.get('SITIO', '')).strip(),
                    fecha=parse_date(fila.get('FECHA')),
                    mes_ano=str(fila.get('MES Y AÑO', '')).strip(),
                    id_orden=id_orden,
                    comprobante_venta=str(fila.get('COMPROBANTE DE VENTA', '')).strip(),
                    sku_almacen=str(fila.get('SKU ALMACÉN', '')).strip(),
                    marca=str(fila.get('MARCA', '')).strip(),
                    categoria=str(fila.get('CATEGORIA', '')).strip(),
                    codigo=str(fila.get('CÓDIGO', '')).strip(),
                    producto=str(fila.get('PRODUCTO', '')).strip(),
                    und=to_int(fila.get('UND.', 1)),
                    p_venta=to_float(fila.get('P. DE VENTA')),
                    costo_envio=to_float(fila.get('COSTO DE ENVÍO')),
                    monto_total_facturable=to_float(fila.get('MONTO TOTAL FACTURABLE')),
                    impuesto=to_float(fila.get('IMPUESTO')),
                    cobro_logistico=to_float(fila.get('COBRO LOGÍSTICO')),
                    costo_prod=to_float(fila.get('COSTO DE PROD.')),
                    ganancia=to_float(fila.get('GANANCIA')),
                    monto_a_pagar=to_float(fila.get('MONTO A PAGAR')),
                    fecha_pago=parse_date(fila.get('FECHA DE PAGO')),
                    id_liquidacion=str(fila.get('ID LIQUIDACION', '')).strip(),
                    estado_pago=str(fila.get('ESTADO DE PAGO', '')).strip(),
                    id_pago=str(fila.get('ID DE PAGO', '')).strip(),
                    validacion='SI' if parse_bool(fila.get('VALIDACIÓN')) else 'NO'
                )
                objetos_a_guardar.append(obj)

            if objetos_a_guardar:
                ids = [o.id_orden for o in objetos_a_guardar]
                ReporteIntercorp.objects.filter(id_orden__in=ids).delete()
                ReporteIntercorp.objects.bulk_create(objetos_a_guardar)

            return JsonResponse({'status': 'ok', 'message': 'guardado'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'error de metodo'})

@login_required
@verificar_acceso_plataforma('Tik tok', 'Tiktok')
def reporte_tiktok(request):
    canal = request.session.get('canal_activo')
    return render(request, 'reportes_plataformas/reporte_tiktok.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Venta Libre')
def reporte_ventalibre(request):
    canal = request.session.get('canal_activo')
    return render(request, 'reportes_plataformas/reporte_ventalibre.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Web')
def reporte_web(request):
    canal = request.session.get('canal_activo')
    return render(request, 'reportes_plataformas/reporte_web.html', {'canal': canal})


# =========================================================
# 7. SIMULADORES Y REFERENCIAS
# =========================================================

@login_required
@verificar_acceso_plataforma('Mercado Libre')
def simulador_mercadolibre(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    simulaciones_todas = SimulacionMercadoLibre.objects.filter(usuario=request.user)
    
    if query_search:
        simulaciones_todas = simulaciones_todas.filter(
            Q(cod_publicacion__icontains=query_search) | 
            Q(cod_producto__icontains=query_search)
        )
        
    simulaciones_todas = simulaciones_todas.order_by('id')
    
    comisiones_ref = ReferenciaComision.objects.all()
    mapa_comisiones = {}
    for ref in comisiones_ref:
        if ref.sub_categoria:
            mapa_comisiones[ref.sub_categoria.upper().strip()] = float(ref.comision)
        if ref.categoria and ref.categoria.upper().strip() not in mapa_comisiones:
            mapa_comisiones[ref.categoria.upper().strip()] = float(ref.comision)

    costos_ref = ReferenciaCosto.objects.all()
    mapa_costos = {}
    mapa_nombres = {}
    for ref in costos_ref:
        if ref.codigo:
            clave = ref.codigo.upper().strip()
            mapa_costos[clave] = float(ref.costo_cero)
            mapa_nombres[clave] = str(ref.producto) if getattr(ref, 'producto', None) else ""

    mapa_comisiones_json = json.dumps(mapa_comisiones)
    mapa_costos_json = json.dumps(mapa_costos)
    mapa_nombres_json = json.dumps(mapa_nombres) 
    
    paginator = Paginator(simulaciones_todas, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    for sim in page_obj:
        cat_buscar = sim.categoria.upper().strip() if sim.categoria else ""
        sim.nueva_comision_ref = mapa_comisiones.get(cat_buscar, 0.00)
        
        cod_buscar = sim.cod_producto.upper().strip() if sim.cod_producto else ""
        sim.nuevo_costo_ref = mapa_costos.get(cod_buscar, float(sim.costo_producto or 0.00))
        
    return render(request, 'simuladores_plataformas/simulador_mercadolibre.html', {
        'canal': canal, 
        'page_obj': page_obj, 
        'mapa_comisiones_json': mapa_comisiones_json,
        'mapa_costos_json': mapa_costos_json,
        'mapa_nombres_json': mapa_nombres_json, 
        'query_search': query_search  
    })

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
def referencia_comisiones(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    comisiones_todas = ReferenciaComision.objects.all().order_by('id')

    if query_search:
        comisiones_todas = comisiones_todas.filter(
            Q(sub_categoria__icontains=query_search) | 
            Q(categoria__icontains=query_search)
        )

    paginator = Paginator(comisiones_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventario/referencia_comisiones.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search
    })

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
def guardar_comisiones(request):
    if request.method == 'POST':
        messages.success(request, "Las comisiones han sido actualizadas.")
        return redirect('referencia_comisiones')
    return redirect('referencia_comisiones')

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
@csrf_exempt
def guardar_comisiones_masivas(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_referencia = data.get('referencias', [])
            
            for fila in filas_referencia:
                sub_categoria = fila.get('SUB CATEGORÍA', '').strip()
                categoria = fila.get('CATEGORÍA', '').strip()
                
                comision_texto = str(fila.get('COMISIÓN', '0')).replace('%', '').replace(',', '.').strip()
                try:
                    comision_num = float(comision_texto) if comision_texto else 0.0
                except ValueError:
                    comision_num = 0.0

                if sub_categoria:
                    ReferenciaComision.objects.update_or_create(
                        sub_categoria=sub_categoria,
                        defaults={
                            'categoria': categoria, 
                            'comision': comision_num
                        }
                    )
                    
            return JsonResponse({'status': 'ok', 'message': f'Se procesaron {len(filas_referencia)} categorías con éxito.'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def descargar_plantilla_comisiones(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_referencia_comisiones.csv"'
    
    response.write('\ufeff'.encode('utf8'))
    
    writer = csv.writer(response, delimiter=';')
    
    writer.writerow(['SUB CATEGORÍA', 'CATEGORÍA', 'COMISIÓN'])
    
    writer.writerow(['Electrodomésticos', 'BATIDORA DE MANO', '12.5%'])
    writer.writerow(['Línea Blanca', 'REFRIGERADORA', '9.5%'])
    writer.writerow(['Audio y Video', 'TELEVISOR', '11.0%'])
    
    return response

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
@csrf_exempt
def eliminar_comisiones_masivas(request):
    if request.method == 'POST':
        try:
            ReferenciaComision.objects.all().delete()
            return JsonResponse({'status': 'ok', 'message': 'Todas las referencias han sido eliminadas correctamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

# ---------------------------------------------------------
# NUEVAS FUNCIONES: REFERENCIA DE COSTOS
# ---------------------------------------------------------
@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
def referencia_costos(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    costos_todos = ReferenciaCosto.objects.all().order_by('codigo')

    if query_search:
        costos_todos = costos_todos.filter(
            Q(codigo__icontains=query_search) | 
            Q(producto__icontains=query_search)
        )

    paginator = Paginator(costos_todos, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inventario/referencia_costos.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search
    })

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
@csrf_exempt
def guardar_costos_masivos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_costos = data.get('referencias', [])
            
            for fila in filas_costos:
                codigo = fila.get('CÓDIGO', '').strip()
                producto = fila.get('PRODUCTO', '').strip()
                
                def limpiar_numero(valor):
                    texto = str(valor).replace('$', '').replace('S/.', '').replace(',', '.').strip()
                    try:
                        return float(texto) if texto else 0.0
                    except ValueError:
                        return 0.0

                c_cero = limpiar_numero(fila.get('COSTO CERO', 0))
                c_dolares = limpiar_numero(fila.get('COSTO U. ($)', 0))
                c_soles = limpiar_numero(fila.get('COSTO U. ($ ► S/.)', 0))

                if codigo:
                    ReferenciaCosto.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'producto': producto, 
                            'costo_cero': c_cero,
                            'costo_u_dolares': c_dolares,
                            'costo_u_soles': c_soles
                        }
                    )
                    
            return JsonResponse({'status': 'ok', 'message': f'Se procesaron {len(filas_costos)} costos con éxito.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
@verificar_acceso_plataforma('Mercado Libre', 'Mercado Libre - Junior')
@csrf_exempt
def eliminar_costos_masivos(request):
    if request.method == 'POST':
        try:
            ReferenciaCosto.objects.all().delete()
            return JsonResponse({'status': 'ok', 'message': 'Todos los costos han sido eliminados correctamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


@login_required
@verificar_acceso_plataforma('Mercado Libre - Junior')
def simulador_mercadolibre_junior(request):
    canal = request.session.get('canal_activo')
    
    query_search = request.GET.get('q', '')
    simulaciones_todas = SimulacionMercadoLibreJunior.objects.filter(usuario=request.user)
    
    if query_search:
        simulaciones_todas = simulaciones_todas.filter(
            Q(cod_publicacion__icontains=query_search) | 
            Q(cod_producto__icontains=query_search)
        )
        
    simulaciones_todas = simulaciones_todas.order_by('id')
    
    comisiones_ref = ReferenciaComision.objects.all()
    mapa_comisiones = {}
    for ref in comisiones_ref:
        if ref.sub_categoria:
            mapa_comisiones[ref.sub_categoria.upper().strip()] = float(ref.comision)
        if ref.categoria and ref.categoria.upper().strip() not in mapa_comisiones:
            mapa_comisiones[ref.categoria.upper().strip()] = float(ref.comision)

    costos_ref = ReferenciaCosto.objects.all()
    mapa_costos = {}
    mapa_nombres = {}
    for ref in costos_ref:
        if ref.codigo:
            clave = ref.codigo.upper().strip()
            mapa_costos[clave] = float(ref.costo_cero)
            mapa_nombres[clave] = str(ref.producto) if getattr(ref, 'producto', None) else ""

    mapa_comisiones_json = json.dumps(mapa_comisiones)
    mapa_costos_json = json.dumps(mapa_costos)
    mapa_nombres_json = json.dumps(mapa_nombres) 
    
    paginator = Paginator(simulaciones_todas, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    for sim in page_obj:
        cat_buscar = sim.categoria.upper().strip() if sim.categoria else ""
        sim.nueva_comision_ref = mapa_comisiones.get(cat_buscar, 0.00)
        
        cod_buscar = sim.cod_producto.upper().strip() if sim.cod_producto else ""
        sim.nuevo_costo_ref = mapa_costos.get(cod_buscar, float(sim.costo_producto or 0.00))
        
    return render(request, 'simuladores_plataformas/simulador_mercadolibre_junior.html', {
        'canal': canal, 
        'page_obj': page_obj, 
        'mapa_comisiones_json': mapa_comisiones_json,
        'mapa_costos_json': mapa_costos_json,
        'mapa_nombres_json': mapa_nombres_json, 
        'query_search': query_search  
    })

@login_required
@verificar_acceso_plataforma('Creditienda')
def simulador_creditienda(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_creditienda.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Falabella')
def simulador_falabella(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_falabella.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Intercorp')
def simulador_intercorp(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_intercorp.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Tik tok', 'Tiktok')
def simulador_tiktok(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_tiktok.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Venta Libre')
def simulador_ventalibre(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_ventalibre.html', {'canal': canal})

@login_required
@verificar_acceso_plataforma('Web')
def simulador_web(request):
    canal = request.session.get('canal_activo')
    return render(request, 'simuladores_plataformas/simulador_web.html', {'canal': canal})

@login_required
def pantalla_carga(request):
    canal = request.session.get('canal_activo', 'Web')
    return render(request, 'inventario/loading.html', {'canal': canal})

@login_required
def descargar_plantilla_simulador(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_simulador_mercadolibre.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'ITEM TYPE', 'LINK', 'ESTADO', 'CÓD. PUB', 'TIPO', 
        'CÓD. PROD', 'CATEGORIA', 'MARCA', 'PRODUCTO', 'P. TACHADO', 
        '% DSCTO', 'P. VENTA', 'ENVÍO', '% NUEVA COM', 'COM (S/)', 
        'PAGO NETO', 'COSTO', 'GANANCIA', 'RTBLD%', 'MPE'
    ])
    return response

@login_required
def descargar_plantilla_costos(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_referencia_costos.csv"'
    writer = csv.writer(response)
    writer.writerow(['CÓDIGO', 'PRODUCTO', 'COSTO CERO', 'COSTO U. ($)', 'COSTO U. ($ ► S/.)'])
    writer.writerow(['SKU-EJEMPLO', 'Producto de Prueba', '10.50', '15.00', ''])
    return response

@login_required
def descargar_plantilla_reporte_ml(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_reportes_mercadolibre.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    
    # Agregamos las dos columnas nuevas aquí
    writer.writerow([
        'FECHA', 'MES Y AÑO', 'NRO. ORDEN', 'N.º de operación', 'Estado de pago', 
        'COMPROBANTE', 'TIPO DE VENTA', 'MARCA', 'CATEGORIA', 'SKU ALMACEN', 
        'MODELO', 'PRODUCTO', 'CANT.', 'PRECIO', 'TOTAL V.', '%CARGO x VENTA', 
        'URBANO', 'FLEX', 'TOTAL PAGADO', 'COSTO x PRODUCTO', 'UND', 'COSTO TOTAL', 
        'COSTO ENTREGA FLEX', 'GANANCIA', 'RENTABILIDAD %', 'DISTRITO', 
        'DIRECCIÓN', 'REPARTIDOR', 'CELULAR DEL CLIENTE', 'MSJ DE AGRADECIMIENTO'
    ])
    
    writer.writerow([
        '15/06/2026', 'JUNIO 2026', '#2000010827615105', '12345678', 'Aprobado',
        'B001-00123', 'CATALOGO', 'OSTER', 'LICUADORA', 'SKU-OST-001', 
        'MOD-123', 'Licuadora Oster Clásica', '1', '150.00', '150.00', '10.50', 
        '0.00', '10.00', '129.50', '80.00', '1', '80.00', 
        '10.00', '39.50', '49.37%', 'San Juan de Lurigancho', 
        'Av. Próceres 123', 'Juan Pérez', '987654321', 'Gracias por su compra'
    ])
    return response

@login_required
def guardar_reportes_masivos_ml(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_ventas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ReporteMercadoLibre.objects.filter(id__in=eliminadas).delete()

            def get_best_val(val_antiguo, val_nuevo):
                v_antiguo = str(val_antiguo or '').replace('\n', '').replace('\r', '').strip()
                v_nuevo = str(val_nuevo or '').replace('\n', '').replace('\r', '').strip()
                if v_antiguo in ['', '---', '-', 'None', 'null', 'NaN']: v_antiguo = ''
                if v_nuevo in ['', '---', '-', 'None', 'null', 'NaN']: v_nuevo = ''
                return v_nuevo if v_nuevo else v_antiguo

            nros_ordenes_entrantes = [str(f.get('NRO. ORDEN', '')).replace('\n', '').strip() for f in filas_ventas if f.get('NRO. ORDEN', '').strip()]
            
            existentes_en_db = {
                venta.nro_orden: venta 
                for venta in ReporteMercadoLibre.objects.filter(nro_orden__in=nros_ordenes_entrantes)
            }

            ventas_unicas = {}
            
            for fila in filas_ventas:
                nro_orden = str(fila.get('NRO. ORDEN', '')).replace('\n', '').strip()
                if not nro_orden: 
                    continue

                db_obj = existentes_en_db.get(nro_orden)
                
                # Leemos las dos columnas nuevas
                val_nro_operacion = get_best_val(db_obj.nro_operacion if db_obj else '', fila.get('N.º de operación', ''))
                val_estado_pago = get_best_val(db_obj.estado_pago if db_obj else '', fila.get('Estado de pago', ''))
                
                val_comprobante = get_best_val(db_obj.comprobante if db_obj else '', fila.get('COMPROBANTE', ''))
                val_tipo_venta = get_best_val(db_obj.tipo_venta if db_obj else '', fila.get('TIPO DE VENTA', ''))
                val_marca = get_best_val(db_obj.marca if db_obj else '', fila.get('MARCA', ''))
                val_categoria = get_best_val(db_obj.categoria if db_obj else '', fila.get('CATEGORIA', ''))
                val_sku = get_best_val(db_obj.sku_almacen if db_obj else '', fila.get('SKU ALMACEN', ''))
                val_modelo = get_best_val(db_obj.modelo if db_obj else '', fila.get('MODELO', ''))
                val_producto = get_best_val(db_obj.producto if db_obj else '', fila.get('PRODUCTO', ''))

                fecha_raw = str(fila.get('FECHA', '')).strip()
                fecha_formateada = None
                if fecha_raw:
                    try:
                        if '/' in fecha_raw:
                            fecha_formateada = datetime.strptime(fecha_raw, '%d/%m/%Y').strftime('%Y-%m-%d')
                        else:
                            fecha_formateada = fecha_raw 
                    except ValueError:
                        fecha_formateada = '2026-01-01'

                def to_float(val):
                    try: return float(str(val).replace(',', '').strip() or 0)
                    except ValueError: return 0.00
                        
                def to_int(val):
                    try: return int(str(val).strip() or 0)
                    except ValueError: return 0

                obj = ReporteMercadoLibre(
                    nro_orden=nro_orden,
                    fecha=fecha_formateada or '2026-01-01',
                    mes_anio=fila.get('MES Y AÑO', '').strip(),
                    nro_operacion=val_nro_operacion,  # Agregado
                    estado_pago=val_estado_pago,      # Agregado
                    comprobante=val_comprobante,
                    tipo_venta=val_tipo_venta,
                    marca=val_marca,
                    categoria=val_categoria,
                    sku_almacen=val_sku,
                    modelo=val_modelo,
                    producto=val_producto,
                    cantidad=to_float(fila.get('CANT.', 0)),
                    precio=to_float(fila.get('PRECIO', 0)),
                    total_venta=to_float(fila.get('TOTAL V.', 0)),
                    cargo_venta=to_float(fila.get('%CARGO x VENTA', 0)),
                    urbano=to_float(fila.get('URBANO', 0)),
                    flex=to_float(fila.get('FLEX', 0)),
                    total_pagado=to_float(fila.get('TOTAL PAGADO', 0)),
                    costo_producto=to_float(fila.get('COSTO x PRODUCTO', 0)),
                    und=to_int(fila.get('UND', 0)),
                    costo_total=to_float(fila.get('COSTO TOTAL', 0)),
                    costo_entrega_flex=to_float(fila.get('COSTO ENTREGA FLEX', 0)),
                    ganancia=to_float(fila.get('GANANCIA', 0)),
                    rentabilidad=str(fila.get('RENTABILIDAD %', '')).strip(),
                    distrito=fila.get('DISTRITO', '').strip(),
                    direccion=fila.get('DIRECCIÓN', '').strip(),
                    repartidor=fila.get('REPARTIDOR', '').strip(),
                    celular=str(fila.get('CELULAR DEL CLIENTE', '')).strip(),
                    mensaje=fila.get('MSJ DE AGRADECIMIENTO', '').strip(),
                )
                
                if nro_orden in ventas_unicas:
                    existente = ventas_unicas[nro_orden]
                    existente.nro_operacion = get_best_val(existente.nro_operacion, obj.nro_operacion) # Agregado
                    existente.estado_pago = get_best_val(existente.estado_pago, obj.estado_pago)       # Agregado
                    existente.comprobante = get_best_val(existente.comprobante, obj.comprobante)
                    existente.tipo_venta = get_best_val(existente.tipo_venta, obj.tipo_venta)
                    existente.marca = get_best_val(existente.marca, obj.marca)
                    existente.categoria = get_best_val(existente.categoria, obj.categoria)
                    existente.sku_almacen = get_best_val(existente.sku_almacen, obj.sku_almacen)
                    existente.modelo = get_best_val(existente.modelo, obj.modelo)
                    existente.producto = get_best_val(existente.producto, obj.producto)
                else:
                    ventas_unicas[nro_orden] = obj

            objetos_a_guardar = list(ventas_unicas.values())

            if objetos_a_guardar:
                campos_actualizar = [
                    'fecha', 'mes_anio', 'nro_operacion', 'estado_pago', 'comprobante', 
                    'tipo_venta', 'marca', 'categoria', 'sku_almacen', 'modelo', 'producto', 
                    'cantidad', 'precio', 'total_venta', 'cargo_venta', 'urbano', 'flex',
                    'total_pagado', 'costo_producto', 'und', 'costo_total',
                    'costo_entrega_flex', 'ganancia', 'rentabilidad', 'distrito',
                    'direccion', 'repartidor', 'celular', 'mensaje'
                ]
                
                ReporteMercadoLibre.objects.bulk_create(
                    objetos_a_guardar,
                    update_conflicts=True,
                    unique_fields=['nro_orden'],
                    update_fields=campos_actualizar
                )
            
            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! Se agruparon y guardaron {len(objetos_a_guardar)} ventas unificadas correctamente.'})
        
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def guardar_reportes_masivos_ml_junior(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_ventas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ReporteMercadoLibreJunior.objects.filter(id__in=eliminadas).delete()

            def get_best_val(val_antiguo, val_nuevo):
                v_antiguo = str(val_antiguo or '').replace('\n', '').replace('\r', '').strip()
                v_nuevo = str(val_nuevo or '').replace('\n', '').replace('\r', '').strip()
                if v_antiguo in ['', '---', '-', 'None', 'null', 'NaN']: v_antiguo = ''
                if v_nuevo in ['', '---', '-', 'None', 'null', 'NaN']: v_nuevo = ''
                return v_nuevo if v_nuevo else v_antiguo

            nros_ordenes_entrantes = [str(f.get('NRO. ORDEN', '')).replace('\n', '').strip() for f in filas_ventas if f.get('NRO. ORDEN', '').strip()]
            existentes_en_db = {
                venta.nro_orden: venta for venta in ReporteMercadoLibreJunior.objects.filter(nro_orden__in=nros_ordenes_entrantes)
            }

            ventas_unicas = {}
            for fila in filas_ventas:
                nro_orden = str(fila.get('NRO. ORDEN', '')).replace('\n', '').strip()
                if not nro_orden: continue

                db_obj = existentes_en_db.get(nro_orden)
                
                fecha_raw = str(fila.get('FECHA', '')).strip()
                fecha_formateada = '2026-01-01'
                if fecha_raw:
                    try:
                        fecha_formateada = datetime.strptime(fecha_raw, '%d/%m/%Y').strftime('%Y-%m-%d') if '/' in fecha_raw else fecha_raw 
                    except ValueError: pass

                def to_float(val):
                    try: return float(str(val).replace(',', '').strip() or 0)
                    except ValueError: return 0.00
                def to_int(val):
                    try: return int(str(val).strip() or 0)
                    except ValueError: return 0

                obj = ReporteMercadoLibreJunior(
                    nro_orden=nro_orden,
                    fecha=fecha_formateada,
                    mes_anio=fila.get('MES Y AÑO', '').strip(),
                    nro_operacion=get_best_val(db_obj.nro_operacion if db_obj else '', fila.get('N.º de operación', '')),
                    estado_pago=get_best_val(db_obj.estado_pago if db_obj else '', fila.get('Estado de pago', '')),
                    comprobante=get_best_val(db_obj.comprobante if db_obj else '', fila.get('COMPROBANTE', '')),
                    tipo_venta=get_best_val(db_obj.tipo_venta if db_obj else '', fila.get('TIPO DE VENTA', '')),
                    marca=get_best_val(db_obj.marca if db_obj else '', fila.get('MARCA', '')),
                    categoria=get_best_val(db_obj.categoria if db_obj else '', fila.get('CATEGORIA', '')),
                    sku_almacen=get_best_val(db_obj.sku_almacen if db_obj else '', fila.get('SKU ALMACEN', '')),
                    modelo=get_best_val(db_obj.modelo if db_obj else '', fila.get('MODELO', '')),
                    producto=get_best_val(db_obj.producto if db_obj else '', fila.get('PRODUCTO', '')),
                    cantidad=to_float(fila.get('CANT.', 0)),
                    precio=to_float(fila.get('PRECIO', 0)),
                    total_venta=to_float(fila.get('TOTAL V.', 0)),
                    cargo_venta=to_float(fila.get('%CARGO x VENTA', 0)),
                    urbano=to_float(fila.get('URBANO', 0)),
                    flex=to_float(fila.get('FLEX', 0)),
                    total_pagado=to_float(fila.get('TOTAL PAGADO', 0)),
                    costo_producto=to_float(fila.get('COSTO x PRODUCTO', 0)),
                    und=to_int(fila.get('UND', 0)),
                    costo_total=to_float(fila.get('COSTO TOTAL', 0)),
                    costo_entrega_flex=to_float(fila.get('COSTO ENTREGA FLEX', 0)),
                    ganancia=to_float(fila.get('GANANCIA', 0)),
                    rentabilidad=str(fila.get('RENTABILIDAD %', '')).strip(),
                    distrito=fila.get('DISTRITO', '').strip(),
                    direccion=fila.get('DIRECCIÓN', '').strip(),
                    repartidor=fila.get('REPARTIDOR', '').strip(),
                    celular=str(fila.get('CELULAR DEL CLIENTE', '')).strip(),
                    mensaje=fila.get('MSJ DE AGRADECIMIENTO', '').strip(),
                )
                
                if nro_orden in ventas_unicas:
                    existente = ventas_unicas[nro_orden]
                    existente.nro_operacion = get_best_val(existente.nro_operacion, obj.nro_operacion)
                    existente.estado_pago = get_best_val(existente.estado_pago, obj.estado_pago)
                    existente.comprobante = get_best_val(existente.comprobante, obj.comprobante)
                    existente.modelo = get_best_val(existente.modelo, obj.modelo)
                else:
                    ventas_unicas[nro_orden] = obj

            objetos_a_guardar = list(ventas_unicas.values())
            if objetos_a_guardar:
                ReporteMercadoLibreJunior.objects.bulk_create(
                    objetos_a_guardar, update_conflicts=True, unique_fields=['nro_orden'],
                    update_fields=[f.name for f in ReporteMercadoLibreJunior._meta.fields if f.name not in ['id', 'nro_orden']]
                )
            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! Se guardaron {len(objetos_a_guardar)} ventas en Junior.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
@csrf_exempt
def borrar_todos_los_reportes_ml_junior(request):
    if request.method == 'POST':
        ReporteMercadoLibreJunior.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': '¡Reportes Junior limpiados con éxito!'})
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})

@login_required
@csrf_exempt
def guardar_ingresos_masivos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_ingresos = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if not filas_ingresos and not eliminadas:
                return JsonResponse({'status': 'error', 'message': 'No hay datos para procesar.'})

            with transaction.atomic():
                productos_db = Producto.objects.all()
                dict_productos = {}
                for p in productos_db:
                    if p.modelo:
                        key_prod = p.modelo.upper().replace(" ", "").replace("-", "")
                        dict_productos[key_prod] = p
                
                productos_a_actualizar = set() 

                if eliminadas:
                    ids_a_eliminar = [int(i) for i in eliminadas if str(i).isdigit()]
                    if ids_a_eliminar:
                        registros_viejos = IngresoPercheron.objects.filter(id__in=ids_a_eliminar)
                        
                        for reg in registros_viejos:
                            if reg.modelo:
                                key_reg = str(reg.modelo).upper().replace(" ", "").replace("-", "")
                                prod = dict_productos.get(key_reg)
                                if prod:
                                    prod.stock_actual = max(prod.stock_actual - (reg.cantidad or 1), 0)
                                    productos_a_actualizar.add(prod)
                        
                        registros_viejos.delete()

                objetos_a_crear = []
                
                for fila in filas_ingresos:
                    modelo = str(fila.get('MODELO') or '').strip()
                    titulo = str(fila.get('TÍTULO') or fila.get('TITULO') or '').strip()
                    codigo_ean = str(fila.get('CÓDIGO EAN') or fila.get('CODIGO EAN') or '').strip()
                    serie_nro = str(fila.get('SERIE / N°') or fila.get('SERIE') or '').strip() or None
                    
                    sku_leido = str(fila.get('SKU') or '').strip()
                    
                    if not sku_leido and modelo:
                        sku_leido = f"{modelo}-AUTO{uuid.uuid4().hex[:4].upper()}"
                    elif not sku_leido:
                        sku_leido = None
                    
                    proveedor_motivo = str(fila.get('PROVEEDOR / MOTIVO') or '').strip()
                    by_usuario = str(fila.get('BY:') or '').strip()

                    if not serie_nro and not modelo and not titulo:
                        continue

                    fecha_raw = str(fila.get('FECHA INGRESO') or fila.get('FECHA') or '').strip()
                    fecha_formateada = datetime.now().date()
                    if fecha_raw:
                        try:
                            if '/' in fecha_raw:
                                fecha_formateada = datetime.strptime(fecha_raw, '%d/%m/%Y').date()
                            elif '-' in fecha_raw:
                                fecha_formateada = datetime.strptime(fecha_raw, '%Y-%m-%d').date()
                        except:
                            pass 

                    def to_float(val):
                        try: return float(str(val).replace(',', '').strip() or 0)
                        except: return 0.0

                    def to_int(val):
                        try: return int(float(str(val).strip() or 1))
                        except: return 1

                    cantidad_val = to_int(fila.get('ING. x 1 und') or fila.get('CANTIDAD') or 1)

                    obj = IngresoPercheron(
                        sku=sku_leido,
                        modelo=modelo,
                        titulo=titulo,
                        fecha_ingreso=fecha_formateada,
                        codigo_ean=codigo_ean,
                        serie_nro=serie_nro,
                        costo_unitario=to_float(fila.get('COSTO UNT.') or fila.get('COSTO') or 0),
                        cantidad=cantidad_val,
                        proveedor_motivo=proveedor_motivo,
                        creado_por=by_usuario
                    )
                    objetos_a_crear.append(obj)

                    if modelo:
                        key_ingreso = str(modelo).upper().replace(" ", "").replace("-", "")
                        prod = dict_productos.get(key_ingreso)
                        if prod:
                            prod.stock_actual += cantidad_val
                            productos_a_actualizar.add(prod)

                if objetos_a_crear:
                    IngresoPercheron.objects.bulk_create(objetos_a_crear)

                for prod in productos_a_actualizar:
                    prod.save(update_fields=['stock_actual'])

            return JsonResponse({'status': 'ok', 'message': f'Guardado correctamente. Se subieron {len(objetos_a_crear)} registros y se actualizó el stock.'})

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': f'Error: {str(e)}'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
def descargar_plantilla_ingresos(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Plantilla_Ingresos_Percheron.csv"'
    response.write('\ufeff'.encode('utf8'))
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'SKU', 'MODELO', 'TÍTULO', 'FECHA INGRESO', 'CÓDIGO EAN', 
        'SERIE / N°', 'COSTO UNT.', 'ING. x 1 und', 'PROVEEDOR / MOTIVO', 'BY:'
    ])
    return response


@login_required
def exportar_modelos_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Directorio_Modelos.csv"'
    response.write('\ufeff'.encode('utf8'))
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'MODELO', 'MARCA', 'CATEGORÍA', 'TÍTULO', 'STOCK', 
        'INVENTARIADO POR LOS PERCHERONES', 'MERCADO LIBRE', 'FALABELLA', 'CREDITIENDA', 'PÁGINA WEB'
    ])
    
    for p in Producto.objects.all().order_by('id'):
        writer.writerow([
            p.modelo or '', 
            p.marca or '', 
            p.categoria or '', 
            p.titulo or '', 
            p.stock_actual, 
            'TRUE' if p.activo_intercorp else 'FALSE',
            'TRUE' if p.activo_ml else 'FALSE',
            'TRUE' if p.activo_falabella else 'FALSE',
            'TRUE' if p.activo_creditienda else 'FALSE',
            'TRUE' if p.activo_web else 'FALSE'
        ])
        
    return response

@login_required
def guardar_modelos_masivos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            referencias = data.get('referencias', [])
            
            if not referencias:
                return JsonResponse({'status': 'error', 'message': 'No se enviaron datos.'})

            with transaction.atomic():
                for item in referencias:
                    modelo_val = str(item.get('MODELO') or '').strip()
                    if not modelo_val:
                        continue
                    
                    obj, created = Producto.objects.get_or_create(
                        modelo=modelo_val, 
                        defaults={
                            'sku': f'SKU-{uuid.uuid4().hex[:8].upper()}', 
                            'titulo': item.get('TÍTULO', '')
                        }
                    )
                    
                    obj.marca = item.get('MARCA', '')
                    obj.categoria = item.get('CATEGORÍA', '')
                    obj.titulo = item.get('TÍTULO', '')
                    
                    obj.activo_intercorp = True if item.get('INVENTARIADO POR LOS PERCHERONES') == 'TRUE' else False
                    obj.activo_ml = True if item.get('MERCADO LIBRE') == 'TRUE' else False
                    obj.activo_falabella = True if item.get('FALABELLA') == 'TRUE' else False
                    obj.activo_creditienda = True if item.get('CREDITIENDA') == 'TRUE' else False
                    obj.activo_web = True if item.get('PÁGINA WEB') == 'TRUE' else False
                    
                    obj.save()
                    
            return JsonResponse({'status': 'ok', 'message': '¡Directorio de Modelos actualizado correctamente!'})
            
        except Exception as e:
            import traceback
            print(traceback.format_exc()) 
            return JsonResponse({'status': 'error', 'message': f'Error en el servidor: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})
        
@login_required
@csrf_exempt
def borrar_todos_los_ingresos(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                IngresoPercheron.objects.all().delete()
                Producto.objects.all().update(stock_actual=0)
            return JsonResponse({'status': 'ok', 'message': '¡Base de datos de ingresos limpiada y stocks reseteados a 0!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})

@login_required
@csrf_exempt
def sincronizar_stock_modelos(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                Producto.objects.all().update(stock_actual=0)
                
                conteo_stock = {}
                todos_ingresos = IngresoPercheron.objects.all()
                
                for ing in todos_ingresos:
                    modelo_key = str(ing.modelo).strip().upper()
                    if modelo_key:
                        conteo_stock[modelo_key] = conteo_stock.get(modelo_key, 0) + (ing.cantidad or 0)

                modelos_db = Producto.objects.all()
                modelos_actualizados = 0
                
                for prod in modelos_db:
                    modelo_prod = str(prod.modelo).strip().upper()
                    if modelo_prod in conteo_stock:
                        prod.stock_actual = conteo_stock[modelo_prod]
                        prod.save(update_fields=['stock_actual'])
                        modelos_actualizados += 1
            
            return JsonResponse({'status': 'ok', 'message': f'Sincronización exitosa: {modelos_actualizados} modelos actualizados.'})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

@login_required
@csrf_exempt
def borrar_todos_los_modelos(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                Producto.objects.all().delete()
                
            return JsonResponse({'status': 'ok', 'message': '¡Directorio de Modelos borrado completamente!'})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})

@login_required
@csrf_exempt
def procesar_salidas_ml(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})

        with transaction.atomic():
            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaMercadoLibre.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    if registro.modelo:
                        key = str(registro.modelo).upper().replace(" ", "").replace("-", "")
                        conteo_restauraciones[key] = conteo_restauraciones.get(key, 0) + registro.descuento
                    
                    registro.delete()

            if salidas:
                for sal in salidas:
                    sku = sal.get('sku', '').strip()
                    modelo = sal.get('modelo', '').strip()
                    titulo = sal.get('titulo', '').strip()
                    fecha_salida = sal.get('fecha_salida') or datetime.now().date()
                    serie = sal.get('serie', '')
                    costo = float(sal.get('costo') or 0)
                    descuento = int(float(sal.get('desc_1und') or 1))
                    nro_venta = sal.get('nro_ventas', '')
                    tipo_venta = sal.get('tipo_venta', '')
                    by_usuario = sal.get('by', request.user.username)

                    SalidaMercadoLibre.objects.create(
                        sku=sku,
                        modelo=modelo,
                        titulo=titulo,
                        fecha_salida=fecha_salida,
                        serie=serie,
                        costo=costo,
                        descuento=descuento,
                        nro_venta=nro_venta,
                        tipo_venta=tipo_venta,
                        creado_por=by_usuario
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento

            modelos_afectados = 0
            modelos_restaurados = 0
            
            if conteo_descuentos or conteo_restauraciones:
                for prod in Producto.objects.all():
                    if prod.modelo:
                        key = prod.modelo.upper().replace(" ", "").replace("-", "")
                        cambio = False
                        
                        if key in conteo_restauraciones:
                            prod.stock_actual += conteo_restauraciones[key]
                            modelos_restaurados += 1
                            cambio = True
                            
                        if key in conteo_descuentos:
                            prod.stock_actual = max(prod.stock_actual - conteo_descuentos[key], 0)
                            modelos_afectados += 1
                            cambio = True
                            
                        if cambio:
                            prod.save(update_fields=['stock_actual'])

        mensaje_final = f'Proceso completado. Salidas nuevas guardadas: {modelos_afectados}. Stock devuelto (filas borradas): {modelos_restaurados}.'
        return JsonResponse({'status': 'ok', 'message': mensaje_final})

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})
    
@login_required
@csrf_exempt
def borrar_todos_los_reportes_ml(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                ReporteMercadoLibre.objects.all().delete()
            return JsonResponse({'status': 'ok', 'message': '¡Base de datos de reportes limpiada con éxito!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})

@login_required
@csrf_exempt
def borrar_todos_simulador_ml(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                SimulacionMercadoLibre.objects.all().delete()
            return JsonResponse({'status': 'ok', 'message': '¡Datos del simulador limpiados con éxito!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})

# ---------------------------------------------------------
# FUNCIONES DE GUARDADO Y BORRADO MASIVO: SIMULADOR ML JUNIOR
# ---------------------------------------------------------
@login_required
@verificar_acceso_plataforma('Mercado Libre - Junior')
@csrf_exempt
def guardar_simulador_masivo_ml_junior(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            datos_simulacion = data.get('datos', [])
            
            for fila in datos_simulacion:
                p_venta = float(fila.get('p_venta') or 0)
                envio = float(fila.get('envio') or 0)
                porc_com = float(fila.get('porc_comision') or 0)
                costo = float(fila.get('costo') or 0)
                
                com_soles = p_venta * (porc_com / 100)
                pago_neto = p_venta - com_soles - envio
                ganancia = pago_neto - costo
                rentabilidad = (ganancia / p_venta * 100) if p_venta > 0 else 0

                cod_pub = fila.get('cod_pub', '').strip()

                datos_diccionario = {
                    'item_type': fila.get('item_type', ''),
                    'link': fila.get('link', ''),
                    'estado_publicacion': fila.get('estado', ''),
                    'tipo_publicacion': fila.get('tipo', ''),
                    'cod_producto': fila.get('cod_prod', ''),
                    'categoria': fila.get('categoria', ''),
                    'marca': fila.get('marca', ''),
                    'producto': fila.get('producto', ''),
                    'precio_tachado': float(fila.get('p_tachado') or 0),
                    'porc_descuento': float(fila.get('dscto') or 0),
                    'precio_venta': p_venta,
                    'costo_envio': envio,
                    'porc_comision': porc_com,
                    'comision_soles': com_soles,
                    'pago_neto': pago_neto,
                    'costo_producto': costo,
                    'ganancia': ganancia,
                    'rentabilidad_porc': rentabilidad,
                    'mpe': fila.get('mpe', False)
                }

                if cod_pub:
                    SimulacionMercadoLibreJunior.objects.update_or_create(
                        usuario=request.user,
                        cod_publicacion=cod_pub,
                        defaults=datos_diccionario
                    )
                else:
                    SimulacionMercadoLibreJunior.objects.create(
                        usuario=request.user,
                        cod_publicacion='',
                        **datos_diccionario
                    )
            
            return JsonResponse({'status': 'ok', 'message': 'Simulación Junior guardada/actualizada exitosamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)

@login_required
@csrf_exempt
def borrar_todos_simulador_ml_junior(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                SimulacionMercadoLibreJunior.objects.filter(usuario=request.user).delete()
            return JsonResponse({'status': 'ok', 'message': '¡Datos del simulador Junior limpiados con éxito!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})


@login_required
@csrf_exempt
def procesar_salidas_ml_junior(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})

        with transaction.atomic():
            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaMercadoLibreJunior.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    if registro.modelo:
                        key = str(registro.modelo).upper().replace(" ", "").replace("-", "")
                        conteo_restauraciones[key] = conteo_restauraciones.get(key, 0) + registro.descuento
                    registro.delete()

            if salidas:
                for sal in salidas:
                    sku = sal.get('sku', '').strip()
                    modelo = sal.get('modelo', '').strip()
                    titulo = sal.get('titulo', '').strip()
                    fecha_salida = sal.get('fecha_salida') or datetime.now().date()
                    serie = sal.get('serie', '')
                    costo = float(sal.get('costo') or 0)
                    descuento = int(float(sal.get('desc_1und') or 1))
                    nro_venta = sal.get('nro_ventas', '')
                    tipo_venta = sal.get('tipo_venta', '')
                    by_usuario = sal.get('by', request.user.username)

                    SalidaMercadoLibreJunior.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo, descuento=descuento, nro_venta=nro_venta,
                        tipo_venta=tipo_venta, creado_por=by_usuario
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento

            modelos_afectados = 0
            modelos_restaurados = 0
            
            if conteo_descuentos or conteo_restauraciones:
                for prod in Producto.objects.all():
                    if prod.modelo:
                        key = prod.modelo.upper().replace(" ", "").replace("-", "")
                        cambio = False
                        
                        if key in conteo_restauraciones:
                            prod.stock_actual += conteo_restauraciones[key]
                            modelos_restaurados += 1
                            cambio = True
                            
                        if key in conteo_descuentos:
                            prod.stock_actual = max(prod.stock_actual - conteo_descuentos[key], 0)
                            modelos_afectados += 1
                            cambio = True
                            
                        if cambio:
                            prod.save(update_fields=['stock_actual'])

        return JsonResponse({'status': 'ok', 'message': f'Proceso completado. Salidas Junior guardadas: {modelos_afectados}. Stock devuelto: {modelos_restaurados}.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    


@login_required
def descargar_plantilla_reporte_creditienda(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_creditienda.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'FECHA DE VENTA', 'FECHA DE DESPACHO', 'MES Y AÑO', 'ESTADO DE PEDIDO', 'NRO. ORDEN', 
        'CLIENTE', 'BOLETA', 'MARCA', 'CATEGORÍA', 'SKU ALMACÉN', 'CÓDIGO', 'PRODUCTO', 
        'CANT.', 'PRECIO DE VENTA', 'TOTAL DE VENTA', 'COMISIÓN (%)', 'COMISIÓN (S/.)', 
        'PAGO DE PLATAFORMA', 'CHECK_PAGO', 'ENVÍO', 'COSTO', 'GANANCIA', 'RENTABILIDAD', 
        'VENTA PAGADA', 'SE ADJUNTO', 'FECHA DE VALIDACIÓN', 'NRO. OPERACIÓN', 'N° TELÉFONO'
    ])
    return response

@login_required
@csrf_exempt
def borrar_todos_los_reportes_creditienda(request):
    if request.method == 'POST':
        ReporteCreditienda.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': '¡Reportes de Creditienda limpiados con éxito!'})
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})

@login_required
def guardar_reportes_masivos_creditienda(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ReporteCreditienda.objects.filter(id__in=eliminadas).delete()

            def parse_date(date_str):
                ds = str(date_str).strip()
                if not ds: return None
                try:
                    if '/' in ds: return datetime.strptime(ds, '%d/%m/%Y').strftime('%Y-%m-%d')
                    elif '-' in ds: return datetime.strptime(ds, '%Y-%m-%d').strftime('%Y-%m-%d')
                except: return None
                return ds

            def to_float(val):
                try: return float(str(val).replace('S/', '').replace('%', '').replace(',', '').strip() or 0)
                except: return 0.00
                
            def to_int(val):
                try: return int(float(str(val).strip() or 0))
                except: return 0

            objetos_a_guardar = []
            
            for fila in filas:
                nro_orden = str(fila.get('NRO. ORDEN', '')).strip()
                if not nro_orden: continue

                obj = ReporteCreditienda(
                    usuario=request.user,
                    fecha_venta=parse_date(fila.get('FECHA DE VENTA')),
                    fecha_despacho=parse_date(fila.get('FECHA DE DESPACHO')),
                    mes_ano=str(fila.get('MES Y AÑO', '')).strip(),
                    estado_pedido=str(fila.get('ESTADO DE PEDIDO', '')).strip(),
                    nro_orden=nro_orden,
                    cliente=str(fila.get('CLIENTE', '')).strip(),
                    boleta=str(fila.get('BOLETA', '')).strip(),
                    marca=str(fila.get('MARCA', '')).strip(),
                    categoria=str(fila.get('CATEGORÍA', '')).strip(),
                    sku_almacen=str(fila.get('SKU ALMACÉN', '')).strip(),
                    codigo=str(fila.get('CÓDIGO', '')).strip(),
                    producto=str(fila.get('PRODUCTO', '')).strip(),
                    cantidad=to_int(fila.get('CANT.', 1)),
                    precio_venta=to_float(fila.get('PRECIO DE VENTA')),
                    total_venta=to_float(fila.get('TOTAL DE VENTA')),
                    porc_comision=to_float(fila.get('COMISIÓN (%)')),
                    comision_soles=to_float(fila.get('COMISIÓN (S/.)')),
                    pago_plataforma=to_float(fila.get('PAGO DE PLATAFORMA')),
                    envio=to_float(fila.get('ENVÍO')),
                    costo=to_float(fila.get('COSTO')),
                    ganancia=to_float(fila.get('GANANCIA')),
                    rentabilidad=to_float(fila.get('RENTABILIDAD')),
                    check_pago=True if str(fila.get('CHECK_PAGO', '')).upper() == 'TRUE' else False,
                    venta_pagada=str(fila.get('VENTA PAGADA', '')).strip(),
                    se_adjunto=str(fila.get('SE ADJUNTO', '')).strip(),
                    fecha_validacion=parse_date(fila.get('FECHA DE VALIDACIÓN')),
                    nro_operacion=str(fila.get('NRO. OPERACIÓN', '')).strip(),
                    nro_telefono=str(fila.get('N° TELÉFONO', '')).strip(),
                )
                objetos_a_guardar.append(obj)

            if objetos_a_guardar:
                # Obtenemos los campos del modelo para actualizar en caso de conflicto
                campos_update = [f.name for f in ReporteCreditienda._meta.fields if f.name not in ['id', 'fecha_registro', 'usuario']]
                
                # Como NRO_ORDEN no es Unique=True en el modelo, borramos los existentes y los re-creamos para "actualizar"
                nros = [o.nro_orden for o in objetos_a_guardar]
                ReporteCreditienda.objects.filter(nro_orden__in=nros).delete()
                ReporteCreditienda.objects.bulk_create(objetos_a_guardar)

            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! Se guardaron/actualizaron {len(objetos_a_guardar)} ventas de Creditienda.'})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})


@login_required
def descargar_plantilla_reporte_falabella(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_falabella.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'FECHA', 'MES-AÑO', 'NRO. ORDEN', 'BOLETA / FACTURA', 'MARCA', 
        'CATEGORIA', 'SKU ALMACÉN', 'CÓDIGO', 'PRODUCTO', 'CANT.', 
        'PRECIO', 'V. TOTAL', 'COMISIÓN %', 'COMISIÓN (S/.)', 'COSTO DE ENVIO', 
        'TOTAL PAGADO', 'COSTO X PROD.', 'CANTIDAD', 'C.TOTAL', 'GANANCIA', 
        '% RTBLD.', 'N.º de operación', 'Estado de pago'
    ])
    return response

@login_required
@csrf_exempt
def borrar_todos_los_reportes_falabella(request):
    if request.method == 'POST':
        ReporteFalabella.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': '¡Reportes de Falabella limpiados con éxito!'})
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})

@login_required
def guardar_reportes_masivos_falabella(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ReporteFalabella.objects.filter(id__in=eliminadas).delete()

            def parse_date(date_str):
                ds = str(date_str).strip()
                if not ds: return None
                try:
                    if '/' in ds: return datetime.strptime(ds, '%d/%m/%Y').strftime('%Y-%m-%d')
                    elif '-' in ds: return datetime.strptime(ds, '%Y-%m-%d').strftime('%Y-%m-%d')
                except: return None
                return ds

            def to_float(val):
                try: return float(str(val).replace('S/', '').replace('%', '').replace(',', '').strip() or 0)
                except: return 0.00
                
            def to_int(val):
                try: return int(float(str(val).strip() or 0))
                except: return 0

            objetos_a_guardar = []
            
            for fila in filas:
                nro_orden = str(fila.get('NRO. ORDEN', '')).strip()
                if not nro_orden: continue

                obj = ReporteFalabella(
                    usuario=request.user,
                    fecha=parse_date(fila.get('FECHA')),
                    mes_ano=str(fila.get('MES-AÑO', '')).strip(),
                    nro_orden=nro_orden,
                    boleta_factura=str(fila.get('BOLETA / FACTURA', '')).strip(),
                    marca=str(fila.get('MARCA', '')).strip(),
                    categoria=str(fila.get('CATEGORIA', '')).strip(),
                    sku_almacen=str(fila.get('SKU ALMACÉN', '')).strip(),
                    codigo=str(fila.get('CÓDIGO', '')).strip(),
                    producto=str(fila.get('PRODUCTO', '')).strip(),
                    cant=to_int(fila.get('CANT.', 1)),
                    precio=to_float(fila.get('PRECIO')),
                    v_total=to_float(fila.get('V. TOTAL')),
                    comision_porc=to_float(fila.get('COMISIÓN %')),
                    comision_soles=to_float(fila.get('COMISIÓN (S/.)')),
                    costo_envio=to_float(fila.get('COSTO DE ENVIO')),
                    total_pagado=to_float(fila.get('TOTAL PAGADO')),
                    costo_x_prod=to_float(fila.get('COSTO X PROD.')),
                    cantidad=to_int(fila.get('CANTIDAD', 1)),
                    c_total=to_float(fila.get('C.TOTAL')),
                    ganancia=to_float(fila.get('GANANCIA')),
                    rtbld=to_float(fila.get('% RTBLD.')),
                    nro_operacion=str(fila.get('N.º de operación', '')).strip(),
                    estado_pago=str(fila.get('Estado de pago', '')).strip(),
                )
                objetos_a_guardar.append(obj)

            if objetos_a_guardar:
                nros = [o.nro_orden for o in objetos_a_guardar]
                ReporteFalabella.objects.filter(nro_orden__in=nros).delete()
                ReporteFalabella.objects.bulk_create(objetos_a_guardar)

            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! Se guardaron/actualizaron {len(objetos_a_guardar)} ventas de Falabella.'})
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})



@login_required
def directorio_productos(request):
    canal = request.session.get('canal_activo', 'Directorio Global')
    query_search = request.GET.get('q', '')
    
    if query_search:
        productos = DirectorioProducto.objects.filter(
            Q(codigo__icontains=query_search) | 
            Q(producto__icontains=query_search)
        ).order_by('codigo')
    else:
        productos = DirectorioProducto.objects.all().order_by('codigo')
        
    paginator = Paginator(productos, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'inventario/directorio_productos.html', {
        'canal': canal,
        'page_obj': page_obj,
        'query_search': query_search
    })

@login_required
def descargar_plantilla_directorio(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_directorio.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['CODIGO', 'PRODUCTO', 'COSTO'])
    return response

@login_required
@csrf_exempt
def guardar_directorio_masivo(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                DirectorioProducto.objects.filter(id__in=eliminadas).delete()

            def to_float(val):
                try: return float(str(val).replace('S/', '').replace(',', '').strip() or 0)
                except: return 0.00

            objetos_a_guardar = []
            for fila in filas:
                codigo = str(fila.get('CODIGO', '')).strip()
                if not codigo: continue
                
                obj = DirectorioProducto(
                    usuario=request.user,
                    codigo=codigo,
                    producto=str(fila.get('PRODUCTO', '')).strip(),
                    costo=to_float(fila.get('COSTO'))
                )
                objetos_a_guardar.append(obj)

            if objetos_a_guardar:
                codigos = [o.codigo for o in objetos_a_guardar]
                DirectorioProducto.objects.filter(codigo__in=codigos).delete()
                DirectorioProducto.objects.bulk_create(objetos_a_guardar)

            return JsonResponse({'status': 'ok', 'message': f'¡Éxito! Se guardaron/actualizaron {len(objetos_a_guardar)} productos en el Directorio.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})

@login_required
@csrf_exempt
def borrar_todos_directorio(request):
    if request.method == 'POST':
        DirectorioProducto.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': '¡Directorio borrado con éxito!'})
    return JsonResponse({'status': 'error', 'message': 'Solo POST'})



@login_required
@verificar_acceso_plataforma('Intercorp')
def comisiones_intercorp(request):
    canal = request.session.get('canal_activo')
    query_search = request.GET.get('q', '')
    
    if query_search:
        comisiones = ComisionIntercorp.objects.filter(
            categoria__icontains=query_search
        ).order_by('categoria')
    else:
        comisiones = ComisionIntercorp.objects.all().order_by('categoria')

    return render(request, 'reportes_plataformas/comisiones_intercorp.html', {
        'canal': canal, 
        'comisiones': comisiones,
        'query_search': query_search
    })

@login_required
@csrf_exempt
def guardar_comisiones_intercorp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas = data.get('referencias', [])
            eliminadas = data.get('eliminadas', [])

            if eliminadas:
                ComisionIntercorp.objects.filter(id__in=eliminadas).delete()

            objetos = []
            for f in filas:
                cat = str(f.get('CATEGORIA', '')).strip()
                if not cat: continue
                val_perc = str(f.get('%', '0')).replace('%', '').strip()
                try: perc = float(val_perc)
                except: perc = 0.00
                
                objetos.append(ComisionIntercorp(usuario=request.user, categoria=cat, porcentaje=perc))

            if objetos:
                cats = [o.categoria for o in objetos]
                ComisionIntercorp.objects.filter(categoria__in=cats).delete()
                ComisionIntercorp.objects.bulk_create(objetos)
            return JsonResponse({'status': 'ok', 'message': 'guardado'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'solo post'})

@login_required
@csrf_exempt
def borrar_comisiones_intercorp(request):
    if request.method == 'POST':
        ComisionIntercorp.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': 'limpio'})

@login_required
def descargar_plantilla_comisiones_intercorp(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_comisiones.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['CATEGORIA', '%'])
    return response


@login_required
def buscar_modelo_intercorp(request):
    modelo_query = request.GET.get('modelo', '').strip()
    try:
        from .models import RegistroPercheron 
        resultados = RegistroPercheron.objects.filter(modelo__icontains=modelo_query, estado='DISPONIBLE')
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().producto
            
        for r in resultados:
            data.append({
                'sku': r.sku,
                'marca': r.marca,
                'fecha_ingreso': r.fecha_ingreso.strftime('%d/%m/%Y') if r.fecha_ingreso else '',
                'serie': r.serie,
                'costo': str(r.costo),
                'proveedor': r.proveedor,
                'ingresado_por': r.usuario.username if r.usuario else ''
            })
            
        return JsonResponse({
            'status': 'ok', 
            'producto': producto_nombre,
            'stock': resultados.count(),
            'items': data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    

@login_required
@csrf_exempt
def procesar_salidas_intercorp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            salidas = data.get('salidas', [])
            from .models import RegistroPercheron 
            
            for s in salidas:
                sku = s.get('sku')
                SalidaIntercorp.objects.create(
                    usuario=request.user,
                    sku=sku,
                    modelo=s.get('modelo'),
                    titulo=s.get('titulo'),
                    fecha_salida=s.get('fecha_salida'),
                    serie=s.get('serie'),
                    costo_unt=s.get('costo_unt'),
                    desc_und=1,
                    nro_ventas=s.get('nro_ventas'),
                    by=s.get('by')
                )
                
                item = RegistroPercheron.objects.filter(sku=sku, estado='DISPONIBLE').first()
                if item:
                    item.estado = 'VENDIDO INTERCORP'
                    item.save()
                    
            return JsonResponse({'status': 'ok', 'message': 'descontado'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error'})