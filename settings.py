import os
import dj_database_url

# ... (Configuraciones de siempre)

DEBUG = 'RENDER' not in os.environ

ALLOWED_HOSTS = []
render_external_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname:
    ALLOWED_HOSTS.append(render_external_hostname)

# Configuración de Base de Datos para Render
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///db.sqlite3',
        conn_max_age=600
    )
}