from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

def render_to_pdf(template_src, context_dict={}):
    """
    Función que toma una ruta de plantilla HTML y un diccionario de datos,
    y devuelve un archivo PDF listo para descargar.
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
    # Generamos el PDF (usamos utf-8 para tildes y eñes)
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), result, encoding='utf-8')
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None