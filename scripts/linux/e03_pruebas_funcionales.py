"""
E03: pruebas funcionales que el informe registra como manuales.

Ejecuta seis pruebas sobre la plataforma con el cliente de pruebas de Django, dentro de una
transacción que se deshace al terminar (como auditar_roles): no deja usuarios, locales ni datos.

  PR-SEG-02  Aislamiento entre locales y usuarios
  PR-FUN-03  Gestión de mesas (alta, edición, desactivación y código repetido)
  PR-DAT-01  Marcas temporales en la exportación CSV con sesiones conocidas
  PR-FUN-10  Reportes diario y por período en CSV y PDF
  PR-FUN-13  Reporte y exportación frente a un conjunto de datos conocido (KPI-08)
  PR-RES-02 / PR-FUN-11  Cámara con dirección inválida: la plataforma no cae; ¿se registra incidencia?

Uso (desde la carpeta del proyecto, con la plataforma detenida o corriendo, da igual):
  venv/bin/python scripts/linux/e03_pruebas_funcionales.py
"""
import csv
import io
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta
from datetime import timezone as dt_tz
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.core.management.base import CommandError  # noqa: E402
from django.db import transaction  # noqa: E402
from django.test import Client  # noqa: E402
from django.test.utils import override_settings  # noqa: E402
from django.utils import timezone  # noqa: E402

SALIDA = RAIZ / "evidencias" / "E03"
RES = []


def registrar(codigo, nombre, aprobada, detalle, texto):
    RES.append({"codigo": codigo, "prueba": nombre, "resultado": aprobada, "detalle": detalle, "texto_ficha": texto})
    marca = {True: "APROBADA", False: "NO APROBADA", None: "NO EJECUTADA"}[aprobada]
    print(f"\n[{codigo}] {nombre}: {marca}\n   {detalle}")


def prueba(codigo, nombre):
    def deco(fn):
        def run(*a):
            try:
                fn(*a)
            except Exception as e:  # noqa: BLE001
                registrar(codigo, nombre, None, f"El script no pudo ejecutar la prueba: {type(e).__name__}: {e}",
                          "")
                traceback.print_exc()
        return run
    return deco


def usuario(nombre, rol, locales):
    from authentication.models import Profile
    u = User.objects.create_user(nombre, password=None)
    p, _ = Profile.objects.get_or_create(user=u)
    p.role = rol
    p.save()
    p.venues.set(locales)
    c = Client()
    c.force_login(u)
    return u, c


def leer_csv(resp):
    texto = resp.content.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


@prueba("PR-SEG-02", "Aislamiento entre locales y usuarios")
def seg02(ctx):
    a, b, ca, cb = ctx["A"], ctx["B"], ctx["cliA"], ctx["cliB"]
    rutas = ["/reports/daily/{}/", "/reports/daily/{}/csv/", "/reports/daily/{}/pdf/"]
    propio = [ca.get(r.format(a.id)).status_code for r in rutas]
    ajeno = [ca.get(r.format(b.id)).status_code for r in rutas]
    ajeno_b = [cb.get(r.format(a.id)).status_code for r in rutas]
    ok = all(s == 200 for s in propio) and all(s in (403, 404) for s in ajeno + ajeno_b)
    det = f"Usuario del local A a su local: {propio}; al local B: {ajeno}; usuario de B al local A: {ajeno_b}"
    registrar("PR-SEG-02", "Aislamiento entre locales y usuarios", ok, det,
              (f"{'Aprobada' if ok else 'No aprobada'}: con dos locales y un administrador por local, cada usuario "
               f"accede al reporte diario de su local en HTML, CSV y PDF (respuesta 200) y recibe "
               f"{sorted(set(ajeno + ajeno_b))} al pedir el del otro local. Evidencia en evidencias/E03."))


@prueba("PR-FUN-03", "Gestión de mesas")
def fun03(ctx):
    from operations.forms import RestaurantTableForm
    from operations.models import RestaurantTable
    a, ca = ctx["A"], ctx["cliA"]
    r = ca.post(f"/operations/tables/create/{a.id}/",
                {"code": "PRUEBA-01", "capacity": 4, "zone_name": "Terraza", "is_active": "on", "notes": ""})
    mesa = RestaurantTable.objects.filter(venue=a, code="PRUEBA-01").first()
    alta = r.status_code in (200, 302) and mesa is not None
    f = RestaurantTableForm({"code": "PRUEBA-01", "capacity": 6, "zone_name": "Salón", "is_active": "on", "notes": "editada"},
                            instance=mesa, venue=a)
    edit = f.is_valid() and f.save().capacity == 6
    f2 = RestaurantTableForm({"code": "PRUEBA-01", "capacity": 6, "zone_name": "Salón", "notes": ""},
                             instance=mesa, venue=a)
    desact = f2.is_valid() and not f2.save().is_active
    r2 = ca.post(f"/operations/tables/create/{a.id}/",
                 {"code": "PRUEBA-01", "capacity": 2, "zone_name": "Terraza", "is_active": "on", "notes": ""})
    duplicada = RestaurantTable.objects.filter(venue=a, code="PRUEBA-01").count() == 1
    ok = alta and edit and desact and duplicada
    det = f"alta={alta} (HTTP {r.status_code}), edición={edit}, desactivación={desact}, código repetido rechazado={duplicada}"
    registrar("PR-FUN-03", "Gestión de mesas", ok, det,
              (f"{'Aprobada' if ok else 'No aprobada'}: alta de una mesa desde la pantalla de creación, edición de su "
               f"capacidad y zona y desactivación con el formulario de la plataforma"
               f"{'; un segundo alta con el mismo código se rechaza' if duplicada else '; el código repetido NO se rechazó'}."
               " Evidencia en evidencias/E03."))


@prueba("PR-DAT-01", "Marcas temporales en la exportación CSV")
def dat01(ctx):
    a, ca, dia, esperadas = ctx["A"], ctx["cliA"], ctx["dia"], ctx["sesiones"]
    filas = leer_csv(ca.get(f"/reports/daily/{a.id}/csv/?date={dia.isoformat()}"))
    i = next(k for k, f in enumerate(filas) if f[:1] == ["Sesión de atención"])
    datos = {}
    for f in filas[i + 1:]:
        if not f or not f[0].strip():
            break
        datos[int(f[0])] = (f[4], f[5])
    ok_local, ok_utc, detalle = 0, 0, []
    for s, ini, fin in esperadas:
        got = datos.get(s.id)
        loc = (ini.strftime("%d-%m-%Y %H:%M"), fin.strftime("%d-%m-%Y %H:%M"))
        utc = tuple(x.astimezone(dt_tz.utc).strftime("%d-%m-%Y %H:%M") for x in (ini, fin))
        ok_local += got == loc
        ok_utc += got == utc and got != loc
        detalle.append(f"sesión {s.id}: esperado {loc[0]}–{loc[1]} (hora de Chile), CSV {got}")
    ok = ok_local == len(esperadas)
    hallazgo = (" HALLAZGO: el CSV escribe las horas en UTC y no en la hora de Chile." if ok_utc == len(esperadas) else "")
    registrar("PR-DAT-01", "Marcas temporales en la exportación CSV", ok, "; ".join(detalle) + hallazgo,
              (f"{'Aprobada' if ok else 'No aprobada'}: tres atenciones con horas conocidas se exportaron en el CSV del "
               f"reporte diario y {ok_local} de {len(esperadas)} coinciden en inicio y término con la hora local."
               + (" El CSV registra las horas en UTC (3 horas de diferencia con la hora de Chile); se registra como "
                  "defecto y cambio recomendado." if hallazgo else "") + " Evidencia en evidencias/E03."))


@prueba("PR-FUN-10", "Reportes CSV y PDF")
def fun10(ctx):
    a, ca, dia = ctx["A"], ctx["cliA"], ctx["dia"]
    res = {}
    for nombre, ruta in [("diario CSV", f"/reports/daily/{a.id}/csv/?date={dia}"),
                         ("diario PDF", f"/reports/daily/{a.id}/pdf/?date={dia}"),
                         ("período CSV", f"/reports/period/{a.id}/csv/"),
                         ("período PDF", f"/reports/period/{a.id}/pdf/")]:
        r = ca.get(ruta)
        tipo = r.get("Content-Type", "")
        cuerpo = r.content[:5]
        valido = r.status_code == 200 and (("csv" in tipo) if "CSV" in nombre else (cuerpo == b"%PDF-"))
        res[nombre] = (r.status_code, tipo.split(";")[0], valido)
    ok = all(v[2] for v in res.values())
    registrar("PR-FUN-10", "Reportes CSV y PDF", ok, str(res),
              (f"{'Aprobada' if ok else 'No aprobada'}: los reportes diario y por período se descargan en CSV y en PDF "
               f"({sum(v[2] for v in res.values())} de 4 archivos válidos: CSV con tipo text/csv y PDF con cabecera %PDF)."
               " Evidencia en evidencias/E03."))


@prueba("PR-FUN-13", "Reporte frente a datos conocidos (KPI-08)")
def fun13(ctx):
    a, ca, dia, esperadas = ctx["A"], ctx["cliA"], ctx["dia"], ctx["sesiones"]
    filas = leer_csv(ca.get(f"/reports/daily/{a.id}/csv/?date={dia.isoformat()}"))
    val = {f[0]: f[1] for f in filas if len(f) >= 2}
    n_csv = int(float(str(val.get("Sesiones de atención", "0")).replace(",", ".")))
    g_csv = float(str(val.get("Promedio de comensales", "0")).replace(",", "."))
    n_ref = len(esperadas)
    g_ref = sum(s.guests_count for s, _, _ in esperadas) / n_ref
    pdf = ca.get(f"/reports/daily/{a.id}/pdf/?date={dia.isoformat()}").content
    casos = [("sesiones", n_csv, n_ref), ("promedio de comensales", round(g_csv, 2), round(g_ref, 2))]
    coinc = sum(1 for _, x, y in casos if x == y)
    ok = coinc == len(casos) and pdf[:5] == b"%PDF-"
    registrar("PR-FUN-13", "Reporte frente a datos conocidos (KPI-08)", ok,
              "; ".join(f"{n}: reporte {x}, referencia {y}" for n, x, y in casos),
              (f"{'Aprobada' if ok else 'No aprobada'}: con un conjunto de referencia de {n_ref} atenciones de "
               f"{g_ref:.2f} comensales en promedio, el reporte diario exportado coincide en {coinc} de {len(casos)} "
               f"indicadores ({100 * coinc // len(casos)} %) y el PDF se genera. Evidencia en evidencias/E03."))


@prueba("PR-RES-02", "Cámara con dirección inválida e incidencia")
def res02(ctx):
    from ai_vision.models import AnalysisSession
    from ai_vision.management.commands.run_camera_analysis import Command as Analizar
    from cameras.models import Camera
    from monitoring.models import Incident
    from venues.models import Venue
    local = next((v for v in Venue.objects.filter(is_active=True) if Analizar().policy_is_authorized(v.id)), None)
    if local is None:
        registrar("PR-RES-02", "Cámara con dirección inválida e incidencia", None,
                  "Ningún local tiene política y autorización vigentes; autoriza uno y repite.", "")
        return
    cam = Camera.objects.create(venue=local, name="Prueba URL inválida", source_type=Camera.SourceType.IP_CAMERA,
                                source="rtsp://127.0.0.1:9/no-existe", is_active=True)
    ses = AnalysisSession.objects.create(camera=cam, status=AnalysisSession.Status.PENDING)
    inc0 = Incident.objects.count()
    t0 = time.perf_counter()
    mensaje, cayo = "", False
    try:
        call_command("run_camera_analysis", ses.id, "--no-preview", "--max-frames", "5", stdout=io.StringIO())
    except CommandError as e:
        mensaje = str(e)
    except Exception as e:  # noqa: BLE001
        cayo, mensaje = True, f"{type(e).__name__}: {e}"
    seg = time.perf_counter() - t0
    ses.refresh_from_db()
    nuevas = Incident.objects.count() - inc0
    sin_caida = not cayo and bool(mensaje)
    registrar("PR-RES-02", "Cámara con dirección inválida", sin_caida,
              f"Mensaje: «{mensaje}» en {seg:.1f} s; estado de la sesión: {ses.status}",
              (f"{'Aprobada' if sin_caida else 'No aprobada'}: con una cámara IP de dirección inválida, el análisis "
               f"termina en {seg:.1f} s con un mensaje claro («{mensaje[:90]}») y la plataforma sigue operando (RNF24). "
               "Evidencia en evidencias/E03."))
    registrar("PR-FUN-11", "Registro de incidencia ante fuente fallida", nuevas > 0,
              f"Incidencias nuevas tras la falla: {nuevas}",
              ("Aprobada: la falla de la fuente quedó registrada como incidencia y puede revisarse." if nuevas > 0 else
               "No aprobada: la falla de la fuente se informa con un mensaje claro, pero "
               "la plataforma no crea una incidencia automáticamente; las incidencias se revisan y resuelven en pantalla, "
               "pero no se generan ante una fuente fallida. Se registra como cambio recomendado."))


def main():
    from operations.models import RestaurantTable, ServiceSession
    from venues.models import Venue
    hosts = list(settings.ALLOWED_HOSTS) + ["testserver"]
    with override_settings(LEGAL_ACCEPTANCE_REQUIRED=False, ALLOWED_HOSTS=hosts):
        with transaction.atomic():
            A = Venue.objects.create(name="Local de prueba A (E03)", is_active=True)
            B = Venue.objects.create(name="Local de prueba B (E03)", is_active=True)
            _, cliA = usuario("e03_admin_a", "venue_admin", [A])
            _, cliB = usuario("e03_admin_b", "venue_admin", [B])
            mesa = RestaurantTable.objects.create(venue=A, code="REF-1", capacity=6, zone_name="Salón")
            dia = timezone.localdate() - timedelta(days=1)
            tz = timezone.get_current_timezone()
            def hora(h, m):
                return timezone.make_aware(datetime(dia.year, dia.month, dia.day, h, m), tz)
            sesiones = []
            for (h1, m1, h2, m2, g) in [(12, 0, 12, 45, 2), (13, 10, 14, 25, 4), (20, 0, 21, 30, 3)]:
                ini, fin = hora(h1, m1), hora(h2, m2)
                s = ServiceSession.objects.create(table=mesa, status=ServiceSession.Status.CLOSED, started_at=ini,
                                                  ended_at=fin, guests_count=g)
                ServiceSession.objects.filter(pk=s.pk).update(started_at=ini, ended_at=fin)
                s.refresh_from_db()
                sesiones.append((s, ini, fin))
            ctx = {"A": A, "B": B, "cliA": cliA, "cliB": cliB, "dia": dia, "sesiones": sesiones}
            for t in (seg02, fun03, dat01, fun10, fun13, res02):
                t(ctx)
            transaction.set_rollback(True)
    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "pruebas_funcionales.json").write_text(json.dumps(
        {"fecha": datetime.now().isoformat(timespec="minutes"), "resultados": RES}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    lineas = ["PRUEBAS FUNCIONALES E03", ""] + [
        f"{r['codigo']}: {({True: 'APROBADA', False: 'NO APROBADA', None: 'NO EJECUTADA'})[r['resultado']]}\n"
        f"   {r['texto_ficha'] or r['detalle']}" for r in RES]
    (SALIDA / "resumen_funcionales.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n" + "=" * 70 + "\n" + "\n".join(lineas))
    print("\nLa transacción se deshizo: no quedaron datos de prueba en la base.")


if __name__ == "__main__":
    main()
