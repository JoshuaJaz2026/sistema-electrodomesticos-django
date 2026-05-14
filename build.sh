set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Crear superusuario automáticamente si no existe
# El "|| true" al final es un truco para que no dé error si el usuario ya fue creado en el futuro
python manage.py createsuperuser --noinput --username admin_jared --email jabarcap.2004@gmail.com || true