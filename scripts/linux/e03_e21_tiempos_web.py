"""
E03 (PR-REN-02, Tabla 18.150) y E21 (PR-REN-03, Tabla 12.7): tiempos de respuesta del tablero.

Requiere la plataforma corriendo:  venv/bin/python manage.py runserver
y un usuario con acceso al local. La contraseña se pide por teclado (no queda guardada).

PR-REN-02, veinte repeticiones de tres operaciones:
  venv/bin/python scripts/linux/e03_e21_tiempos_web.py tablero --usuario admin --local 1

PR-REN-03, un escenario de carga (repite con cada escenario de la Tabla 12.7):
  venv/bin/python scripts/linux/e03_e21_tiempos_web.py carga --usuario admin --local 1 --usuarios 3 --minutos 5 --escenario normal
  Para "operación normal" y "carga máxima" deja antes las fuentes de video en análisis desde la plataforma.
  Para "estrés":  ... carga --usuarios 3,5,10,15,20 --minutos 2 --escenario estres
Opcional: --pid <PID de runserver> para medir CPU y memoria del servidor.
"""
import argparse
import getpass
import http.cookiejar
import json
import os
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[2]


def sesion(url, usuario, clave):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    html = op.open(url + "/auth/login/", timeout=30).read().decode("utf-8", "replace")
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
    datos = urllib.parse.urlencode({"csrfmiddlewaretoken": token, "username": usuario, "password": clave}).encode()
    req = urllib.request.Request(url + "/auth/login/", data=datos, headers={"Referer": url + "/auth/login/"})
    r = op.open(req, timeout=30)
    if "/auth/login/" in r.geturl():
        raise SystemExit("No se pudo iniciar sesión: revisa usuario y contraseña.")
    return op


def medir(op, ruta, url):
    t = time.perf_counter()
    try:
        r = op.open(url + ruta, timeout=60)
        r.read()
        ok = r.status == 200 and "/auth/login/" not in r.geturl()
    except Exception:
        ok = False
    return (time.perf_counter() - t) * 1000, ok


def operaciones(local):
    ayer = (date.today() - timedelta(days=1)).isoformat()
    return {"Abrir el tablero": "/analytics/",
            "Filtrar por período": f"/analytics/?date={ayer}",
            "Exportar el reporte diario (CSV)": f"/reports/daily/{local}/csv/"}


class Cpu:
    def __init__(self, pid):
        self.pid, self.muestras, self.ram, self.activo = pid, [], [], True

    def _ticks(self):
        with open(f"/proc/{self.pid}/stat") as f:
            c = f.read().split(")")[-1].split()
        return int(c[11]) + int(c[12])

    def correr(self):
        hz, n = os.sysconf("SC_CLK_TCK"), os.cpu_count()
        prev, tp = self._ticks(), time.time()
        while self.activo:
            time.sleep(1)
            now, tn = self._ticks(), time.time()
            self.muestras.append(100 * (now - prev) / hz / (tn - tp) / n)
            prev, tp = now, tn
            with open(f"/proc/{self.pid}/status") as f:
                m = re.search(r"VmRSS:\s+(\d+)", f.read())
            self.ram.append(int(m.group(1)) / 1024 if m else 0)


def tablero(args, op):
    salida = RAIZ / "evidencias" / "E03"; salida.mkdir(parents=True, exist_ok=True)
    filas, crudo = [], {}
    for nombre, ruta in operaciones(args.local).items():
        medir(op, ruta, args.url)  # calentamiento
        ts = [medir(op, ruta, args.url) for _ in range(20)]
        tiempos = [t for t, _ in ts]
        errores = sum(1 for _, ok in ts if not ok)
        crudo[nombre] = tiempos
        filas.append((nombre, np.median(tiempos) / 1000, np.percentile(tiempos, 95) / 1000, errores))
    (salida / "tiempos_tablero.json").write_text(json.dumps({"fecha": datetime.now().isoformat(timespec="minutes"),
                                                          "tiempos_ms": crudo}, indent=1, ensure_ascii=False), encoding="utf-8")
    peor = max(f[2] for f in filas)
    lineas = ["FICHA PR-REN-02: TIEMPO DE RESPUESTA DEL TABLERO (20 repeticiones)",
              f"{'Operación':<36}{'Mediana':>10}{'P95':>10}{'Errores':>9}"]
    lineas += [f"{n:<36}{m:>9.2f}s{p:>9.2f}s{e:>9}" for n, m, p, e in filas]
    lineas += ["", "Texto para la ficha (Resultado obtenido):",
               f"{'Aprobada' if peor <= 3 and not any(f[3] for f in filas) else 'No aprobada'}: percentil 95 de "
               + "; ".join(f"{n.lower()} {p:.2f} s".replace(".", ",") for n, _, p, _ in filas)
               + " (criterio ≤ 3 s). Registro de tiempos en evidencias/E03/tiempos_tablero.json."]
    (salida / "resumen_tablero.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


def carga(args, clave):
    salida = RAIZ / "evidencias" / "E21"; salida.mkdir(parents=True, exist_ok=True)
    niveles = [int(x) for x in str(args.usuarios).split(",")]
    resultados = []
    for n in niveles:
        print(f"Escenario {args.escenario}: {n} usuarios durante {args.minutos} min...")
        sesiones = [sesion(args.url, args.usuario, clave) for _ in range(n)]
        tiempos, errores, fin = [], [0], time.time() + 60 * args.minutos
        lock = threading.Lock()
        rutas = list(operaciones(args.local).values())[:2]
        def usuario(op):
            i = 0
            while time.time() < fin:
                t, ok = medir(op, rutas[i % 2], args.url); i += 1
                with lock:
                    tiempos.append(t)
                    errores[0] += 0 if ok else 1
                time.sleep(1)  # pausa de "lectura" entre consultas
        cpu = Cpu(args.pid) if args.pid else None
        if cpu:
            threading.Thread(target=cpu.correr, daemon=True).start()
        hilos = [threading.Thread(target=usuario, args=(op,)) for op in sesiones]
        [h.start() for h in hilos]; [h.join() for h in hilos]
        if cpu:
            cpu.activo = False
        r = {"usuarios": n, "solicitudes": len(tiempos), "p95_s": round(float(np.percentile(tiempos, 95)) / 1000, 2),
             "mediana_s": round(float(np.median(tiempos)) / 1000, 2), "errores": errores[0]}
        if cpu and cpu.muestras:
            r.update(cpu_media_pct=round(float(np.mean(cpu.muestras)), 1), cpu_max_pct=round(float(max(cpu.muestras)), 1),
                     ram_max_mb=round(max(cpu.ram)))
        resultados.append(r)
        print("  ", r)
    archivo = salida / f"carga_{args.escenario}_{datetime.now():%Y%m%d_%H%M}.json"
    archivo.write_text(json.dumps({"escenario": args.escenario, "resultados": resultados}, indent=1), encoding="utf-8")
    print("\nTexto para la columna Resultado de la Tabla 12.7:")
    if args.escenario == "estres":
        limite = next((r["usuarios"] for r in resultados if r["p95_s"] > 3 or r["errores"]), None)
        print(f"Límite: {'sobre ' + str(niveles[-1]) + ' usuarios no se superan 3 s ni hay errores' if limite is None else f'con {limite} usuarios se supera 3 s o aparecen errores'}.")
    else:
        r = resultados[-1]
        extra = f", CPU media {r['cpu_media_pct']} % (máx. {r['cpu_max_pct']} %), memoria máx. {r['ram_max_mb']} MB" if "cpu_media_pct" in r else ""
        print(f"P95 {r['p95_s']} s con {r['usuarios']} usuarios{extra}, {r['errores']} errores en {r['solicitudes']} solicitudes "
              f"({'aprobado' if r['p95_s'] <= 3 and (args.escenario != 'maxima' or r['errores'] == 0) else 'no aprobado'}).".replace(".", ",", 1))
    print(f"Evidencia: {archivo.relative_to(RAIZ)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("modo", choices=["tablero", "carga"])
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--usuario", required=True)
    p.add_argument("--local", type=int, default=1, help="id del local (aparece en la URL de sus reportes)")
    p.add_argument("--usuarios", default="1")
    p.add_argument("--minutos", type=float, default=5)
    p.add_argument("--escenario", default="base", choices=["base", "normal", "maxima", "estres"])
    p.add_argument("--pid", type=int)
    args = p.parse_args()
    clave = getpass.getpass("Contraseña: ")
    if args.modo == "tablero":
        tablero(args, sesion(args.url, args.usuario, clave))
    else:
        carga(args, clave)


if __name__ == "__main__":
    main()
