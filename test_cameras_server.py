"""
Módulo de prueba para verificar conexión de cámaras con el servidor Django activo.
Este script valida que las cámaras registradas en la base de datos puedan establecer
conexión y capturar frames correctamente.

Uso:
    python test_cameras_server.py

Requisitos:
    - Servidor Django ejecutándose (python manage.py runserver)
    - Entorno virtual activado
    - Dependencias: opencv-python, requests
"""

import os
import sys
import cv2
import time
from datetime import datetime

# Configurar paths correctamente
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir  # Asumiendo que el script está en la raíz

# Agregar la raíz del proyecto al path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Buscar el módulo de settings de Django
settings_module = None
possible_settings = [
    'gastroinsight_ai.settings',
    'config.settings',
    'core.settings',
    'settings'
]

for settings in possible_settings:
    try:
        # Verificar si el módulo existe
        parts = settings.split('.')
        module_path = os.path.join(project_root, *parts[:-1])
        settings_file = os.path.join(module_path, parts[-1] + '.py')
        
        if os.path.exists(settings_file):
            settings_module = settings
            break
    except:
        continue

if not settings_module:
    # Intentar detectar automáticamente
    for item in os.listdir(project_root):
        item_path = os.path.join(project_root, item)
        if os.path.isdir(item_path):
            settings_file = os.path.join(item_path, 'settings.py')
            if os.path.exists(settings_file):
                settings_module = f"{item}.settings"
                break

if not settings_module:
    print("✗ Error: No se pudo encontrar el módulo de settings de Django")
    print("\nBuscando en:")
    print(f"  {project_root}")
    print("\nPor favor, ejecuta este script desde la raíz del proyecto")
    sys.exit(1)

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

try:
    import django
    django.setup()
    print(f"✓ Django configurado correctamente ({settings_module})")
except Exception as e:
    print(f"✗ Error configurando Django: {e}")
    print(f"\nSettings module intentado: {settings_module}")
    print("\nAsegúrate de:")
    print("  1. Estar en la raíz del proyecto (donde está manage.py)")
    print("  2. Tener el entorno virtual activado")
    print("  3. Haber ejecutado 'python manage.py migrate'")
    sys.exit(1)

try:
    from cameras.models import Camera
    print("✓ Modelos de cameras cargados correctamente")
except Exception as e:
    print(f"✗ Error cargando modelos de cameras: {e}")
    print("\nVerifica que la app 'cameras' esté en INSTALLED_APPS")
    sys.exit(1)


class CameraTester:
    """Clase para probar conexión y captura de cámaras"""
    
    def __init__(self, timeout_frames=30, frame_timeout=5):
        self.timeout_frames = timeout_frames  # Máximo de frames a capturar
        self.frame_timeout = frame_timeout  # Segundos sin respuesta antes de timeout
        
    def test_camera_connection(self, camera_id, camera_url, camera_name="Cámara"):
        """
        Prueba conexión a una cámara específica
        
        Args:
            camera_id: ID de la cámara en la base de datos
            camera_url: URL/RTSP de la cámara
            camera_name: Nombre descriptivo de la cámara
            
        Returns:
            dict: Resultados de la prueba
        """
        print(f"\n{'='*60}")
        print(f"Probando cámara: {camera_name} (ID: {camera_id})")
        print(f"URL: {camera_url}")
        print(f"{'='*60}")
        
        results = {
            'camera_id': camera_id,
            'camera_name': camera_name,
            'camera_url': camera_url,
            'connection_success': False,
            'frames_captured': 0,
            'first_frame_size': None,
            'error_message': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Intentar abrir la cámara
            print("  [1/3] Intentando abrir conexión...")
            cap = cv2.VideoCapture(camera_url)
            
            # Verificar si abrió correctamente
            if not cap.isOpened():
                results['error_message'] = "No se pudo abrir la cámara - URL inválida o cámara offline"
                print(f"  ✗ Error: {results['error_message']}")
                cap.release()
                return results
            
            print("  ✓ Conexión establecida exitosamente")
            results['connection_success'] = True
            
            # Esperar un momento para que la cámara se inicialice
            time.sleep(1)
            
            # Intentar capturar frames
            print(f"  [2/3] Capturando frames de prueba (máx {self.timeout_frames})...")
            frames_captured = 0
            first_frame_size = None
            
            for i in range(self.timeout_frames):
                ret, frame = cap.read()
                
                if not ret:
                    print(f"  ⚠ No se pudo leer frame {i+1}")
                    if i == 0:
                        results['error_message'] = "La cámara no está enviando frames"
                        break
                    continue
                
                frames_captured += 1
                
                # Guardar información del primer frame
                if first_frame_size is None:
                    first_frame_size = frame.shape
                    print(f"  ✓ Primer frame capturado: {first_frame_size[1]}x{first_frame_size[0]}")
                
                # Mostrar progreso
                if frames_captured % 5 == 0:
                    print(f"    Frames capturados: {frames_captured}")
            
            results['frames_captured'] = frames_captured
            results['first_frame_size'] = first_frame_size
            
            if frames_captured > 0:
                print(f"  ✓ Frames capturados exitosamente: {frames_captured}")
            else:
                results['error_message'] = "No se capturaron frames válidos"
                print(f"  ✗ Error: {results['error_message']}")
            
            # Liberar cámara
            print("  [3/3] Cerrando conexión...")
            cap.release()
            print("  ✓ Conexión cerrada correctamente")
            
        except cv2.error as e:
            results['error_message'] = f"Error de OpenCV: {str(e)}"
            print(f"  ✗ Error de OpenCV: {e}")
            
        except Exception as e:
            results['error_message'] = f"Error inesperado: {str(e)}"
            print(f"  ✗ Error inesperado: {e}")
        
        # Resumen de resultados
        print(f"\n  {'='*40}")
        print(f"  RESUMEN:")
        print(f"  {'='*40}")
        print(f"  Estado: {'✓ EXITOSO' if results['connection_success'] and results['frames_captured'] > 0 else '✗ FALLIDO'}")
        print(f"  Frames capturados: {results['frames_captured']}")
        if first_frame_size:
            print(f"  Resolución: {first_frame_size[1]}x{first_frame_size[0]}")
        if results['error_message']:
            print(f"  Error: {results['error_message']}")
        print(f"  {'='*40}")
        
        return results
    
    def test_all_cameras_from_db(self):
        """
        Prueba todas las cámaras registradas en la base de datos
        
        Returns:
            list: Lista de resultados de todas las cámaras
        """
        print("\n" + "="*60)
        print(" TEST DE CÁMARAS - GastroInsight AI")
        print("="*60)
        print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Obtener todas las cámaras de la base de datos
        try:
            cameras = Camera.objects.all()
            print(f"\nCámaras encontradas en BD: {cameras.count()}")
        except Exception as e:
            print(f"\n✗ Error consultando la base de datos: {e}")
            return []
        
        if cameras.count() == 0:
            print("\n⚠ No hay cámaras registradas en la base de datos")
            print("  Registra al menos una cámara antes de ejecutar este test")
            return []
        
        all_results = []
        
        # Probar cada cámara
        for camera in cameras:
            # Construir URL de conexión
            camera_url = self._build_camera_url(camera)
            
            # Probar conexión
            result = self.test_camera_connection(
                camera_id=camera.id,
                camera_url=camera_url,
                camera_name=camera.name
            )
            
            all_results.append(result)
            
            # Pequeña pausa entre pruebas
            time.sleep(2)
        
        # Resumen general
        self._print_summary(all_results)
        
        return all_results
    
    def _build_camera_url(self, camera):
        """
        Construye la URL de conexión según los campos disponibles del modelo Camera
        
        Args:
            camera: Objeto Camera de Django
            
        Returns:
            str: URL para cv2.VideoCapture
        """
        # Obtener todos los campos del modelo
        available_fields = [f.name for f in Camera._meta.get_fields()]
        
        # Obtener stream_url (campo principal)
        stream_url = getattr(camera, 'stream_url', None)
        
        # Si no hay stream_url, buscar campos alternativos
        if not stream_url:
            for field_name in ['url', 'rtsp_url', 'ip_url', 'location', 'address']:
                if field_name in available_fields:
                    stream_url = getattr(camera, field_name, None)
                    if stream_url:
                        break
        
        # Si aún no hay URL, intentar con ip + puerto
        if not stream_url:
            ip = getattr(camera, 'ip_address', None) or getattr(camera, 'ip', None)
            port = getattr(camera, 'port', None) or getattr(camera, 'rtsp_port', None)
            
            if ip and port:
                stream_url = f"rtsp://{ip}:{port}/stream1"
            elif ip:
                stream_url = f"rtsp://{ip}:554/stream1"
        
        # Si es webcam local (número)
        if stream_url and stream_url.isdigit():
            return int(stream_url)
        
        # Si hay credenciales, insertarlas en la URL
        username = getattr(camera, 'username', None)
        password = getattr(camera, 'password', None)
        
        if username and password and stream_url and '@' not in stream_url:
            # Insertar credenciales
            url_parts = stream_url.split('://')
            if len(url_parts) == 2:
                protocol, rest = url_parts
                return f"{protocol}://{username}:{password}@{rest}"
        
        # Por defecto, retornar stream_url o valor por defecto
        return stream_url if stream_url else 0
    
    def _print_summary(self, results):
        """Imprime resumen general de todas las pruebas"""
        print("\n" + "="*60)
        print(" RESUMEN GENERAL")
        print("="*60)
        
        total = len(results)
        successful = sum(1 for r in results if r['connection_success'] and r['frames_captured'] > 0)
        failed = total - successful
        
        print(f"\nTotal de cámaras probadas: {total}")
        print(f"✓ Exitosas: {successful}")
        print(f"✗ Fallidas: {failed}")
        
        if failed > 0:
            print("\nCámaras con problemas:")
            for result in results:
                if not result['connection_success'] or result['frames_captured'] == 0:
                    print(f"  - {result['camera_name']} (ID: {result['camera_id']})")
                    if result['error_message']:
                        print(f"    Error: {result['error_message']}")
        
        print("\n" + "="*60)
        
        # Guardar resultados en archivo JSON para referencia
        self._save_results_to_file(results)
    
    def _save_results_to_file(self, results):
        """Guarda los resultados en un archivo JSON"""
        try:
            import json
            
            filename = f"test_cameras_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            
            print(f"\n✓ Resultados guardados en: {filename}")
            
        except Exception as e:
            print(f"\n⚠ No se pudieron guardar los resultados: {e}")


def test_single_camera(camera_id):
    """Función auxiliar para probar una cámara específica por ID"""
    try:
        camera = Camera.objects.get(id=camera_id)
        tester = CameraTester()
        
        camera_url = tester._build_camera_url(camera)
        
        result = tester.test_camera_connection(
            camera_id=camera.id,
            camera_url=camera_url,
            camera_name=camera.name
        )
        
        return result
        
    except Camera.DoesNotExist:
        print(f"✗ Cámara con ID {camera_id} no encontrada")
        return None


if __name__ == '__main__':
    print("\n" + "="*60)
    print(" TEST DE CONEXIÓN DE CÁMARAS - GastroInsight AI")
    print("="*60)
    print("\nEste script probará la conexión de todas las cámaras")
    print("registradas en la base de datos con el servidor activo.\n")
    
    # Verificar que Django esté configurado
    try:
        from cameras.models import Camera
        print("✓ Modelos de Django cargados correctamente")
    except Exception as e:
        print(f"✗ Error cargando modelos: {e}")
        print("\nAsegúrate de:")
        print("  1. Estar en la raíz del proyecto (donde está manage.py)")
        print("  2. Tener el entorno virtual activado")
        print("  3. Haber ejecutado 'python manage.py migrate'")
        sys.exit(1)
    
    # Ejecutar pruebas
    tester = CameraTester()
    results = tester.test_all_cameras_from_db()
    
    # Código de salida según resultados
    if results:
        successful = sum(1 for r in results if r['connection_success'] and r['frames_captured'] > 0)
        if successful == len(results):
            print("\n✓ TODAS LAS CÁMARAS FUNCIONAN CORRECTAMENTE")
            sys.exit(0)
        elif successful > 0:
            print(f"\n⚠ ALGUNAS CÁMARAS PRESENTAN PROBLEMAS ({successful}/{len(results)})")
            sys.exit(1)
        else:
            print("\n✗ NINGUNA CÁMARA FUNCIONA CORRECTAMENTE")
            sys.exit(2)
    else:
        print("\n⚠ NO SE EJECUTARON PRUEBAS (sin cámaras en BD)")
        sys.exit(3)