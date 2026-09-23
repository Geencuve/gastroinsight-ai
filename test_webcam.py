import cv2


def main():
    camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not camera.isOpened():
        print("ERROR: No fue posible abrir la webcam con índice 0.")
        print("Prueba cambiando 0 por 1 o verifica los permisos de cámara.")
        return

    print("Webcam abierta. Presiona la tecla q para cerrar.")

    while True:
        success, frame = camera.read()

        if not success:
            print("ERROR: No fue posible leer un frame.")
            break

        cv2.imshow("GastroInsight AI - Prueba de cámara", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()