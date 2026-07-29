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
from django.core.cache import cache
from .utils import render_to_pdf

# Importación corregida de SimulacionMercadoLibreJunior
from .models import Electrodomestico, Plataforma, Producto, MovimientoPercheron, SimulacionMercadoLibre, ReferenciaComision, ReferenciaCosto, ReporteMercadoLibre, IngresoPercheron, SalidaMercadoLibre, ReporteMercadoLibreJunior, SimulacionMercadoLibreJunior, SalidaMercadoLibreJunior, SimulacionMercadoLibreJunior, SalidaMercadoLibreJunior, SalidaFalabella, SalidaCreditienda, SalidaIntercorp, SalidaTiktok, SalidaVentaLibre, ReporteCreditienda, ReporteFalabella, DirectorioProducto, ReporteIntercorp, ComisionIntercorp, SalidaBCI, SalidaWeb, HistorialEliminacion

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
def cambiar_plataforma_menu(request, plataforma, ruta_destino):
    """
    Función interceptora: Actualiza la sesión con la nueva plataforma
    y luego redirige a la vista solicitada.
    """
    # 1. Definimos los colores e íconos oficiales
    ESTILOS = {
        "Mercado Libre": {"color": "#F1C40F", "icono": "fas fa-handshake"},
        "Mercado Libre - Junior": {"color": "#F39C12", "icono": "fas fa-seedling"},
        "Creditienda": {"color": "#E74C3C", "icono": "fas fa-credit-card"},
        "Falabella": {"color": "#2ECC71", "icono": "fas fa-store"},
        "Intercorp": {"color": "#2980B9", "icono": "fas fa-building"},
        "Venta Libre": {"color": "#9B59B6", "icono": "fas fa-tags"},
        "Tik tok": {"color": "#2C3E50", "icono": "fab fa-tiktok"},
        "Web": {"color": "#3498DB", "icono": "fas fa-globe"}
    }
    
    # 2. Reconstruimos el nombre si viene con guiones bajos desde la URL
    plataforma_limpia = plataforma.replace('_', ' ')
    if plataforma_limpia == "Mercado Libre Junior":
        plataforma_limpia = "Mercado Libre - Junior"
    
    # 3. Validamos permisos
    if not request.user.is_superuser:
        if not hasattr(request.user, 'perfil') or not request.user.perfil.plataformas.filter(nombre=plataforma_limpia).exists():
            messages.error(request, f"Acceso denegado: No tienes permiso para acceder al módulo de {plataforma_limpia}.")
            return redirect('inicio')
    
    # 4. Actualizamos TODA la sesión
    request.session['canal_activo'] = plataforma_limpia
    tema = ESTILOS.get(plataforma_limpia, ESTILOS["Web"])
    request.session['color_actual'] = tema['color']
    request.session['icono_actual'] = tema['icono']
    
    # 5. Redirigimos a la vista real que el usuario quería ver
    return redirect(ruta_destino)

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
    from django.db.models import Sum
    from django.core.paginator import Paginator
    
    # 1. Capturamos las fechas desde la interfaz web (Buscador)
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    ingresos_db = IngresoPercheron.objects.all().order_by('id')
    
    # 2. Aplicamos el filtro de fecha a los ingresos
    if fecha_desde:
        ingresos_db = ingresos_db.filter(fecha_ingreso__gte=fecha_desde)
    if fecha_hasta:
        ingresos_db = ingresos_db.filter(fecha_ingreso__lte=fecha_hasta)
        
    productos_db = Producto.objects.all()
    dict_productos = {p.modelo: p for p in productos_db if p.modelo}
    
    # --- DICCIONARIO INTELIGENTE EN CASCADA ---
    dict_titulos_global = {}
    for ing in ingresos_db:
        if ing.modelo and ing.titulo and ing.titulo != 'Modelo nuevo / Sin título':
            dict_titulos_global[str(ing.modelo).strip().upper()] = ing.titulo
    for prod in productos_db:
        if prod.modelo and prod.titulo and prod.titulo != 'Modelo nuevo / Sin título':
            dict_titulos_global[str(prod.modelo).strip().upper()] = prod.titulo
    # ---------------------------------------------
    
    # 3. Preparamos los registros base de salidas
    out_ml_qs = SalidaMercadoLibre.objects.all()
    out_ml_jr_qs = SalidaMercadoLibreJunior.objects.all()
    out_fbl_qs = SalidaFalabella.objects.all()
    out_cdt_qs = SalidaCreditienda.objects.all()
    out_int_qs = SalidaIntercorp.objects.all()
    out_tk_qs = SalidaTiktok.objects.all()
    out_vl_qs = SalidaVentaLibre.objects.all()

    # 4. Aplicamos EXACTAMENTE el mismo filtro a las salidas (OUT)
    if fecha_desde:
        out_ml_qs = out_ml_qs.filter(fecha_salida__gte=fecha_desde)
        out_ml_jr_qs = out_ml_jr_qs.filter(fecha_salida__gte=fecha_desde)
        out_fbl_qs = out_fbl_qs.filter(fecha_salida__gte=fecha_desde)
        out_cdt_qs = out_cdt_qs.filter(fecha_salida__gte=fecha_desde)
        out_int_qs = out_int_qs.filter(fecha_salida__gte=fecha_desde)
        out_tk_qs = out_tk_qs.filter(fecha_salida__gte=fecha_desde)
        out_vl_qs = out_vl_qs.filter(fecha_salida__gte=fecha_desde)

    if fecha_hasta:
        out_ml_qs = out_ml_qs.filter(fecha_salida__lte=fecha_hasta)
        out_ml_jr_qs = out_ml_jr_qs.filter(fecha_salida__lte=fecha_hasta)
        out_fbl_qs = out_fbl_qs.filter(fecha_salida__lte=fecha_hasta)
        out_cdt_qs = out_cdt_qs.filter(fecha_salida__lte=fecha_hasta)
        out_int_qs = out_int_qs.filter(fecha_salida__lte=fecha_hasta)
        out_tk_qs = out_tk_qs.filter(fecha_salida__lte=fecha_hasta)
        out_vl_qs = out_vl_qs.filter(fecha_salida__lte=fecha_hasta)

    # 5. Ejecutamos las sumatorias filtradas
    out_ml_qs = out_ml_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_ml = {s['sku']: s['total'] for s in out_ml_qs if s['sku']}
    
    out_ml_jr_qs = out_ml_jr_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_ml_jr = {s['sku']: s['total'] for s in out_ml_jr_qs if s['sku']}

    out_fbl_qs = out_fbl_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_fbl = {s['sku']: s['total'] for s in out_fbl_qs if s['sku']}

    out_cdt_qs = out_cdt_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_cdt = {s['sku']: s['total'] for s in out_cdt_qs if s['sku']}

    out_int_qs = out_int_qs.values('sku').annotate(total=Sum('desc_und')) # Intercorp usa desc_und
    dict_out_int = {s['sku']: s['total'] for s in out_int_qs if s['sku']}

    out_tk_qs = out_tk_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_tk = {s['sku']: s['total'] for s in out_tk_qs if s['sku']}

    out_vl_qs = out_vl_qs.values('sku').annotate(total=Sum('descuento'))
    dict_out_vl = {s['sku']: s['total'] for s in out_vl_qs if s['sku']}
    
    registros_data = []
    
    # 6. Ensamblaje final de la tabla
    for ing in ingresos_db:
        prod = dict_productos.get(ing.modelo)
        
        marca_val = prod.marca if prod else 'SIN MARCA'
        ubicacion_val = prod.ubicacion if prod else 'SIN UBICACIÓN'
        
        mod_limpio = str(ing.modelo).strip().upper() if ing.modelo else ''
        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')
        
        out_ml = dict_out_ml.get(ing.sku, 0)
        out_ml2 = dict_out_ml_jr.get(ing.sku, 0)
        out_fbl = dict_out_fbl.get(ing.sku, 0)
        out_cdt = dict_out_cdt.get(ing.sku, 0)
        out_intcp = dict_out_int.get(ing.sku, 0)
        out_tk = dict_out_tk.get(ing.sku, 0)
        out_vl = dict_out_vl.get(ing.sku, 0)
        
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
            'titulo': titulo_val,
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
        'page_obj': page_obj,
        # Enviamos las fechas al HTML para que el calendario no se borre
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta
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

# ==========================================
# 1. PLATAFORMA MERCADO LIBRE
# ==========================================
@login_required
@verificar_acceso_plataforma('Mercado Libre')
def percheron_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Mercado Libre')
    from .models import SalidaMercadoLibre, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaMercadoLibre.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_mercadolibre.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

# ==========================================
# 2. PLATAFORMA MERCADO LIBRE JUNIOR
# ==========================================
@login_required
@verificar_acceso_plataforma('Mercado Libre - Junior')
def percheron_mercadolibre_junior(request):
    canal = request.session.get('canal_activo', 'Mercado Libre - Junior')
    from .models import SalidaMercadoLibreJunior, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaMercadoLibreJunior.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_mercadolibre_junior.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

# ==========================================
# 3. PLATAFORMA FALABELLA
# ==========================================
@login_required
@verificar_acceso_plataforma('Falabella')
def percheron_falabella(request):
    canal = request.session.get('canal_activo', 'Falabella')
    from .models import SalidaFalabella, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaFalabella.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_falabella.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })


@login_required
def buscar_modelo_falabella(request):
    modelo_query = request.GET.get('modelo', '').strip()
    try:
        from .models import IngresoPercheron, Producto, SalidaFalabella 
        
        skus_usados = SalidaFalabella.objects.values_list('sku', flat=True)
        resultados = IngresoPercheron.objects.filter(
            modelo__icontains=modelo_query
        ).exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
        
        productos_db = Producto.objects.all()
        dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().titulo or ""
            
        for r in resultados:
            mod_limpio = str(r.modelo).strip().upper() if r.modelo else ''
            prod = dict_prods.get(mod_limpio)
            marca_val = prod.marca if prod else 'S/N MARCA'
            
            fecha_str = '-'
            if r.fecha_ingreso:
                try: fecha_str = r.fecha_ingreso.strftime('%d/%m/%Y')
                except: fecha_str = str(r.fecha_ingreso)
                
            data.append({
                'sku': r.sku, 'marca': marca_val, 'fecha_ingreso': fecha_str,
                'serie': r.serie_nro or '-', 'costo': str(r.costo_unitario) if r.costo_unitario else '0.00',
                'proveedor': r.proveedor_motivo or '-', 'ingresado_por': r.creado_por or ''
            })
            
        return JsonResponse({
            'status': 'ok', 'producto': producto_nombre,
            'stock': resultados.count(), 'items': data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

# ==========================================
# 4. PLATAFORMA CREDITIENDA
# ==========================================
@login_required
@verificar_acceso_plataforma('Creditienda')
def percheron_creditienda(request):
    canal = request.session.get('canal_activo', 'Creditienda')
    from .models import SalidaCreditienda, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaCreditienda.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_creditienda.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

@login_required
def buscar_modelo_creditienda(request):
    modelo_query = request.GET.get('modelo', '').strip()
    try:
        from .models import IngresoPercheron, Producto, SalidaCreditienda 
        
        skus_usados = SalidaCreditienda.objects.values_list('sku', flat=True)
        resultados = IngresoPercheron.objects.filter(
            modelo__icontains=modelo_query
        ).exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
        
        productos_db = Producto.objects.all()
        dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().titulo or ""
            
        for r in resultados:
            mod_limpio = str(r.modelo).strip().upper() if r.modelo else ''
            prod = dict_prods.get(mod_limpio)
            marca_val = prod.marca if prod else 'S/N MARCA'
            
            fecha_str = '-'
            if r.fecha_ingreso:
                try: fecha_str = r.fecha_ingreso.strftime('%d/%m/%Y')
                except: fecha_str = str(r.fecha_ingreso)
                
            data.append({
                'sku': r.sku, 'marca': marca_val, 'fecha_ingreso': fecha_str,
                'serie': r.serie_nro or '-', 'costo': str(r.costo_unitario) if r.costo_unitario else '0.00',
                'proveedor': r.proveedor_motivo or '-', 'ingresado_por': r.creado_por or ''
            })
            
        return JsonResponse({
            'status': 'ok', 'producto': producto_nombre,
            'stock': resultados.count(), 'items': data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

# ==========================================
# 5. PLATAFORMA INTERCORP
# ==========================================
@login_required
@verificar_acceso_plataforma('Intercorp')
def percheron_intercorp(request):
    canal = request.session.get('canal_activo', 'Intercorp')
    from .models import SalidaIntercorp, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaIntercorp.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_intercorp.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

# ==========================================
# 6. PLATAFORMA TIK TOK
# ==========================================
@login_required
@verificar_acceso_plataforma('Tik tok')
def percheron_tiktok(request):
    canal = request.session.get('canal_activo', 'Tik tok')
    from .models import SalidaTiktok, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaTiktok.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_tiktok.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

@login_required
def buscar_modelo_tiktok(request):
    modelo_query = request.GET.get('modelo', '').strip()
    try:
        from .models import IngresoPercheron, Producto, SalidaTiktok 
        
        skus_usados = SalidaTiktok.objects.values_list('sku', flat=True)
        resultados = IngresoPercheron.objects.filter(
            modelo__icontains=modelo_query
        ).exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
        
        productos_db = Producto.objects.all()
        dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().titulo or ""
            
        for r in resultados:
            mod_limpio = str(r.modelo).strip().upper() if r.modelo else ''
            prod = dict_prods.get(mod_limpio)
            marca_val = prod.marca if prod else 'S/N MARCA'
            
            fecha_str = '-'
            if r.fecha_ingreso:
                try: fecha_str = r.fecha_ingreso.strftime('%d/%m/%Y')
                except: fecha_str = str(r.fecha_ingreso)
                
            data.append({
                'sku': r.sku, 'marca': marca_val, 'fecha_ingreso': fecha_str,
                'serie': r.serie_nro or '-', 'costo': str(r.costo_unitario) if r.costo_unitario else '0.00',
                'proveedor': r.proveedor_motivo or '-', 'ingresado_por': r.creado_por or ''
            })
            
        return JsonResponse({
            'status': 'ok', 'producto': producto_nombre,
            'stock': resultados.count(), 'items': data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# ==========================================
# 8. PLATAFORMA WEB
# ==========================================
@login_required
@verificar_acceso_plataforma('Web')
def percheron_web(request):
    canal = request.session.get('canal_activo', 'Web')
    from .models import SalidaWeb, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaWeb.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_web.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

@login_required
@csrf_exempt
def procesar_salidas_web(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        from .models import SalidaWeb, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaWeb.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Web',
                        usuario_que_elimino=request.user.username
                    )
                    
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
                    costo_html = float(sal.get('costo') or 0)
                    descuento_html = 1
                    nro_venta_html = sal.get('nro_ventas', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaWeb.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@csrf_exempt
def procesar_salidas_tiktok(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        from .models import SalidaTiktok, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA TIKTOK
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaTiktok.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Tik tok',
                        usuario_que_elimino=request.user.username
                    )
                    
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
                    costo_html = float(sal.get('costo') or 0)
                    descuento_html = 1
                    nro_venta_html = sal.get('nro_ventas', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaTiktok.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})



@login_required
def percheron_bci(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso exclusivo para BCI Autorizados.")
        return redirect('inicio')
        
    canal = request.session.get('canal_activo', 'Web')
    from .models import SalidaBCI, IngresoPercheron, Producto
    import json
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = {}
    for ing in IngresoPercheron.objects.all():
        if ing.modelo and ing.titulo and ing.titulo != 'Modelo nuevo / Sin título':
            dict_titulos_global[str(ing.modelo).strip().upper()] = ing.titulo
    for prod in productos_db:
        if prod.modelo and prod.titulo and prod.titulo != 'Modelo nuevo / Sin título':
            dict_titulos_global[str(prod.modelo).strip().upper()] = prod.titulo

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    page_obj = SalidaBCI.objects.all().order_by('-id')

    return render(request, 'inventario/percheron_bci.html', {
        'canal': canal, 'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global), 'page_obj': page_obj
    })

@login_required
@csrf_exempt
def procesar_salidas_bci(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        from .models import SalidaBCI, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # Validación de Concurrencia
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                skus_ya_vendidos = SalidaBCI.objects.filter(sku__in=skus_entrantes).values_list('sku', flat=True)
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs ya fueron descontados por otro usuario: {skus_repetidos}.'
                    })

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaBCI.objects.filter(id__in=eliminadas)
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
                    costo_html = float(sal.get('costo') or 0)
                    descuento_html = int(float(sal.get('desc_1und') or 1))
                    nro_venta_html = sal.get('nro_ventas', '')
                    tipo_venta_html = sal.get('tipo_venta', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaBCI.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, tipo_venta=tipo_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        return JsonResponse({'status': 'ok', 'message': f'Descontados: {modelos_afectados}. Devueltos: {modelos_restaurados}.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

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

# ==========================================
# REPORTES: TIKTOK
# ==========================================
@login_required
@verificar_acceso_plataforma('Tik tok')
def reporte_tiktok(request):
    canal = request.session.get('canal_activo', 'Tik tok')
    
    from .models import ReporteTiktok, Producto
    import json
    
    reportes = ReporteTiktok.objects.all().order_by('-fecha', '-id')
    
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p.titulo for p in productos_db if p.modelo}
    
    # MUY IMPORTANTE LA RUTA CORRECTA AQUÍ
    return render(request, 'reportes_plataformas/reporte_tiktok.html', {
        'canal': canal,
        'page_obj': reportes,
        'dict_prods_json': json.dumps(dict_prods)
    })

@login_required
@verificar_acceso_plataforma('Venta Libre')
def reporte_ventalibre(request):
    canal = request.session.get('canal_activo', 'Venta Libre')
    
    from .models import ReporteVentaLibre, Producto
    import json
    
    # 1. Traemos el historial de reportes ordenado
    reportes = ReporteVentaLibre.objects.all().order_by('-fecha', '-id')
    
    # 2. Diccionario para simular el BUSCARV del Producto en el frontend
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p.titulo for p in productos_db if p.modelo}
    
    # AQUÍ ESTÁ LA LÍNEA CORREGIDA
    return render(request, 'reportes_plataformas/reporte_ventalibre.html', {
        'canal': canal,
        'page_obj': reportes,
        'dict_prods_json': json.dumps(dict_prods)
    })
#hola
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
@verificar_acceso_plataforma('Tik tok')
def simulador_tiktok(request):
    canal = request.session.get('canal_activo', 'Tik tok')
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
                    
                    ubicacion_leida = str(fila.get('UBICACIÓN') or fila.get('UBICACION') or '').strip()
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
                        ubicacion=ubicacion_leida,
                        proveedor_motivo=proveedor_motivo,
                        creado_por=by_usuario
                    )
                    objetos_a_crear.append(obj)

                    if modelo:
                        key_ingreso = str(modelo).upper().replace(" ", "").replace("-", "")
                        prod = dict_productos.get(key_ingreso)
                        if prod:
                            prod.stock_actual += cantidad_val
                            if ubicacion_leida:
                                prod.ubicacion = ubicacion_leida
                            productos_a_actualizar.add(prod)

                if objetos_a_crear:
                    IngresoPercheron.objects.bulk_create(objetos_a_crear)

                for prod in productos_a_actualizar:
                    prod.save(update_fields=['stock_actual', 'ubicacion'])

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
        'SERIE / N°', 'COSTO UNT.', 'ING. x 1 und', 'UBICACIÓN', 'PROVEEDOR / MOTIVO', 'BY:'
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
        'INVENTARIO SSJ 2', 'MERCADO LIBRE', 'FALABELLA', 'CREDITIENDA', 'PÁGINA WEB', 'INTERCORP'
    ])
    
    for p in Producto.objects.all().order_by('id'):
        writer.writerow([
            p.modelo or '', 
            p.marca or '', 
            p.categoria or '', 
            p.titulo or '', 
            p.stock_actual, 
            'TRUE' if p.activo_inventario_ssj2 else 'FALSE',
            'TRUE' if p.activo_ml else 'FALSE',
            'TRUE' if p.activo_falabella else 'FALSE',
            'TRUE' if p.activo_creditienda else 'FALSE',
            'TRUE' if p.activo_web else 'FALSE',
            'TRUE' if p.activo_intercorp else 'FALSE'
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
                from .models import IngresoPercheron # Importamos el modelo de ingresos
                
                for item in referencias:
                    modelo_val = str(item.get('MODELO') or '').strip()
                    if not modelo_val:
                        continue
                        
                    titulo_nuevo = item.get('TÍTULO', '')
                    
                    # 1. Guarda en el Directorio de Modelos
                    obj, created = Producto.objects.get_or_create(
                        modelo=modelo_val, 
                        defaults={
                            'sku': f'SKU-{uuid.uuid4().hex[:8].upper()}', 
                            'titulo': titulo_nuevo
                        }
                    )
                    
                    obj.marca = item.get('MARCA', '')
                    obj.categoria = item.get('CATEGORÍA', '')
                    obj.titulo = titulo_nuevo
                    
                    obj.activo_inventario_ssj2 = True if item.get('INVENTARIO SSJ 2') == 'TRUE' else False
                    obj.activo_ml = True if item.get('MERCADO LIBRE') == 'TRUE' else False
                    obj.activo_falabella = True if item.get('FALABELLA') == 'TRUE' else False
                    obj.activo_creditienda = True if item.get('CREDITIENDA') == 'TRUE' else False
                    obj.activo_web = True if item.get('PÁGINA WEB') == 'TRUE' else False
                    obj.activo_intercorp = True if item.get('INTERCORP') == 'TRUE' else False
                    
                    obj.save()
                    
                    # 2. ¡LA MAGIA RETROACTIVA! 
                    # Busca todos los ingresos del pasado que tengan este modelo y les actualiza el título
                    if titulo_nuevo:
                        IngresoPercheron.objects.filter(modelo=modelo_val).update(titulo=titulo_nuevo)
                    
            return JsonResponse({'status': 'ok', 'message': '¡Directorio actualizado y títulos sincronizados con los ingresos del pasado!'})
            
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
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})
            
        from .models import SalidaMercadoLibre, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA MERCADO LIBRE
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaMercadoLibre.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    # --- 1. GUARDAR EVIDENCIA EN LA AUDITORÍA ---
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Mercado Libre',
                        usuario_que_elimino=request.user.username
                    )
                    
                    # --- 2. DEVOLVER EL STOCK NORMALMENTE ---
                    if registro.modelo:
                        key = str(registro.modelo).upper().replace(" ", "").replace("-", "")
                        conteo_restauraciones[key] = conteo_restauraciones.get(key, 0) + registro.descuento
                    
                    # --- 3. BORRAR REGISTRO ORIGINAL ---
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
        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

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
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})

        from .models import SalidaMercadoLibreJunior, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA ML JUNIOR
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaMercadoLibreJunior.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Mercado Libre - Junior',
                        usuario_que_elimino=request.user.username
                    )
                    
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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
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
        from .models import IngresoPercheron, Producto, SalidaIntercorp 
        
        # 1. Filtramos los SKUs que YA salieron en Intercorp para no volver a mostrarlos
        skus_usados = SalidaIntercorp.objects.values_list('sku', flat=True)
        
        # 2. Buscamos los ingresos disponibles
        resultados = IngresoPercheron.objects.filter(
            modelo__icontains=modelo_query
        ).exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
        
        # 3. Traemos el directorio de productos para sacar la marca correcta
        productos_db = Producto.objects.all()
        dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().titulo or ""
            
        for r in resultados:
            mod_limpio = str(r.modelo).strip().upper() if r.modelo else ''
            prod = dict_prods.get(mod_limpio)
            marca_val = prod.marca if prod else 'S/N MARCA'
            
            fecha_str = '-'
            if r.fecha_ingreso:
                try: fecha_str = r.fecha_ingreso.strftime('%d/%m/%Y')
                except: fecha_str = str(r.fecha_ingreso)
                
            data.append({
                'sku': r.sku,
                'marca': marca_val,
                'fecha_ingreso': fecha_str,
                'serie': r.serie_nro or '-',
                'costo': str(r.costo_unitario) if r.costo_unitario else '0.00',
                'proveedor': r.proveedor_motivo or '-',
                'ingresado_por': r.creado_por or ''
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
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        # *Asegúrate de que este sea el nombre correcto de tu modelo Intercorp*
        from .models import SalidaIntercorp, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA INTERCORP
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaIntercorp.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Intercorp',
                        usuario_que_elimino=request.user.username
                    )
                    
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
                    costo_html = float(sal.get('costo_unt') or 0)
                    descuento_html = 1
                    nro_venta_html = sal.get('nro_ventas', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaIntercorp.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    

# ==========================================
# 7. PLATAFORMA VENTA LIBRE
# ==========================================
@login_required
@verificar_acceso_plataforma('Venta Libre')
def percheron_ventalibre(request):
    canal = request.session.get('canal_activo', 'Venta Libre')
    from .models import SalidaVentaLibre, IngresoPercheron, Producto
    from django.core.paginator import Paginator
    import json
    
    # --- PAGINACIÓN DE 50 EN 50 ---
    salidas_list = SalidaVentaLibre.objects.all().order_by('-id')
    paginator = Paginator(salidas_list, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    # ---------------------------------
    
    skus_usados_global = obtener_todos_los_skus_usados()
    ingresos_db = IngresoPercheron.objects.exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados_global)
    productos_db = Producto.objects.all()
    dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()

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

        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Modelo nuevo / Sin título')

        dict_skus[ing.sku] = {
            'modelo': ing.modelo or '', 'titulo': titulo_val, 'serie': ing.serie_nro or '-',
            'costo': float(ing.costo_unitario) if ing.costo_unitario else 0.00,
            'fecha_ingreso': fecha_str, 'proveedor': ing.proveedor_motivo or '-',
            'registrado_por': ing.creado_por or '', 'marca': marca_val, 'stock_real': stock_val
        }

    return render(request, 'inventario/percheron_ventalibre.html', {
        'canal': canal,
        'page_obj': page_obj,
        'skus_json': json.dumps(dict_skus),
        'titulos_json': json.dumps(dict_titulos_global)
    })

@login_required
def buscar_modelo_ventalibre(request):
    modelo_query = request.GET.get('modelo', '').strip()
    try:
        from .models import IngresoPercheron, Producto, SalidaVentaLibre 
        
        skus_usados = SalidaVentaLibre.objects.values_list('sku', flat=True)
        resultados = IngresoPercheron.objects.filter(
            modelo__icontains=modelo_query
        ).exclude(sku__isnull=True).exclude(sku__exact='').exclude(sku__in=skus_usados)
        
        productos_db = Producto.objects.all()
        dict_prods = {str(p.modelo).strip().upper(): p for p in productos_db if p.modelo}
        
        data = []
        producto_nombre = ""
        if resultados.exists():
            producto_nombre = resultados.first().titulo or ""
            
        for r in resultados:
            mod_limpio = str(r.modelo).strip().upper() if r.modelo else ''
            prod = dict_prods.get(mod_limpio)
            marca_val = prod.marca if prod else 'S/N MARCA'
            
            fecha_str = '-'
            if r.fecha_ingreso:
                try: fecha_str = r.fecha_ingreso.strftime('%d/%m/%Y')
                except: fecha_str = str(r.fecha_ingreso)
                
            data.append({
                'sku': r.sku,
                'marca': marca_val,
                'fecha_ingreso': fecha_str,
                'serie': r.serie_nro or '-',
                'costo': str(r.costo_unitario) if r.costo_unitario else '0.00',
                'proveedor': r.proveedor_motivo or '-',
                'ingresado_por': r.creado_por or ''
            })
            
        return JsonResponse({
            'status': 'ok', 'producto': producto_nombre,
            'stock': resultados.count(), 'items': data
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
@csrf_exempt
def procesar_salidas_ventalibre(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        from .models import SalidaVentaLibre, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA VENTA LIBRE
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaVentaLibre.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Venta Libre',
                        usuario_que_elimino=request.user.username
                    )
                    
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
                    costo_html = float(sal.get('costo_unt') or 0)
                    descuento_html = 1
                    nro_venta_html = sal.get('nro_ventas', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaVentaLibre.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    

@login_required
@csrf_exempt
def guardar_reportes_masivos_ventalibre(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        from .models import ReporteVentaLibre
        from django.db import transaction
        
        data = json.loads(request.body)
        filas = data.get('filas', [])

        if not filas:
            return JsonResponse({'status': 'error', 'message': 'No hay datos para guardar.'})

        with transaction.atomic():
            for f in filas:
                ReporteVentaLibre.objects.create(
                    usuario=request.user,
                    fecha=f.get('fecha'),
                    mes_anio=f.get('mes_anio'),
                    asesor=f.get('asesor'),
                    tipo_cliente=f.get('tipo_cliente'),
                    dni_ruc=f.get('dni_ruc'),
                    comprobante=f.get('comprobante'),
                    nombre_razon_social=f.get('nombre_razon_social'),
                    marca=f.get('marca'),
                    categoria=f.get('categoria'),
                    almacen_sjl=f.get('almacen_sjl', False),
                    sku_almacen=f.get('sku_almacen'),
                    modelo=f.get('modelo'),
                    producto=f.get('producto'),
                    precio_u=float(f.get('precio_u') or 0),
                    cant=int(f.get('cant') or 1),
                    costo_envio=float(f.get('costo_envio') or 0),
                    p_total=float(f.get('p_total') or 0),
                    a_cuenta=float(f.get('a_cuenta') or 0),
                    restante=float(f.get('restante') or 0),
                    costo_x_prod=float(f.get('costo_x_prod') or 0),
                    und=int(f.get('und') or 1),
                    costo_x_prod_total=float(f.get('costo_x_prod_total') or 0),
                    flete=float(f.get('flete') or 0),
                    saldo_x_envio=float(f.get('saldo_x_envio') or 0),
                    ganancia=float(f.get('ganancia') or 0),
                    rentabilidad=str(f.get('rentabilidad', '0%'))
                )

        return JsonResponse({'status': 'ok', 'message': f'{len(filas)} filas guardadas con éxito.'})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})
    
@login_required
@csrf_exempt
def borrar_todos_los_reportes_ventalibre(request):
    if request.method == 'POST':
        from .models import ReporteVentaLibre
        ReporteVentaLibre.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': 'Se ha vaciado el reporte de Venta Libre.'})
    return JsonResponse({'status': 'error'})


@login_required
@csrf_exempt
def guardar_reportes_masivos_tiktok(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        from .models import ReporteTiktok
        from django.db import transaction
        
        data = json.loads(request.body)
        filas = data.get('filas', [])

        if not filas:
            return JsonResponse({'status': 'error', 'message': 'No hay datos para guardar.'})

        with transaction.atomic():
            for f in filas:
                ReporteTiktok.objects.create(
                    usuario=request.user,
                    venta_verificada=f.get('venta_verificada', False),
                    asesor=f.get('asesor'),
                    fecha=f.get('fecha'),
                    mes=f.get('mes'),
                    comprobante=f.get('comprobante'),
                    dni_ruc=f.get('dni_ruc'),
                    nombre_razon_social=f.get('nombre_razon_social'),
                    telefono=f.get('telefono'),
                    ciudad=f.get('ciudad'),
                    marca=f.get('marca'),
                    categoria=f.get('categoria'),
                    sku_almacen=f.get('sku_almacen'),
                    modelo=f.get('modelo'),
                    metodo_pago=f.get('metodo_pago'),
                    precio_live=float(f.get('precio_live') or 0),
                    cant=int(f.get('cant') or 1),
                    total=float(f.get('total') or 0),
                    a_cuenta=float(f.get('a_cuenta') or 0),
                    restante=float(f.get('restante') or 0),
                    producto=f.get('producto'),
                    precio=float(f.get('precio') or 0),
                    cantidad=int(f.get('cantidad') or 1),
                    p_total=float(f.get('p_total') or 0),
                    c_envio=float(f.get('c_envio') or 0),
                    flete=float(f.get('flete') or 0),
                    costo_producto=float(f.get('costo_producto') or 0),
                    ganancia=float(f.get('ganancia') or 0),
                    ganancia_con_envio=float(f.get('ganancia_con_envio') or 0),
                    rentabilidad=str(f.get('rentabilidad', '0%')),
                    delivery_a_cargo=f.get('delivery_a_cargo')
                )

        return JsonResponse({'status': 'ok', 'message': f'{len(filas)} filas guardadas con éxito en TikTok.'})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})
    

@login_required
@csrf_exempt
def borrar_todos_los_reportes_tiktok(request):
    if request.method == 'POST':
        from .models import ReporteTiktok
        ReporteTiktok.objects.all().delete()
        return JsonResponse({'status': 'ok', 'message': 'Se ha vaciado el reporte de TikTok.'})
    return JsonResponse({'status': 'error'})


@login_required
@csrf_exempt
def procesar_salidas_falabella(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})

        from .models import SalidaFalabella, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA FALABELLA
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaFalabella.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Falabella',
                        usuario_que_elimino=request.user.username
                    )
                    
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

                    SalidaFalabella.objects.create(
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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required
@csrf_exempt
def procesar_salidas_creditienda(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Método no permitido'})

    try:
        import json
        data = json.loads(request.body)
        salidas = data.get('salidas', [])
        eliminadas = data.get('eliminadas', []) 

        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'Sin datos para procesar.'})

        from .models import SalidaCreditienda, Producto
        from datetime import datetime
        from django.db import transaction

        with transaction.atomic():
            
            # ========================================================
            # 🛑 EL PORTERO: VALIDACIÓN DE CONCURRENCIA CREDITIENDA
            # ========================================================
            if salidas:
                skus_entrantes = [sal.get('sku', '').strip() for sal in salidas if sal.get('sku', '').strip()]
                
                # --- NUEVA VALIDACIÓN GLOBAL ANTI-CHOQUES ---
                skus_globales_usados = obtener_todos_los_skus_usados()
                skus_ya_vendidos = [sku for sku in skus_entrantes if sku in skus_globales_usados]
                
                if skus_ya_vendidos:
                    skus_repetidos = ", ".join(skus_ya_vendidos)
                    return JsonResponse({
                        'status': 'error', 
                        'message': f'¡ALTO! Los siguientes SKUs acaban de ser vendidos por otro usuario o en otra plataforma: {skus_repetidos}. Por favor, bórralos de tu lista y actualiza.'
                    })
                # ---------------------------------------------
            # ========================================================

            conteo_descuentos = {}
            conteo_restauraciones = {}

            if eliminadas:
                registros_viejos = SalidaCreditienda.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    
                    HistorialEliminacion.objects.create(
                        sku=registro.sku,
                        modelo=registro.modelo,
                        plataforma_origen='Creditienda',
                        usuario_que_elimino=request.user.username
                    )
                    
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
                    costo_html = float(sal.get('costo') or 0)
                    # OJO: Creditienda usa 'desc_1und' en el HTML
                    descuento_html = int(float(sal.get('desc_1und') or 1))
                    nro_venta_html = sal.get('nro_ventas', '')
                    by_html = sal.get('by', request.user.username)

                    SalidaCreditienda.objects.create(
                        sku=sku, modelo=modelo, titulo=titulo, fecha_salida=fecha_salida,
                        serie=serie, costo=costo_html, descuento=descuento_html,
                        nro_venta=nro_venta_html, creado_por=by_html
                    )

                    key = modelo.upper().replace(" ", "").replace("-", "")
                    if key:
                        conteo_descuentos[key] = conteo_descuentos.get(key, 0) + descuento_html

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

        total_descontado = sum(conteo_descuentos.values()) if conteo_descuentos else 0
        total_devuelto = sum(conteo_restauraciones.values()) if conteo_restauraciones else 0
        
        return JsonResponse({
            'status': 'ok', 
            'message': f'Unidades descontadas: {total_descontado}. Unidades devueltas: {total_devuelto}.'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    

def obtener_todos_los_skus_usados():
    """Recopila absolutamente todos los SKUs que ya han salido por cualquier plataforma"""
    skus = []
    skus += list(SalidaMercadoLibre.objects.values_list('sku', flat=True))
    skus += list(SalidaMercadoLibreJunior.objects.values_list('sku', flat=True))
    skus += list(SalidaFalabella.objects.values_list('sku', flat=True))
    skus += list(SalidaCreditienda.objects.values_list('sku', flat=True))
    skus += list(SalidaIntercorp.objects.values_list('sku', flat=True))
    skus += list(SalidaTiktok.objects.values_list('sku', flat=True))
    skus += list(SalidaVentaLibre.objects.values_list('sku', flat=True))

    try:
        from .models import SalidaWeb
        skus += list(SalidaWeb.objects.values_list('sku', flat=True))
    except:
        pass
    
    try:
        from .models import SalidaBCI
        skus += list(SalidaBCI.objects.values_list('sku', flat=True))
    except:
        pass
    
    return set(skus) # Devuelve una lista única de SKUs descontados globalmente


def obtener_diccionario_titulos_cache():
    # 1. Intentamos buscar el diccionario en la memoria rápida (Caché)
    dict_titulos = cache.get('memoria_titulos_globales')
    
    # 2. Si no existe (o ya caducó), lo construimos leyendo la base de datos
    if not dict_titulos:
        from .models import IngresoPercheron, Producto
        dict_titulos = {}
        
        # Leemos los ingresos
        for ing in IngresoPercheron.objects.all():
            if ing.modelo and ing.titulo and ing.titulo != 'Modelo nuevo / Sin título':
                dict_titulos[str(ing.modelo).strip().upper()] = ing.titulo
                
        # Leemos los productos
        for prod in Producto.objects.all():
            if prod.modelo and prod.titulo and prod.titulo != 'Modelo nuevo / Sin título':
                dict_titulos[str(prod.modelo).strip().upper()] = prod.titulo
                
        # 3. Lo guardamos en la Caché por 1 hora (3600 segundos)
        cache.set('memoria_titulos_globales', dict_titulos, 3600)
        
    return dict_titulos


@login_required
def exportar_registros_pdf(request):
    from django.db.models import Sum
    from django.utils import timezone
    
    # 1. Capturamos las fechas para que el PDF salga filtrado igual que en la pantalla
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    ingresos_db = IngresoPercheron.objects.all().order_by('id')
    
    if fecha_desde: ingresos_db = ingresos_db.filter(fecha_ingreso__gte=fecha_desde)
    if fecha_hasta: ingresos_db = ingresos_db.filter(fecha_ingreso__lte=fecha_hasta)
        
    productos_db = Producto.objects.all()
    dict_productos = {p.modelo: p for p in productos_db if p.modelo}
    
    dict_titulos_global = obtener_diccionario_titulos_cache()
    
    out_ml_qs, out_ml_jr_qs, out_fbl_qs, out_cdt_qs, out_int_qs, out_tk_qs, out_vl_qs = (
        SalidaMercadoLibre.objects.all(), SalidaMercadoLibreJunior.objects.all(),
        SalidaFalabella.objects.all(), SalidaCreditienda.objects.all(),
        SalidaIntercorp.objects.all(), SalidaTiktok.objects.all(),
        SalidaVentaLibre.objects.all()
    )

    if fecha_desde:
        out_ml_qs = out_ml_qs.filter(fecha_salida__gte=fecha_desde)
        out_ml_jr_qs = out_ml_jr_qs.filter(fecha_salida__gte=fecha_desde)
        out_fbl_qs = out_fbl_qs.filter(fecha_salida__gte=fecha_desde)
        out_cdt_qs = out_cdt_qs.filter(fecha_salida__gte=fecha_desde)
        out_int_qs = out_int_qs.filter(fecha_salida__gte=fecha_desde)
        out_tk_qs = out_tk_qs.filter(fecha_salida__gte=fecha_desde)
        out_vl_qs = out_vl_qs.filter(fecha_salida__gte=fecha_desde)

    if fecha_hasta:
        out_ml_qs = out_ml_qs.filter(fecha_salida__lte=fecha_hasta)
        out_ml_jr_qs = out_ml_jr_qs.filter(fecha_salida__lte=fecha_hasta)
        out_fbl_qs = out_fbl_qs.filter(fecha_salida__lte=fecha_hasta)
        out_cdt_qs = out_cdt_qs.filter(fecha_salida__lte=fecha_hasta)
        out_int_qs = out_int_qs.filter(fecha_salida__lte=fecha_hasta)
        out_tk_qs = out_tk_qs.filter(fecha_salida__lte=fecha_hasta)
        out_vl_qs = out_vl_qs.filter(fecha_salida__lte=fecha_hasta)

    dict_out_ml = {s['sku']: s['total'] for s in out_ml_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    dict_out_ml_jr = {s['sku']: s['total'] for s in out_ml_jr_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    dict_out_fbl = {s['sku']: s['total'] for s in out_fbl_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    dict_out_cdt = {s['sku']: s['total'] for s in out_cdt_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    dict_out_int = {s['sku']: s['total'] for s in out_int_qs.values('sku').annotate(total=Sum('desc_und')) if s['sku']}
    dict_out_tk = {s['sku']: s['total'] for s in out_tk_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    dict_out_vl = {s['sku']: s['total'] for s in out_vl_qs.values('sku').annotate(total=Sum('descuento')) if s['sku']}
    
    registros_data = []
    for ing in ingresos_db:
        prod = dict_productos.get(ing.modelo)
        marca_val = prod.marca if prod else 'SIN MARCA'
        mod_limpio = str(ing.modelo).strip().upper() if ing.modelo else ''
        titulo_val = dict_titulos_global.get(mod_limpio, ing.titulo or 'Sin título')
        
        out_ml = dict_out_ml.get(ing.sku, 0)
        out_ml2 = dict_out_ml_jr.get(ing.sku, 0)
        out_fbl = dict_out_fbl.get(ing.sku, 0)
        out_cdt = dict_out_cdt.get(ing.sku, 0)
        out_intcp = dict_out_int.get(ing.sku, 0)
        out_tk = dict_out_tk.get(ing.sku, 0)
        out_vl = dict_out_vl.get(ing.sku, 0)
        
        total_out = out_ml + out_fbl + out_cdt + out_vl + out_tk + out_intcp + out_ml2
        stock_val = ing.cantidad - total_out
        
        registros_data.append({
            'sku': ing.sku, 'marca': marca_val, 'fecha_ingreso': ing.fecha_ingreso,
            'modelo': ing.modelo, 'titulo': titulo_val, 'in_cant': ing.cantidad,
            'out_ml': out_ml, 'out_fbl': out_fbl, 'out_cdt': out_cdt, 'out_vl': out_vl,
            'out_tk': out_tk, 'out_intcp': out_intcp, 'out_ml2': out_ml2, 'stock': stock_val
        })

    # Armamos el contexto para el PDF
    context = {
        'registros': registros_data,
        'fecha_impresion': timezone.now(),
        'usuario': request.user.username,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta
    }
    
    # 2. Convertimos a PDF (La plantilla la crearemos en el paso 4)
    pdf = render_to_pdf('inventario/pdf_kardex.html', context)
    
    if pdf:
        # Esto hace que el navegador descargue el archivo con un nombre bonito
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Kardex_General_{timezone.now().strftime('%d%m%Y')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("Error al generar el PDF.")


@login_required
def exportar_salidas_pdf(request):
    from django.utils import timezone
    from django.http import HttpResponse
    from .utils import render_to_pdf
    
    canal = request.session.get('canal_activo', 'Mercado Libre')
    
    # 1. Elegimos el modelo correcto según el canal
    if canal == 'Mercado Libre': from .models import SalidaMercadoLibre as ModeloSalida
    elif canal == 'Mercado Libre - Junior': from .models import SalidaMercadoLibreJunior as ModeloSalida
    elif canal == 'Falabella': from .models import SalidaFalabella as ModeloSalida
    elif canal == 'Creditienda': from .models import SalidaCreditienda as ModeloSalida
    elif canal == 'Intercorp': from .models import SalidaIntercorp as ModeloSalida
    elif canal == 'Tik tok': from .models import SalidaTiktok as ModeloSalida
    elif canal == 'Venta Libre': from .models import SalidaVentaLibre as ModeloSalida
    elif canal == 'Web': from .models import SalidaWeb as ModeloSalida
    else: from .models import SalidaMercadoLibre as ModeloSalida

    salidas = ModeloSalida.objects.all().order_by('-id')
    
    # 2. Normalizamos los datos (ya que algunas tablas usan nombres de columnas diferentes)
    registros_data = []
    for s in salidas:
        registros_data.append({
            'sku': s.sku,
            'modelo': s.modelo,
            'titulo': s.titulo,
            'fecha_salida': s.fecha_salida,
            'serie': getattr(s, 'serie', '-'),
            'costo': getattr(s, 'costo', getattr(s, 'costo_unt', 0)),
            'descuento': getattr(s, 'descuento', getattr(s, 'desc_und', 1)),
            'nro_venta': getattr(s, 'nro_venta', getattr(s, 'nro_ventas', '-')),
            'tipo_venta': getattr(s, 'tipo_venta', '-'),
            'by': getattr(s, 'creado_por', getattr(s, 'by', '-'))
        })

    context = {
        'registros': registros_data,
        'canal': canal,
        'fecha_impresion': timezone.now(),
        'usuario': request.user.username,
    }
    
    pdf = render_to_pdf('inventario/pdf_salidas.html', context)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        nombre_limpio = canal.replace(' ', '_').replace('-', '')
        filename = f"Salidas_{nombre_limpio}_{timezone.now().strftime('%d%m%Y')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    return HttpResponse("Error al generar el PDF de Salidas.")


@login_required
def requerimientos_alertas_view(request):
    from .models import RequerimientoAlerta
    requerimientos = RequerimientoAlerta.objects.all()
    
    context = {
        'requerimientos': requerimientos,
        'canal': request.session.get('canal_activo', 'Mercado Libre'),
    }
    return render(request, 'inventario/req_alertas.html', context)



@login_required
def req_observaciones_web_view(request):
    from .models import ObservacionWeb
    observaciones = ObservacionWeb.objects.all()
    context = {
        'observaciones': observaciones,
        'canal': request.session.get('canal_activo', 'Mercado Libre'),
    }
    return render(request, 'inventario/req_observaciones_web.html', context)

@login_required
def req_pagina_web_view(request):
    from .models import EvaluacionPrecioWeb
    evaluaciones = EvaluacionPrecioWeb.objects.all()
    context = {
        'evaluaciones': evaluaciones,
        'canal': request.session.get('canal_activo', 'Mercado Libre'),
    }
    return render(request, 'inventario/req_pagina_web.html', context)


@login_required
def guardar_requerimientos_alertas(request):
    from .models import RequerimientoAlerta
    if request.method == 'POST':
        try:
            datos = json.loads(request.body)
            
            # Como funciona igual que Excel, borramos el historial anterior 
            # y guardamos exactamente lo que el usuario tiene en pantalla
            RequerimientoAlerta.objects.all().delete()
            
            for fila in datos:
                RequerimientoAlerta.objects.create(
                    fecha_solicitud=fila.get('fecha_solicitud') or None,
                    solicitado_por=fila.get('solicitado_por'),
                    cantidad=fila.get('cantidad') or 1,
                    producto_solicitado=fila.get('producto_solicitado'),
                    observaciones=fila.get('observaciones'),
                    plataforma_concepto=fila.get('plataforma_concepto'),
                    fecha_entrega=fila.get('fecha_entrega') or None,
                    comentarios_compras=fila.get('comentarios_compras'),
                    compra_realizada=fila.get('compra_realizada', False),
                    agotado=fila.get('agotado', False)
                )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no válido'})

@login_required
def guardar_observaciones_web(request):
    from .models import ObservacionWeb
    if request.method == 'POST':
        try:
            datos = json.loads(request.body)
            
            # Borra lo anterior y sobrescribe (para que funcione igual que un Excel)
            ObservacionWeb.objects.all().delete()
            
            for fila in datos:
                ObservacionWeb.objects.create(
                    fecha_reporte=fila.get('fecha_reporte') or None,
                    asesor=fila.get('asesor'),
                    tipo_observacion=fila.get('tipo_observacion'),
                    comentarios=fila.get('comentarios'),
                    modelo=fila.get('modelo'),
                    link=fila.get('link'),
                    corregido=fila.get('corregido', False)
                )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no válido'})

@login_required
def guardar_evaluaciones_web(request):
    from .models import EvaluacionPrecioWeb
    import json
    if request.method == 'POST':
        try:
            datos = json.loads(request.body)
            
            # Borra lo anterior y sobrescribe (modo Excel)
            EvaluacionPrecioWeb.objects.all().delete()
            
            for fila in datos:
                EvaluacionPrecioWeb.objects.create(
                    marca=fila.get('marca'),
                    categoria=fila.get('categoria'),
                    modelo=fila.get('modelo'),
                    producto=fila.get('producto'),
                    precio_tachado=fila.get('precio_tachado', 0),
                    precio_web=fila.get('precio_web', 0),
                    precio_cyber=fila.get('precio_cyber', 0),
                    costo_producto=fila.get('costo_producto', 0),
                    ganancia_cyber=fila.get('ganancia_cyber', 0),
                    ganancia_web=fila.get('ganancia_web', 0),
                    rentabilidad=fila.get('rentabilidad', 0)
                )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no válido'})

@login_required
def guardar_referencia_costos_web(request):
    from .models import CostoReferencial
    import json
    
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            tc_dolar = payload.get('tc_dolar', 3.80)
            datos = payload.get('datos', [])

            # Forzar el guardado del Dólar en sesión
            request.session['tc_dolar_referencial'] = str(tc_dolar)
            request.session.modified = True 
            
            CostoReferencial.objects.all().delete()
            
            for fila in datos:
                # EXTRACCIÓN POR FUERZA BRUTA: Convertimos todo a texto, limpiamos símbolos y forzamos a decimal (float)
                try:
                    c_cero = float(str(fila.get('costo_cero_soles', '0')).replace('S/', '').replace(',', '').strip() or 0)
                except:
                    c_cero = 0.0

                try:
                    c_dolar = float(str(fila.get('costo_u_dolares', '0')).replace('$', '').replace(',', '').strip() or 0)
                except:
                    c_dolar = 0.0

                try:
                    c_conv = float(str(fila.get('costo_u_convertido', '0')).replace('S/', '').replace(',', '').strip() or 0)
                except:
                    c_conv = 0.0

                CostoReferencial.objects.create(
                    modelo=fila.get('modelo', ''),
                    producto=fila.get('producto', ''),
                    costo_cero_soles=c_cero,
                    costo_u_dolares=c_dolar,
                    costo_u_convertido=c_conv
                )
                
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Método no válido'})

@login_required
def referencia_costos_web_view(request):
    from .models import CostoReferencial
    
    # 1. Traemos la información guardada en la base de datos
    costos = CostoReferencial.objects.all()
    
    # 2. Leemos el dólar guardado en la memoria de la sesión (o 3.80 por defecto)
    tc_dolar = request.session.get('tc_dolar_referencial', '3.80')
    
    context = {
        'costos': costos,
        'tc_dolar': tc_dolar,
        'canal': request.session.get('canal_activo', 'Mercado Libre'),
    }
    return render(request, 'inventario/referencia_costos_web.html', context)