"""
E10 (PR-RES-01, Tablas 13.3 y 18.140): simulacro de respaldo y restauración de la base SQLite.

Uso (con la plataforma DETENIDA):
  venv/bin/python scripts/linux/e10_respaldo_restauracion.py
Opcional: --base ruta/a/db.sqlite3   --respaldo ruta/a/un/respaldo/existente.sqlite3

Qué hace:
  1. Cuenta las filas de cada tabla de la base.
  2. Si no le das un respaldo existente, crea uno nuevo con la API de respaldo de SQLite.
  3. Simula la pérdida: restaura el respaldo en un archivo nuevo y cronometra la restauración.
  4. Revisa integridad (PRAGMA integrity_check y foreign_key_check) y compara los conteos.
La base original no se modifica.
"""
import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "evidencias" / "E10"


def conteos(ruta):
    con = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    tablas = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    out = {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
    con.close()
    return out


def coma(x):
    return f"{x:.1f}".replace(".", ",")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", default=str(RAIZ / "db.sqlite3"))
    a.add_argument("--respaldo")
    args = a.parse_args()
    base = Path(args.base)
    if not base.exists():
        raise SystemExit(f"No existe la base {base}")
    SALIDA.mkdir(parents=True, exist_ok=True)
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")

    antes = conteos(base)
    if args.respaldo:
        respaldo = Path(args.respaldo)
    else:
        respaldo = SALIDA / f"respaldo_{sello}.sqlite3"
        src, dst = sqlite3.connect(base), sqlite3.connect(respaldo)
        src.backup(dst); dst.close(); src.close()
    edad_h = (time.time() - respaldo.stat().st_mtime) / 3600

    restaurada = SALIDA / f"restaurada_{sello}.sqlite3"
    t0 = time.perf_counter()
    shutil.copy2(respaldo, restaurada)
    con = sqlite3.connect(restaurada)
    integridad = con.execute("PRAGMA integrity_check").fetchone()[0]
    fk = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    despues = conteos(restaurada)
    rto_s = time.perf_counter() - t0

    diferencias = {t: (antes.get(t), despues.get(t)) for t in set(antes) | set(despues) if antes.get(t) != despues.get(t)}
    conforme = integridad == "ok" and not fk and not diferencias
    datos = {"fecha": sello, "base": str(base), "respaldo": str(respaldo), "sha256_respaldo": sha(respaldo),
             "sha256_restaurada": sha(restaurada), "edad_respaldo_horas": round(edad_h, 2),
             "tiempo_restauracion_s": round(rto_s, 2), "integrity_check": integridad,
             "foreign_key_check_filas": len(fk), "tablas": len(antes), "filas_totales": sum(antes.values()),
             "diferencias_de_conteo": diferencias, "conteos_antes": antes}
    (SALIDA / f"simulacro_{sello}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    lineas = ["TABLA 13.3: PRUEBA DE RECUPERACIÓN (PR-RES-01)",
              f"Tiempo de restauración (RTO): {rto_s:.1f} s  (meta ≤ 2 h; solo la restauración de la base)",
              f"Pérdida de datos (RPO): {edad_h:.1f} h, antigüedad del respaldo usado (meta ≤ 24 h)",
              f"Integridad posterior: integrity_check = {integridad}; foreign_key_check: {len(fk)} filas; "
              f"conteos {'iguales' if not diferencias else 'DISTINTOS'} en {len(antes)} tablas ({sum(antes.values())} filas)",
              f"Antigüedad de la última copia válida: {edad_h:.1f} h",
              f"Huella SHA-256 del respaldo: {datos['sha256_respaldo']}", "",
              "Texto para la ficha 18.140 (Resultado obtenido):",
              (f"{'Aprobada' if conforme and edad_h <= 24 else 'No aprobada'}. Simulacro del {datetime.now():%d-%m-%Y}: "
               f"restauración en {coma(rto_s)} s, respaldo de {coma(edad_h)} h de antigüedad, integrity_check = {integridad}, "
               f"foreign_key_check sin {'filas' if not fk else 'errores: ' + str(len(fk))} y conteos "
               f"{'iguales' if not diferencias else 'distintos'} en las {len(antes)} tablas. Evidencia en evidencias/E10.")]
    (SALIDA / "resumen.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))
    print("\nNota: el RTO del informe incluye también los pasos manuales (detener la aplicación, conseguir el respaldo,"
          " reiniciar). Cronométralos con el reloj y súmalos si quieres informar el procedimiento completo.")


if __name__ == "__main__":
    main()
