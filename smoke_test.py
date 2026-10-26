import os, re, sys, traceback, logging
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.test import Client
from django.urls import get_resolver, URLPattern, URLResolver, reverse
from django.contrib.auth import get_user_model
logging.disable(logging.WARNING)

ACCIONES = ("logout", "delete", "eliminar", "stream", "feed", "video", "live",
            "start", "stop", "preview", "pay", "confirm", "cancel", "close",
            "resolve", "review", "continue", "message", "add", "discount")

def recorrer(patterns, prefijo="", ns=""):
    for p in patterns:
        ruta = str(p.pattern)
        if isinstance(p, URLResolver):
            nuevo_ns = f"{ns}{p.namespace}:" if p.namespace else ns
            yield from recorrer(p.url_patterns, prefijo + ruta, nuevo_ns)
        elif isinstance(p, URLPattern):
            yield prefijo + ruta, f"{ns}{p.name or '-'}"

def construir(ruta, nombre):
    if "format" in ruta:
        return None, "formato"
    if "^" in ruta:
        corto = nombre.split(":")[-1]
        try:
            if corto.endswith("-list"):
                return reverse(nombre), None
            if corto.endswith("-detail"):
                return reverse(nombre, kwargs={"pk": 1}), None
        except Exception as e:
            return None, f"reverse fallo: {e}"
        return None, "regex"
    ruta2 = re.sub(r"<int:\w+>", "1", ruta)
    if "<" in ruta2:
        return None, "parametro de texto"
    return "/" + ruta2, None

User = get_user_model()
if len(sys.argv) > 1:
    user = User.objects.filter(username=sys.argv[1]).first()
else:
    user = User.objects.filter(is_superuser=True).first()
if not user:
    print("ERROR: usuario no encontrado"); raise SystemExit
print(f"##### USUARIO: {user.username} (superuser={user.is_superuser}) #####\n")

c = Client(HTTP_HOST="127.0.0.1")
c.force_login(user)

ok, redir, prohib, no_existe, errores, omitidas = [], [], [], [], [], []
n_formato = 0
vistas = set()

for ruta, nombre in recorrer(get_resolver().url_patterns):
    if ruta.startswith("admin/") and ruta != "admin/":
        continue
    corto = nombre.split(":")[-1].lower()
    if any(a in corto or a in ruta.lower() for a in ACCIONES):
        omitidas.append(f"/{ruta}  [{nombre}] (accion: se prueba a mano)")
        continue
    url, motivo = construir(ruta, nombre)
    if not url:
        if motivo == "formato":
            n_formato += 1
        else:
            omitidas.append(f"/{ruta}  [{nombre}] ({motivo})")
        continue
    if url in vistas:
        continue
    vistas.add(url)
    try:
        r = c.get(url)
        tipo = r.get("Content-Type", "").split(";")[0]
        linea = f"{r.status_code}  {url}  [{nombre}]  {tipo}"
        s = r.status_code
        if s < 300: ok.append(linea)
        elif s < 400: redir.append(f"{linea} -> {r.get('Location')}")
        elif s in (401, 403): prohib.append(linea)
        elif s == 404: no_existe.append(linea)
        else: errores.append(linea)
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        propio = [f for f in tb if "site-packages" not in f.filename]
        donde = f"{propio[-1].filename}:{propio[-1].lineno}" if propio else ""
        errores.append(f"EXC  {url}  [{nombre}]\n      {type(e).__name__}: {e}\n      en {donde}")

for titulo, lista in [("OK", ok), ("REDIRECCIONES", redir), ("SIN PERMISO 401/403", prohib),
                      ("NO EXISTE 404 (puede faltar el id 1)", no_existe),
                      ("ERRORES", errores), ("OMITIDAS", omitidas)]:
    print(f"=== {titulo} ({len(lista)}) ===")
    print("\n".join(lista))
    print()
print(f"(Variantes de formato de la API omitidas: {n_formato})\n")
