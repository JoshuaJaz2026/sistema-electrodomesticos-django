from django.db import models
from django.contrib.auth.models import User

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

# =========================================================
# 3. MAESTRO DE PRODUCTOS (El Catálogo Único de Percherón)
# =========================================================
class Producto(models.Model):
    sku = models.CharField(max_length=50, unique=True, verbose_name="SKU")
    modelo = models.CharField(max_length=100, verbose_name="Modelo")
    marca = models.CharField(max_length=100, blank=True, null=True, verbose_name="Marca")
    titulo = models.CharField(max_length=255, verbose_name="Título / Descripción")
    codigo_ean = models.CharField(max_length=100, blank=True, null=True, verbose_name="Código EAN")
    ubicacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Ubicación Base")
    
    # Costos para tu módulo "Costos General"
    costo_dolares = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Unit. ($)")
    costo_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Cero (S/.)")
    
    # NUEVO: Casillas (Checkboxes) para tu pantalla "Consulta Rápida"
    activo_ml = models.BooleanField(default=False, verbose_name="Mercado Libre")
    activo_ml_jr = models.BooleanField(default=False, verbose_name="Mercado Libre Junior")
    activo_falabella = models.BooleanField(default=False, verbose_name="Falabella")
    activo_web = models.BooleanField(default=False, verbose_name="Página Web")
    activo_creditienda = models.BooleanField(default=False, verbose_name="Creditienda")
    activo_intercorp = models.BooleanField(default=False, verbose_name="Intercorp")

    def __str__(self):
        return f"{self.sku} - {self.titulo}"

    # Función mágica para calcular el stock en tiempo real
    @property
    def stock_actual(self):
        ingresos = sum(mov.cantidad for mov in self.movimientos_percheron.filter(tipo='IN'))
        salidas = sum(mov.cantidad for mov in self.movimientos_percheron.filter(tipo='OUT'))
        return ingresos - salidas

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
    porc_descuento = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Costos operativos e impuestos de plataforma
    costo_envio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    porc_comision = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    comision_soles = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Resultados financieros de la plataforma y costos propios
    pago_neto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    costo_producto = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Indicadores finales de éxito
    ganancia = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    rentabilidad_porc = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    mpe = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Simulación Mercado Libre"
        verbose_name_plural = "Simulaciones Mercado Libre"
        ordering = ['-fecha_registro']

    def __str__(self):
        return f"{self.producto if self.producto else 'Sin nombre'} - S/ {self.precio_venta} ({self.usuario.username})"
    
class Comision(models.Model):
    sub_categoria = models.CharField(max_length=100)
    categoria = models.CharField(max_length=100)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2)