import os, traceback
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.test import Client
from django.urls import get_resolver, URLPattern, URLResolver
from django.contrib.auth import get_user_model

SALTAR = ("logout", "delete", "eliminar", "stream", "feed", "video", "live")

def recorrer(patterns, prefijo="", ns=""):
    for p in patterns:
        ruta = str(p.pattern)
        if isinstance(p, URLResolver):
            nuevo_ns = f"{ns}{p.namespace}:" if p.namespace else ns
            yield from recorrer(p.url_patterns, prefijo + ruta, nuevo_ns)
        elif isinstance(p, URLPattern):
            yield prefijo + ruta, f"{ns}{p.name or '-'}"

user = get_user_model().objects.filter(is_superuser=True).first()
if not user:
    print("ERROR: no hay superusuario"); raise SystemExit
c = Client(HTTP_HOST="127.0.0.1")
c.force_login(user)

ok, redir, errores, omitidas = [], [], [], []
vistas = set()
for ruta, nombre in recorrer(get_resolver().url_patterns):
    if ruta.startswith("admin/") and ruta != "admin/":
        continue
    if any(ch in ruta for ch in "<^$(?"):
        omitidas.append(f"/{ruta}  [{nombre}] (requiere parametro)"); continue
    if any(s in ruta.lower() or s in nombre.lower() for s in SALTAR):
        omitidas.append(f"/{ruta}  [{nombre}] (omitida por seguridad)"); continue
    url = "/" + ruta
    if url in vistas: continue
    vistas.add(url)
    try:
        r = c.get(url)
        linea = f"{r.status_code}  {url}  [{nombre}]"
        if r.status_code < 300: ok.append(linea)
        elif r.status_code < 400: redir.append(linea + f" -> {r.get('Location')}")
        else: errores.append(linea)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        propio = [f for f in tb if "site-packages" not in f.filename]
        donde = f"{propio[-1].filename}:{propio[-1].lineno}" if propio else ""
        errores.append(f"EXC  {url}  [{nombre}]\n      {type(e).__name__}: {e}\n      en {donde}")

print(f"=== OK ({len(ok)}) ==="); print("\n".join(ok))
print(f"\n=== REDIRECCIONES ({len(redir)}) ==="); print("\n".join(redir))
print(f"\n=== ERRORES ({len(errores)}) ==="); print("\n".join(errores))
print(f"\n=== OMITIDAS ({len(omitidas)}) ==="); print("\n".join(omitidas))
