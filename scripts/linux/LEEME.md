# Scripts para cerrar las marcas PENDIENTE (Linux)

Copia esta carpeta dentro del proyecto como `scripts/linux/`. Así:

```
gastroinsight-ai/
├── manage.py
└── scripts/
    └── linux/      <- aquí van estos archivos
```

Abre una terminal en la carpeta `gastroinsight-ai` y sigue los pasos en orden. Cada script deja sus
resultados en `evidencias/Exx/` y al final imprime un **"Texto para la ficha"**: ese texto es el que
reemplaza la marca `[PENDIENTE Exx]` en el informe.

## 0. Preparar el entorno (una sola vez)

```
bash scripts/linux/preparar_entorno.sh
venv/bin/python manage.py createsuperuser      # si aún no tienes usuario
```

Si falta el modelo YOLO del equipo (`ai_vision/ml_models/mesas_personas_yolo26s.onnx`), cópialo a esa carpeta.

## 1. E28 y E03: pruebas de la versión congelada (HAZ ESTO PRIMERO)

Con el código en la versión que se entrega y confirmada en Git:

```
bash scripts/linux/e28_regenerar_evidencias.sh
```

Corre las pruebas con cobertura y la auditoría por rol, y deja todo en `evidencias/E28`. Comprime esa carpeta y pásamela: con ella se cierran las 25 marcas de E03 y E28.

## 1b. E03: solo pruebas (opcional)

```
bash scripts/linux/e03_pruebas.sh
```

Resultado en `evidencias/E03/resumen.txt` (total, aprobadas, fallidas, cobertura). Con esto se completan la
Tabla 12.3 y las marcas E03 del catálogo de pruebas.

## 2. E10: respaldo y restauración

Detén la plataforma si está corriendo (Ctrl + C en su terminal) y ejecuta:

```
venv/bin/python scripts/linux/e10_respaldo_restauracion.py
```

Completa la Tabla 13.3 y la ficha 18.140. La base original no se toca.

## 3. E08: búsqueda de imágenes

```
venv/bin/python scripts/linux/e08_inventario_imagenes.py antes
```

Luego inicia la plataforma, deja una cámara en análisis unos 10 minutos, revoca la autorización a mitad de
camino y reinicia la aplicación. Al terminar:

```
venv/bin/python scripts/linux/e08_inventario_imagenes.py despues
```

Completa la ficha 18.137.

## 4. E07 y E26: latencia (Tabla 9.6)

Cierra otros programas pesados. Con la webcam:

```
venv/bin/python scripts/linux/e07_medir_latencia.py --camara 0
```

O con un video: `--video ruta/al/video.mp4`. Tarda unos minutos (1.000 fotogramas por escenario).
Completa la Tabla 9.6 y la ficha 18.149.

## 5. E03 y E21: tiempos del tablero y carga

En una terminal deja la plataforma corriendo:

```
venv/bin/python manage.py runserver
```

En otra terminal (la contraseña se pide por teclado):

```
venv/bin/python scripts/linux/e03_e21_tiempos_web.py tablero --usuario TU_USUARIO --local 1
```

Para la Tabla 12.7, un comando por escenario. Para conocer el PID de runserver, usa `pgrep -f runserver`:

```
... carga --usuario TU_USUARIO --usuarios 1 --minutos 5 --escenario base --pid PID
... carga --usuario TU_USUARIO --usuarios 3 --minutos 5 --escenario normal --pid PID      (1 cámara en análisis)
... carga --usuario TU_USUARIO --usuarios 3 --minutos 5 --escenario maxima --pid PID      (4 fuentes en análisis)
... carga --usuario TU_USUARIO --usuarios 3,5,10,15,20 --minutos 2 --escenario estres --pid PID
```

`--local` es el número del local que aparece en la dirección de sus reportes.

## 6. E06: métricas de expresiones (Tabla 12.4)

Primero carga las muestras etiquetadas con consentimiento en la sección de entrenamiento de la plataforma.
Luego ejecuta:

```
venv/bin/python scripts/linux/e06_metricas_expresiones.py
```

## Si algo falla

Copia el mensaje de error completo y pásamelo.
