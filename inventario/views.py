import json
import uuid
import csv
import json
import os
from datetime import datetime
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from .models import Electrodomestico, Plataforma, Producto, MovimientoPercheron, SimulacionMercadoLibre, ReferenciaComision, ReferenciaCosto, ReporteMercadoLibre, IngresoPercheron, SalidaMercadoLibre,SimulacionMercadoLibre

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
    canal = request.session.get('canal_activo', 'Percheron')
    
    # Paginación normal de los ingresos
    registros_lista = IngresoPercheron.objects.all().order_by('id')
    paginator = Paginator(registros_lista, 100) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # === NUEVA LÓGICA: DICCIONARIO DE TÍTULOS ===
    # Traemos todos los productos y armamos un diccionario { 'EPS10': 'VAPORIZADOR...', ... }
    productos_db = Producto.objects.all()
    dict_titulos = {p.modelo: p.titulo for p in productos_db if p.modelo}

    return render(request, 'inventario/percheron_ingresos.html', {
        'canal': canal,
        'page_obj': page_obj,
        'titulos_json': json.dumps(dict_titulos) # Lo enviamos al HTML
    })

from django.db.models import Sum

@login_required
def percheron_registros(request):
    canal = request.session.get('canal_activo', 'Percheron')
    
    # 1. Obtenemos TODOS los ingresos (La hoja IN)
    ingresos_db = IngresoPercheron.objects.all().order_by('id')
    
    # 2. Obtenemos los Modelos para hacer el BUSCARV de Marca/Ubicación
    productos_db = Producto.objects.all()
    dict_productos = {p.modelo: p for p in productos_db if p.modelo}
    
    # =========================================================
    # 3. LA MAGIA: CONECTAMOS LAS SALIDAS DE MERCADO LIBRE
    # =========================================================
    # Agrupamos todas las salidas de ML y sumamos el descuento por cada SKU
    salidas_ml_agrupadas = SalidaMercadoLibre.objects.values('sku').annotate(total_desc=Sum('descuento'))
    dict_out_ml = {s['sku']: s['total_desc'] for s in salidas_ml_agrupadas if s['sku']}
    
    registros_data = []
    
    # 4. Recorremos fila por fila cruzando la información
    for ing in ingresos_db:
        prod = dict_productos.get(ing.modelo)
        
        marca_val = prod.marca if prod else 'SIN MARCA'
        ubicacion_val = prod.ubicacion if prod else 'SIN UBICACIÓN'
        
        # === AQUI SE APLICA EL DESCUENTO AUTOMÁTICO ===
        # Va a buscar el SKU en el diccionario de salidas de Mercado Libre
        out_ml = dict_out_ml.get(ing.sku, 0)
        
        # Las demás plataformas siguen en 0 hasta que las vayamos programando
        out_fbl = 0
        out_cdt = 0
        out_vl = 0
        out_tk = 0
        out_intcp = 0
        out_ml2 = 0
        
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
        
    # 5. Paginación
    paginator = Paginator(registros_data, 100) # Muestra 100 registros por página
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
    
    # 1. ORDENAMOS POR ID (Respeta el orden de tu Excel)
    if query_search:
        modelos_db = Producto.objects.filter(
            modelo__icontains=query_search
        ).order_by('id')
    else:
        modelos_db = Producto.objects.all().order_by('id')
    
    # 2. DEVOLVEMOS LA PAGINACIÓN (Carga rápida sin lag de CSS)
    # 100 es un número perfecto: carga rápido y muestra bastantes datos
    from django.core.paginator import Paginator
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
    
    # Dejamos la exportación vacía también por ahora
    registros = []
    
    for r in registros:
        pass
        
    return response

# =========================================================
# 4. SECCIÓN PERCHERÓN: PLATAFORMAS ESPECÍFICAS
# =========================================================


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
            
            if plataforma == 'Mercado Libre':
                # 🚀 YA NO BORRAMOS LA BASE DE DATOS AQUÍ
                
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

                    # Preparamos los datos a guardar
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

                    # Si el producto ya existe (por código MPE), se actualiza. Si no, se crea.
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
def reporte_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Web')
    
    # 1. Capturamos los parámetros de búsqueda y fechas que vienen del HTML
    query_search = request.GET.get('q', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')

    # 2. Obtenemos todas las ventas ordenadas por FECHA (de la más antigua a la más nueva)
    # y luego por ID para mantener un orden consistente en ventas del mismo día
    ventas_todas = ReporteMercadoLibre.objects.all().order_by('fecha', 'id')

    # 3. Aplicamos el filtro de búsqueda por NRO. ORDEN o SKU
    if query_search:
        ventas_todas = ventas_todas.filter(
            Q(nro_orden__icontains=query_search) | 
            Q(sku_almacen__icontains=query_search)
        )
    
    # 4. Aplicamos los filtros de fecha (desde - hasta)
    if fecha_inicio:
        ventas_todas = ventas_todas.filter(fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_todas = ventas_todas.filter(fecha__lte=fecha_fin)

    # 5. PAGINACIÓN: Dividimos los resultados en bloques de 40
    paginator = Paginator(ventas_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # === NUEVO: AÑADIR ESTAS LÍNEAS PARA EL BUSCARV DE PRODUCTO ===
    # Extraemos todos los modelos (códigos) y su descripción de producto
    costos_db = ReferenciaCosto.objects.all()
    diccionario_productos = {str(c.codigo).strip().upper(): c.producto for c in costos_db if c.codigo}
    diccionario_productos_json = json.dumps(diccionario_productos)
    # ===============================================================

    # 6. Pasamos las variables al HTML (incluyendo la ruta de tu carpeta que es reportes_plataformas)
    return render(request, 'reportes_plataformas/reporte_mercadolibre.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search,
        'diccionario_productos_json': diccionario_productos_json
    })

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
# 7. SIMULADORES Y REFERENCIAS
# =========================================================

from django.db.models import Q

@login_required
def simulador_mercadolibre(request):
    canal = request.session.get('canal_activo', 'Web')
    
    # 1. Capturamos lo que el usuario escriba en el buscador
    query_search = request.GET.get('q', '')

    # 2. Obtenemos las simulaciones base del usuario
    simulaciones_todas = SimulacionMercadoLibre.objects.filter(usuario=request.user)
    
    # 3. Aplicamos el filtro si el usuario buscó algún código (Cód. Pub o Cód. Prod)
    if query_search:
        simulaciones_todas = simulaciones_todas.filter(
            Q(cod_publicacion__icontains=query_search) | 
            Q(cod_producto__icontains=query_search)
        )
        
    # 4. Ordenamos para la paginación (vital para que no se rompa al cambiar de página)
    simulaciones_todas = simulaciones_todas.order_by('id')
    
    # 1. MAPA DE COMISIONES
    comisiones_ref = ReferenciaComision.objects.all()
    mapa_comisiones = {}
    for ref in comisiones_ref:
        if ref.sub_categoria:
            mapa_comisiones[ref.sub_categoria.upper().strip()] = float(ref.comision)
        if ref.categoria and ref.categoria.upper().strip() not in mapa_comisiones:
            mapa_comisiones[ref.categoria.upper().strip()] = float(ref.comision)

    # 2. MAPA DE COSTOS
    costos_ref = ReferenciaCosto.objects.all()
    mapa_costos = {}
    for ref in costos_ref:
        if ref.codigo:
            mapa_costos[ref.codigo.upper().strip()] = float(ref.costo_cero)

    mapa_comisiones_json = json.dumps(mapa_comisiones)
    mapa_costos_json = json.dumps(mapa_costos)
    
    # 🚀 PAGINACIÓN: Dividimos la lista (filtrada o completa) en bloques de 50
    paginator = Paginator(simulaciones_todas, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Pre-cruzamos los datos SOLO para los 50 de esta página (Súper rápido)
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
        'query_search': query_search  # Pasamos la búsqueda al HTML para mantenerla en la cajita
    })

@login_required
def referencia_comisiones(request):
    canal = request.session.get('canal_activo', 'Web')
    
    # 1. Buscador
    query_search = request.GET.get('q', '')

    # 2. Obtenemos todas las referencias ordenadas
    comisiones_todas = ReferenciaComision.objects.all().order_by('id')

    # 3. Aplicamos el filtro si se buscó algo
    if query_search:
        comisiones_todas = comisiones_todas.filter(
            Q(sub_categoria__icontains=query_search) | 
            Q(categoria__icontains=query_search)
        )

    # 4. Paginación de 40 en 40
    paginator = Paginator(comisiones_todas, 40) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Pasamos todo al HTML
    return render(request, 'inventario/referencia_comisiones.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search
    })

@login_required
def guardar_comisiones(request):
    if request.method == 'POST':
        messages.success(request, "Las comisiones han sido actualizadas.")
        return redirect('referencia_comisiones')
    return redirect('referencia_comisiones')

@login_required
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
def referencia_costos(request):
    canal = request.session.get('canal_activo', 'Web')
    
    # 1. Capturamos lo que el usuario escriba en el buscador
    query_search = request.GET.get('q', '')

    # 2. Obtenemos todos los costos ordenados por código
    costos_todos = ReferenciaCosto.objects.all().order_by('codigo')

    # 3. Aplicamos el filtro a la base de datos si el usuario buscó algo
    if query_search:
        costos_todos = costos_todos.filter(
            Q(codigo__icontains=query_search) | 
            Q(producto__icontains=query_search)
        )

    # 4. PAGINACIÓN: Dividimos la lista (filtrada o completa) en bloques de 50
    paginator = Paginator(costos_todos, 50) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Pasamos 'page_obj' y 'query_search' al HTML
    return render(request, 'inventario/referencia_costos.html', {
        'canal': canal, 
        'page_obj': page_obj,
        'query_search': query_search
    })

@login_required
def guardar_costos_masivos(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            filas_costos = data.get('referencias', [])
            
            for fila in filas_costos:
                codigo = fila.get('CÓDIGO', '').strip()
                producto = fila.get('PRODUCTO', '').strip()
                
                # Función para limpiar números de cualquier símbolo de moneda
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
def eliminar_costos_masivos(request):
    if request.method == 'POST':
        try:
            ReferenciaCosto.objects.all().delete()
            return JsonResponse({'status': 'ok', 'message': 'Todos los costos han sido eliminados correctamente.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'}, status=405)


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

@login_required
def descargar_plantilla_simulador(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_simulador_mercadolibre.csv"'

    # Esto es crucial para que Excel abra bien los caracteres especiales
    response.write('\ufeff'.encode('utf8'))

    writer = csv.writer(response, delimiter=';')

    # ¡AQUÍ ESTÁ LA CORRECCIÓN! 
    # Estas son las verdaderas columnas de tu Simulador de Costos
    writer.writerow([
        'ITEM TYPE', 'LINK', 'ESTADO', 'CÓD. PUB', 'TIPO', 
        'CÓD. PROD', 'CATEGORIA', 'MARCA', 'PRODUCTO', 'P. TACHADO', 
        '% DSCTO', 'P. VENTA', 'ENVÍO', '% NUEVA COM', 'COM (S/)', 
        'PAGO NETO', 'COSTO', 'GANANCIA', 'RTBLD%', 'MPE'
    ])

    return response

@login_required
def descargar_plantilla_costos(request):
    # Configuramos la respuesta para que el navegador sepa que es un archivo descargable
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="plantilla_referencia_costos.csv"'

    # Creamos el escritor CSV
    writer = csv.writer(response)
    
    # Escribimos la fila principal con los títulos exactos que lee tu JavaScript
    writer.writerow(['CÓDIGO', 'PRODUCTO', 'COSTO CERO', 'COSTO U. ($)', 'COSTO U. ($ ► S/.)'])
    
    # (Opcional) Agregamos una fila de ejemplo para guiar al usuario
    writer.writerow(['SKU-EJEMPLO', 'Producto de Prueba', '10.50', '15.00', ''])

    return response


@login_required
def descargar_plantilla_reporte_ml(request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="plantilla_reportes_mercadolibre.csv"'

    # Esto es crucial para que Excel abra bien los caracteres especiales como la "Ñ" y tildes
    response.write('\ufeff'.encode('utf8'))
    
    # AQUÍ ESTÁ LA MAGIA: delimiter=';' fuerza a Excel a separar las celdas
    writer = csv.writer(response, delimiter=';')
    
    # Cabeceras exactas de tu reporte
    writer.writerow([
        'FECHA', 'MES Y AÑO', 'NRO. ORDEN', 'COMPROBANTE', 'TIPO DE VENTA', 
        'MARCA', 'CATEGORIA', 'SKU ALMACEN', 'MODELO', 'PRODUCTO', 
        'CANT.', 'PRECIO', 'TOTAL V.', '%CARGO x VENTA', 'URBANO', 
        'FLEX', 'TOTAL PAGADO', 'COSTO x PRODUCTO', 'UND', 'COSTO TOTAL', 
        'COSTO ENTREGA FLEX', 'GANANCIA', 'RENTABILIDAD %', 'DISTRITO', 
        'DIRECCIÓN', 'REPARTIDOR', 'CELULAR DEL CLIENTE', 'MSJ DE AGRADECIMIENTO'
    ])
    
    # Fila de ejemplo
    writer.writerow([
        '15/06/2026', 'JUNIO 2026', 'ML-123456789', 'B001-00123', 'CATALOGO', 
        'OSTER', 'LICUADORA', 'SKU-OST-001', 'MOD-123', 'Licuadora Oster Clásica', 
        '1', '150.00', '150.00', '10.50', '0.00', 
        '10.00', '129.50', '80.00', '1', '80.00', 
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

            # --- MAGIA ANTI-BORRADO Y ANTI ALT+ENTER ---
            def get_best_val(val_antiguo, val_nuevo):
                # Elimina saltos de linea (Alt+Enter) y limpia el texto
                v_antiguo = str(val_antiguo or '').replace('\n', '').replace('\r', '').strip()
                v_nuevo = str(val_nuevo or '').replace('\n', '').replace('\r', '').strip()
                
                # Considera vacíos los "---" o nulos
                if v_antiguo in ['', '---', '-', 'None', 'null', 'NaN']: v_antiguo = ''
                if v_nuevo in ['', '---', '-', 'None', 'null', 'NaN']: v_nuevo = ''
                
                # Si el nuevo dato es válido, lo usamos. Si viene vacío, RESCATAMOS el antiguo.
                return v_nuevo if v_nuevo else v_antiguo

            # Obtenemos los números de orden limpios
            nros_ordenes_entrantes = [str(f.get('NRO. ORDEN', '')).replace('\n', '').strip() for f in filas_ventas if f.get('NRO. ORDEN', '').strip()]
            
            existentes_en_db = {
                venta.nro_orden: venta 
                for venta in ReporteMercadoLibre.objects.filter(nro_orden__in=nros_ordenes_entrantes)
            }

            ventas_unicas = {}
            
            for fila in filas_ventas:
                # Limpiamos el Nro de Orden por si trae un salto de línea invisible
                nro_orden = str(fila.get('NRO. ORDEN', '')).replace('\n', '').strip()
                if not nro_orden: 
                    continue

                db_obj = existentes_en_db.get(nro_orden)
                
                # Aplicamos la protección a tus campos clave
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
                    try:
                        return float(str(val).replace(',', '').strip() or 0)
                    except ValueError:
                        return 0.00
                        
                def to_int(val):
                    try:
                        return int(str(val).strip() or 0)
                    except ValueError:
                        return 0

                obj = ReporteMercadoLibre(
                    nro_orden=nro_orden,
                    fecha=fecha_formateada or '2026-01-01',
                    mes_anio=fila.get('MES Y AÑO', '').strip(),
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
                
                # Fusión de filas duplicadas dentro del mismo Excel
                if nro_orden in ventas_unicas:
                    existente = ventas_unicas[nro_orden]
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
                    'fecha', 'mes_anio', 'comprobante', 'tipo_venta', 'marca',
                    'categoria', 'sku_almacen', 'modelo', 'producto', 'cantidad',
                    'precio', 'total_venta', 'cargo_venta', 'urbano', 'flex',
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
                # =========================================================
                # PRE-CARGAR PRODUCTOS PARA BÚSQUEDA Y ACTUALIZACIÓN RÁPIDA
                # =========================================================
                productos_db = Producto.objects.all()
                dict_productos = {}
                for p in productos_db:
                    if p.modelo:
                        key_prod = p.modelo.upper().replace(" ", "").replace("-", "")
                        dict_productos[key_prod] = p
                
                productos_a_actualizar = set() # Aquí guardaremos los productos que cambiaron su stock

                # =========================================================
                # 1. ELIMINAR LOS REGISTROS SOLICITADOS Y RESTAR STOCK
                # =========================================================
                if eliminadas:
                    ids_a_eliminar = [int(i) for i in eliminadas if str(i).isdigit()]
                    if ids_a_eliminar:
                        registros_viejos = IngresoPercheron.objects.filter(id__in=ids_a_eliminar)
                        
                        # Restamos el stock antes de borrarlos
                        for reg in registros_viejos:
                            if reg.modelo:
                                key_reg = str(reg.modelo).upper().replace(" ", "").replace("-", "")
                                prod = dict_productos.get(key_reg)
                                if prod:
                                    prod.stock_actual = max(prod.stock_actual - (reg.cantidad or 1), 0)
                                    productos_a_actualizar.add(prod)
                        
                        # Ahora sí, los eliminamos de la BD
                        registros_viejos.delete()

                objetos_a_crear = []
                
                # =========================================================
                # 2. PROCESAR DATOS NUEVOS Y SUMAR STOCK
                # =========================================================
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

                    # Aumentar stock en el diccionario
                    if modelo:
                        key_ingreso = str(modelo).upper().replace(" ", "").replace("-", "")
                        prod = dict_productos.get(key_ingreso)
                        if prod:
                            prod.stock_actual += cantidad_val
                            productos_a_actualizar.add(prod)

                # =========================================================
                # 3. GUARDADO EN MASA DE TODO (Ingresos y Modelos)
                # =========================================================
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
    # Preparamos el archivo para descargar
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Plantilla_Ingresos_Percheron.csv"'
    
    # Esto asegura que Excel lea las tildes y la letra "N°" correctamente
    response.write('\ufeff'.encode('utf8'))
    
    # EL TRUCO PARA EXCEL EN ESPAÑOL: Usar punto y coma (;) como separador
    writer = csv.writer(response, delimiter=';')
    
    # Escribimos las cabeceras
    writer.writerow([
        'SKU', 
        'MODELO', 
        'TÍTULO', 
        'FECHA INGRESO', 
        'CÓDIGO EAN', 
        'SERIE / N°', 
        'COSTO UNT.', 
        'ING. x 1 und', 
        'PROVEEDOR / MOTIVO', 
        'BY:'
    ])
    
    return response


@login_required
def exportar_modelos_excel(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="Directorio_Modelos.csv"'
    response.write('\ufeff'.encode('utf8'))
    
    writer = csv.writer(response, delimiter=';')
    # NUEVO ORDEN DE COLUMNAS EXACTO
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
            p.stock_actual, # Bloqueado, solo lectura
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
                    
                    # Buscamos si el modelo ya existe. Si no existe, lo crea.
                    # Le asignamos un SKU temporal autogenerado si es nuevo.
                    obj, created = Producto.objects.get_or_create(
                        modelo=modelo_val, 
                        defaults={
                            'sku': f'SKU-{uuid.uuid4().hex[:8].upper()}', 
                            'titulo': item.get('TÍTULO', '')
                        }
                    )
                    
                    # Actualizamos todos sus datos con lo que viene de la tabla/Excel
                    obj.marca = item.get('MARCA', '')
                    obj.categoria = item.get('CATEGORÍA', '')
                    obj.titulo = item.get('TÍTULO', '')
                    
                    # Actualizamos los checks de disponibilidad (True o False)
                    obj.activo_intercorp = True if item.get('INVENTARIADO POR LOS PERCHERONES') == 'TRUE' else False
                    obj.activo_ml = True if item.get('MERCADO LIBRE') == 'TRUE' else False
                    obj.activo_falabella = True if item.get('FALABELLA') == 'TRUE' else False
                    obj.activo_creditienda = True if item.get('CREDITIENDA') == 'TRUE' else False
                    obj.activo_web = True if item.get('PÁGINA WEB') == 'TRUE' else False
                    
                    obj.save()
                    
            return JsonResponse({'status': 'ok', 'message': '¡Directorio de Modelos actualizado correctamente!'})
            
        except Exception as e:
            import traceback
            print(traceback.format_exc()) # Esto imprimirá el error en la consola negra si algo más falla
            return JsonResponse({'status': 'error', 'message': f'Error en el servidor: {str(e)}'})
            
    return JsonResponse({'status': 'error', 'message': 'Método no permitido'})
        
@login_required
@csrf_exempt
def borrar_todos_los_ingresos(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Borramos el historial de ingresos
                IngresoPercheron.objects.all().delete()
                
                # 2. Reseteamos el stock actual de TODOS los modelos a cero
                Producto.objects.all().update(stock_actual=0)
            
            return JsonResponse({'status': 'ok', 'message': '¡Base de datos de ingresos limpiada y stocks reseteados a 0!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})


@login_required
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
        
    # === CAMBIO CLAVE: Eliminamos el Paginator para enviar la lista completa de corrido ===
    page_obj = SalidaMercadoLibre.objects.all().order_by('-id')

    return render(request, 'inventario/percheron_mercadolibre.html', {
        'canal': canal,
        'skus_json': json.dumps(dict_skus),
        'page_obj': page_obj 
    })




@login_required
@csrf_exempt
def sincronizar_stock_modelos(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Resetear todo a 0
                Producto.objects.all().update(stock_actual=0)
                
                # 2. Crear un mapa de stock basado en el modelo limpio
                conteo_stock = {}
                todos_ingresos = IngresoPercheron.objects.all()
                
                for ing in todos_ingresos:
                    # Usamos el modelo tal cual viene en la base de datos de ingresos
                    modelo_key = str(ing.modelo).strip().upper()
                    if modelo_key:
                        conteo_stock[modelo_key] = conteo_stock.get(modelo_key, 0) + (ing.cantidad or 0)

                # 3. Comparar con el Directorio de Modelos
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
                # Borra absolutamente todos los registros de la tabla Producto (Directorio de Modelos)
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
        eliminadas = data.get('eliminadas', []) # Recibimos los IDs a borrar

        # VALIDACIÓN INTELIGENTE: Falla solo si NO hay salidas nuevas Y TAMPOCO hay eliminaciones
        if not salidas and not eliminadas:
            return JsonResponse({'status': 'error', 'message': 'No hay nuevas salidas ni registros eliminados para procesar.'})

        with transaction.atomic():
            conteo_descuentos = {}
            conteo_restauraciones = {}

            # ==========================================================
            # 1. PROCESAR ELIMINACIONES (Recuperar stock y borrar bd)
            # ==========================================================
            if eliminadas:
                registros_viejos = SalidaMercadoLibre.objects.filter(id__in=eliminadas)
                for registro in registros_viejos:
                    if registro.modelo:
                        # Limpiamos el modelo igual que en la creación para asegurar que coincida
                        key = str(registro.modelo).upper().replace(" ", "").replace("-", "")
                        conteo_restauraciones[key] = conteo_restauraciones.get(key, 0) + registro.descuento
                    
                    # Destruimos el registro de la base de datos
                    registro.delete()

            # ==========================================================
            # 2. PROCESAR NUEVAS SALIDAS (Guardar historial y acumular descuentos)
            # ==========================================================
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

            # ==========================================================
            # 3. ACTUALIZAR STOCK DE PRODUCTOS (Sumas y Restas en un solo paso)
            # ==========================================================
            modelos_afectados = 0
            modelos_restaurados = 0
            
            if conteo_descuentos or conteo_restauraciones:
                for prod in Producto.objects.all():
                    if prod.modelo:
                        key = prod.modelo.upper().replace(" ", "").replace("-", "")
                        cambio = False
                        
                        # A. Devolvemos el stock de las filas eliminadas
                        if key in conteo_restauraciones:
                            prod.stock_actual += conteo_restauraciones[key]
                            modelos_restaurados += 1
                            cambio = True
                            
                        # B. Restamos el stock de las filas nuevas
                        if key in conteo_descuentos:
                            prod.stock_actual = max(prod.stock_actual - conteo_descuentos[key], 0)
                            modelos_afectados += 1
                            cambio = True
                            
                        # C. Si el producto sufrió algún cambio, lo guardamos
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
                # Reemplaza 'ReporteMercadoLibre' por el nombre exacto de tu modelo si es diferente
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
                # ¡AHORA SÍ USA EL NOMBRE CORRECTO DEL MODELO!
                SimulacionMercadoLibre.objects.all().delete()
            
            return JsonResponse({'status': 'ok', 'message': '¡Datos del simulador limpiados con éxito!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})
    return JsonResponse({'status': 'error', 'message': 'Solo permitido POST'})