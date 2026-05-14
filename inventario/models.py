from django.db import models
from django.contrib.auth.models import User

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
    
    # Creamos un perfil anexo al usuario de Django
class Perfil(models.Model):
    # Lista de opciones exactas de tus plataformas
    PLATAFORMAS_CHOICES = [
        ("Mercado Libre", "Mercado Libre"),
        ("Mercado Libre - Junior", "Mercado Libre - Junior"),
        ("Creditienda", "Creditienda"),
        ("Falabella", "Falabella"),
        ("Intercorp", "Intercorp"),
        ("Venta Libre", "Venta Libre"),
        ("Tik tok", "Tik tok"),
        ("Web", "Web"),
    ]
    
    # Conectamos este perfil con un usuario (Si se borra el usuario, se borra el perfil)
    usuario = models.OneToOneField(User, on_delete=models.CASCADE)
    plataforma = models.CharField(max_length=50, choices=PLATAFORMAS_CHOICES, default="Web")

    def __str__(self):
        return f"{self.usuario.username} - {self.plataforma}"