from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from inventario import views as inventario_views # Traemos las vistas de tu inventario

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Aquí conectamos tu Login Camaleónico
    path('login/', inventario_views.LoginCamaleonicoView.as_view(), name='login'),
    
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    # Tu portal de plataformas
    path('', include('inventario.urls')), 
]