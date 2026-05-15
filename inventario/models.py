from django.db import models
from django.contrib.auth.models import User

# 1. Modelos de productos (Tus modelos originales)
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

# 2. NUEVA TABLA: Para registrar las plataformas disponibles
class Plataforma(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nombre

# 3. PERFIL ACTUALIZADO: Ahora permite múltiples plataformas
class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Cambiamos CharField por ManyToManyField para permitir varias selecciones
    plataformas = models.ManyToManyField(Plataforma, blank=True)

    def __str__(self):
        # Mostramos el nombre y cuántas plataformas tiene asignadas
        return f"{self.usuario.username} ({self.plataformas.count()} plataformas)"