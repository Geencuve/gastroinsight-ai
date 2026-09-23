"""
Script rápido para probar una cámara específica sin cargar todo Django.
Ideal para pruebas rápidas de conexión.

Uso:
    python test_camera_rapida.py --url "rtsp://admin:password@192.168.1.100:554/stream1"
    python test_camera_rapida.py --url "http://192.168.1.50:8080/video"
    python test_camera_rapida.py --camera 0  # webcam local
"""

import cv2
import argparse
import time
from datetime import datetime


def test_camera(url_or_index, timeout_seconds=10, max_frames=30):
    """
    Prueba rápida de conexión a cámara
    
    Args:
        url_or_index: URL de la cámara o índice de webcam (0, 1, 2...)
        timeout_seconds: Tiempo máximo de prueba
        max_frames: Máximo de frames a capturar
        
    Returns:
        bool: True si la cámara funciona, False si falla
    """
    print(f"\n{'='*60}")
    print(f" PRUEBA RÁPIDA DE CÁMARA")
    print(f"{'='*60}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"URL/Índice: {url_or_index}")
    print(f"{'='*60}\n")
    
    try:
        # Abrir cámara
        print("[1/4] Abriendo conexión...")
        cap = cv2.VideoCapture(url_or_index)
        
        # Verificar apertura
        if not cap.isOpened():
            print("✗ ERROR: No se pudo abrir la cámara")
            print("  Posibles causas:")
            print("  - URL incorrecta o mal formada")
            print("  - Cámara offline o sin alimentación")
            print("  - Credenciales inválidas")
            print("  - Firewall bloqueando conexión")
            cap.release()
            return False
        
        print("✓ Conexión establecida\n")
        
        # Esperar inicialización
        print("[2/4] Esperando inicialización de cámara...")
        time.sleep(2)
        
        # Capturar frames
        print(f"[3/4] Capturando frames (máx {max_frames} frames / {timeout_seconds}s)...")
        frames_captured = 0
        first_frame_time = time.time()
        first_frame_size = None
        
        while frames_captured < max_frames:
            elapsed = time.time() - first_frame_time
            if elapsed > timeout_seconds:
                print(f"  ⏱ Timeout alcanzado ({timeout_seconds}s)")
                break
            
            ret, frame = cap.read()
            
            if not ret:
                if frames_captured == 0:
                    print("✗ ERROR: La cámara no está enviando frames")
                    cap.release()
                    return False
                print(f"  ⚠ Frame {frames_captured+1} no leído correctamente")
                continue
            
            frames_captured += 1
            
            # Guardar info del primer frame
            if first_frame_size is None:
                first_frame_size = frame.shape
                print(f"  ✓ Primer frame: {first_frame_size[1]}x{first_frame_size[0]} px")
            
            # Mostrar progreso cada 5 frames
            if frames_captured % 5 == 0:
                print(f"    Frames: {frames_captured}")
        
        # Cerrar conexión
        print("[4/4] Cerrando conexión...")
        cap.release()
        print("✓ Conexión cerrada\n")
        
        # Resumen
        print(f"{'='*60}")
        print(" RESULTADOS:")
        print(f"{'='*60}")
        print(f"Estado: {'✓ EXITOSO' if frames_captured > 0 else '✗ FALLIDO'}")
        print(f"Frames capturados: {frames_captured}")
        if first_frame_size:
            print(f"Resolución: {first_frame_size[1]}x{first_frame_size[0]}")
        print(f"{'='*60}\n")
        
        return frames_captured > 0
        
    except cv2.error as e:
        print(f"\n✗ ERROR DE OPENCV: {e}")
        return False
        
    except Exception as e:
        print(f"\n✗ ERROR INESPERADO: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Prueba rápida de conexión a cámara',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python test_camera_rapida.py --url "rtsp://admin:1234@192.168.1.100:554/stream"
  python test_camera_rapida.py --url "http://192.168.1.50:8080/video"
  python test_camera_rapida.py --camera 0
  python test_camera_rapida.py --camera 1
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--url', type=str, help='URL de la cámara IP/RTSP')
    group.add_argument('--camera', type=int, help='Índice de webcam local (0, 1, 2...)')
    
    parser.add_argument('--timeout', type=int, default=10, 
                       help='Tiempo máximo de prueba en segundos (default: 10)')
    parser.add_argument('--frames', type=int, default=30,
                       help='Máximo de frames a capturar (default: 30)')
    
    args = parser.parse_args()
    
    # Determinar qué probar
    if args.url:
        target = args.url
    else:
        target = args.camera
    
    # Ejecutar prueba
    success = test_camera(
        url_or_index=target,
        timeout_seconds=args.timeout,
        max_frames=args.frames
    )
    
    # Código de salida
    if success:
        print("✓ LA CÁMARA FUNCIONA CORRECTAMENTE\n")
        exit(0)
    else:
        print("✗ LA CÁMARA PRESENTA PROBLEMAS\n")
        exit(1)


if __name__ == '__main__':
    main()