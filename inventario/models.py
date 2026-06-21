from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# =========================================================
# 1. MODELOS DE PRODUCTOS (Tus modelos originales)
# =========================================================
class Categoria(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre

class Electrodomestico(models.Model):
    nombre = models.CharField(max_length=200)
    marca = models.CharField(max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField()
    descripcion = models.TextField(blank=True)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} - {self.marca}"

# =========================================================
# 2. SISTEMA DE USUARIOS Y PLATAFORMAS
# =========================================================
class Plataforma(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    plataformas = models.ManyToManyField(Plataforma, blank=True)

    def __str__(self):
        return f"{self.usuario.username} ({self.plataformas.count()} plataformas)"

# SEÑALES PARA CREAR EL PERFIL AUTOMÁTICAMENTE
@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        Perfil.objects.create(usuario=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    instance.perfil.save()

# =========================================================
# 3. MAESTRO DE PRODUCTOS (El Catálogo Único de Percherón)
# =========================================================
class Producto(models.Model):
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    categoria = models.CharField(max_length=150, blank=True, null=True, verbose_name="Categoría")
    titulo = models.CharField(max_length=255, verbose_name="Título / Descripción")
    codigo_ean = models.CharField(max_length=100, blank=True, null=True, verbose_name="Código EAN")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación Base")
    
    # Costos para tu módulo "Costos General"
    costo_dolares = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Unit. ($)")
    costo_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Cero (S/.)")
    
    # NUEVO: ¡La columna física real para el Stock!
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual")
    
    # Casillas (Checkboxes) para tu pantalla "Consulta Rápida"
    activo_ml = models.BooleanField(default=False, verbose_name="Mercado Libre")
    activo_ml_jr = models.BooleanField(default=False, verbose_name="Mercado Libre Junior")
    activo_falabella = models.BooleanField(default=False, verbose_name="Falabella")
    activo_web = models.BooleanField(default=False, verbose_name="Página Web")
    activo_creditienda = models.BooleanField(default=False, verbose_name="Creditienda")
    activo_intercorp = models.BooleanField(default=False, verbose_name="Intercorp")

    def __str__(self):
        return f"{self.sku} - {self.titulo}"

# =========================================================
# 4. KARDEX PERCHERÓN (El Historial de Movimientos)
# =========================================================
class MovimientoPercheron(models.Model):
    TIPO_MOVIMIENTO = [
        ('IN', 'Ingreso (+)'),
        ('OUT', 'Salida (-)')
    ]
    
    # Enlace directo al Producto
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='movimientos_percheron')
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad")
    fecha = models.DateField(verbose_name="Fecha de Operación")
    serie = models.CharField(max_length=150, blank=True, null=True, verbose_name="Nro. Serie")
    costo_transaccion = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Unit. (S/.) en este mov.")
    
    # Campos específicos para Ingresos (IN)
    proveedor_motivo = models.CharField(max_length=200, blank=True, null=True, verbose_name="Proveedor / Motivo (Ingreso)")
    
    # Campos específicos para Salidas (OUT)
    documento_salida = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. Orden / Boleta (Salida)")
    canal_venta = models.CharField(max_length=100, blank=True, null=True, verbose_name="Canal de Venta (Salida)")
    
    # Auditoría automática
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Registrado por")
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.tipo}] {self.cantidad} und - {self.producto.sku} - {self.fecha}"

    class Meta:
        ordering = ['-fecha', '-creado_en'] # Ordena del más reciente al más antiguo

class SimulacionMercadoLibre(models.Model):
    # Relación para saber quién hizo la simulación y cuándo
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='simulaciones_mercadolibre')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # Identificadores y clasificación de la publicación
    item_type = models.CharField(max_length=20, blank=True, null=True)  # KILLER, NORMAL, SLOW, NUEVO
    link = models.URLField(max_length=500, blank=True, null=True)
    estado_publicacion = models.CharField(max_length=20, blank=True, null=True)  # ACTIVO, PAUSADO
    cod_publicacion = models.CharField(max_length=50, blank=True, null=True)
    tipo_publicacion = models.CharField(max_length=30, blank=True, null=True)  # CATALOGO, TRADICIONAL
    
    # Datos del producto
    cod_producto = models.CharField(max_length=50, blank=True, null=True)
    categoria = models.CharField(max_length=150, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    producto = models.CharField(max_length=255, blank=True, null=True)
    
    # Valores comerciales y descuentos
    precio_tachado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # AMPLIADO: max_digits=10
    porc_descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Costos operativos e impuestos de plataforma
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # AMPLIADO: max_digits=10
    porc_comision = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    comision_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Resultados financieros de la plataforma y costos propios
    pago_neto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_producto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Indicadores finales de éxito
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # AMPLIADO: max_digits=10 
    rentabilidad_porc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    mpe = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Simulación Mercado Libre"
        verbose_name_plural = "Simulaciones Mercado Libre"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.producto if self.producto else 'Sin nombre'} - S/ {self.precio_venta} ({self.usuario.username})"

# =========================================================
# MODELO CLONADO: SIMULADOR MERCADO LIBRE JUNIOR
# =========================================================
class SimulacionMercadoLibreJunior(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='simulaciones_mercadolibre_junior')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    item_type = models.CharField(max_length=20, blank=True, null=True) 
    link = models.URLField(max_length=500, blank=True, null=True)
    estado_publicacion = models.CharField(max_length=20, blank=True, null=True)
    cod_publicacion = models.CharField(max_length=50, blank=True, null=True)
    tipo_publicacion = models.CharField(max_length=30, blank=True, null=True) 
    cod_producto = models.CharField(max_length=50, blank=True, null=True)
    categoria = models.CharField(max_length=150, blank=True, null=True)
    marca = models.CharField(max_length=100, blank=True, null=True)
    producto = models.CharField(max_length=255, blank=True, null=True)
    precio_tachado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    porc_descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    porc_comision = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    comision_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pago_neto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_producto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rentabilidad_porc = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    mpe = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = "Simulación Mercado Libre Junior"
        verbose_name_plural = "Simulaciones Mercado Libre Junior"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"Junior: {self.producto if self.producto else 'Sin nombre'} - S/ {self.precio_venta} ({self.usuario.username})"
    
class Comision(models.Model):
    sub_categoria = models.CharField(max_length=100)
    categoria = models.CharField(max_length=100)
    
    # AMPLIADO: max_digits=10
    porcentaje = models.DecimalField(max_digits=10, decimal_places=2)

class ReferenciaComision(models.Model):
    sub_categoria = models.CharField(max_length=200, unique=True) 
    categoria = models.CharField(max_length=200, blank=True, null=True) 
    
    # AMPLIADO: max_digits=10
    comision = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.sub_categoria} - {self.comision}%"
    
class ReferenciaCosto(models.Model):
    codigo = models.CharField(max_length=100, unique=True)
    producto = models.CharField(max_length=255, blank=True, null=True)
    costo_cero = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_u_dolares = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_u_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.codigo} - {self.producto}"
    
class ReporteMercadoLibre(models.Model):
    fecha = models.DateField()
    mes_anio = models.CharField(max_length=100)
    nro_orden = models.CharField(max_length=255, unique=True)
    
    # Restauradas las columnas nuevas que faltaban en tu archivo
    nro_operacion = models.CharField(max_length=255, blank=True, null=True)
    estado_pago = models.CharField(max_length=100, blank=True, null=True)
    
    comprobante = models.CharField(max_length=255)
    tipo_venta = models.CharField(max_length=255)
    marca = models.CharField(max_length=255)
    categoria = models.CharField(max_length=255)
    sku_almacen = models.CharField(max_length=255)
    modelo = models.CharField(max_length=255)
    producto = models.CharField(max_length=500)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cargo_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    urbano = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    flex = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_producto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    und = models.IntegerField(default=0)
    costo_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_entrega_flex = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rentabilidad = models.CharField(max_length=50)
    distrito = models.CharField(max_length=255)
    direccion = models.CharField(max_length=500)
    repartidor = models.CharField(max_length=255)
    celular = models.CharField(max_length=50)
    mensaje = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.nro_orden

# =========================================================
# 5. REGISTRO DE INGRESOS - PERCHERON
# =========================================================
class IngresoPercheron(models.Model):
    sku = models.CharField(max_length=150, blank=True, null=True, verbose_name="SKU Autogenerado")
    modelo = models.CharField(max_length=200, blank=True, null=True, verbose_name="Modelo")
    titulo = models.CharField(max_length=500, blank=True, null=True, verbose_name="Título")
    fecha_ingreso = models.DateField(blank=True, null=True, verbose_name="Fecha de Ingreso")
    codigo_ean = models.CharField(max_length=150, blank=True, null=True, verbose_name="Código EAN")
    serie_nro = models.CharField(max_length=200, blank=True, null=True, verbose_name="Serie / N°")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Unt.")
    cantidad = models.IntegerField(default=1, verbose_name="Ing. x 1 und")
    proveedor_motivo = models.CharField(max_length=300, blank=True, null=True, verbose_name="Proveedor / Motivo")
    creado_por = models.CharField(max_length=150, blank=True, null=True, verbose_name="By:")

    def __str__(self):
        return f"{self.sku if self.sku else 'Sin SKU'} - {self.modelo} (Serie: {self.serie_nro if self.serie_nro else 'Sin Serie'})"
    

class SalidaMercadoLibre(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return str(self.sku)
    
class ReporteMercadoLibreJunior(models.Model):
    nro_orden = models.CharField(max_length=255, unique=True)
    fecha = models.DateField()
    mes_anio = models.CharField(max_length=100, blank=True, null=True)
    nro_operacion = models.CharField(max_length=255, blank=True, null=True)
    estado_pago = models.CharField(max_length=100, blank=True, null=True)
    comprobante = models.CharField(max_length=255, blank=True, null=True)
    tipo_venta = models.CharField(max_length=255, blank=True, null=True)
    marca = models.CharField(max_length=255, blank=True, null=True)
    categoria = models.CharField(max_length=255, blank=True, null=True)
    sku_almacen = models.CharField(max_length=255, blank=True, null=True)
    modelo = models.CharField(max_length=255, blank=True, null=True)
    producto = models.CharField(max_length=255, blank=True, null=True)
    cantidad = models.FloatField(default=0)
    precio = models.FloatField(default=0)
    total_venta = models.FloatField(default=0)
    cargo_venta = models.FloatField(default=0)
    urbano = models.FloatField(default=0)
    flex = models.FloatField(default=0)
    total_pagado = models.FloatField(default=0)
    costo_producto = models.FloatField(default=0)
    und = models.IntegerField(default=0)
    costo_total = models.FloatField(default=0)
    costo_entrega_flex = models.FloatField(default=0)
    ganancia = models.FloatField(default=0)
    rentabilidad = models.CharField(max_length=100, blank=True, null=True)
    distrito = models.CharField(max_length=255, blank=True, null=True)
    direccion = models.CharField(max_length=255, blank=True, null=True)
    repartidor = models.CharField(max_length=255, blank=True, null=True)
    celular = models.CharField(max_length=255, blank=True, null=True)
    mensaje = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Junior: {self.nro_orden} - {self.fecha}"
    

class SalidaMercadoLibreJunior(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self):
        return str(self.sku)
    

class SalidaFalabella(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self): return str(self.sku)

class SalidaCreditienda(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self): return str(self.sku)

class SalidaIntercorp(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self): return str(self.sku)

class SalidaTiktok(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self): return str(self.sku)

class SalidaVentaLibre(models.Model):
    sku = models.CharField(max_length=100, null=True, blank=True)
    modelo = models.CharField(max_length=100, null=True, blank=True)
    titulo = models.CharField(max_length=255, null=True, blank=True)
    fecha_salida = models.DateField(null=True, blank=True)
    serie = models.CharField(max_length=100, null=True, blank=True)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    descuento = models.IntegerField(default=1)
    nro_venta = models.CharField(max_length=100, null=True, blank=True)
    tipo_venta = models.CharField(max_length=50, null=True, blank=True)
    creado_por = models.CharField(max_length=50, null=True, blank=True)

    def __str__(self): return str(self.sku)


class ReporteCreditienda(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reportes_creditienda')
    fecha_registro = models.DateTimeField(auto_now_add=True)

    # Datos Generales
    fecha_venta = models.DateField(null=True, blank=True)
    fecha_despacho = models.DateField(null=True, blank=True)
    mes_ano = models.CharField(max_length=50, null=True, blank=True)
    estado_pedido = models.CharField(max_length=100, null=True, blank=True)
    nro_orden = models.CharField(max_length=100, null=True, blank=True)
    cliente = models.CharField(max_length=255, null=True, blank=True)
    boleta = models.CharField(max_length=100, null=True, blank=True)
    marca = models.CharField(max_length=100, null=True, blank=True)
    categoria = models.CharField(max_length=150, null=True, blank=True)
    
    # Datos del Producto
    sku_almacen = models.CharField(max_length=100, null=True, blank=True)
    codigo = models.CharField(max_length=100, null=True, blank=True)
    producto = models.CharField(max_length=255, null=True, blank=True)
    cantidad = models.IntegerField(default=1)
    
    # Finanzas
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    porc_comision = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    comision_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pago_plataforma = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rentabilidad = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Control de Pagos y Validación
    check_pago = models.BooleanField(default=False) # Para la columna con el ícono de check
    venta_pagada = models.CharField(max_length=50, null=True, blank=True)
    se_adjunto = models.CharField(max_length=50, null=True, blank=True)
    fecha_validacion = models.DateField(null=True, blank=True)
    nro_operacion = models.CharField(max_length=100, null=True, blank=True)
    nro_telefono = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Reporte Creditienda'
        verbose_name_plural = 'Reportes Creditienda'
        ordering = ['-fecha_venta']

    def __str__(self):
        return f"{self.nro_orden} - {self.sku_almacen}"