from time import perf_counter

import cv2


class HaarFaceDetector:
    """
    Detector facial utilizando Haar Cascade de OpenCV.
    """

    def __init__(self):
        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        self.classifier = cv2.CascadeClassifier(cascade_path)

        if self.classifier.empty():
            raise RuntimeError(
                "No se pudo cargar el clasificador Haar de OpenCV."
            )

    def detect(self, frame):
        """
        Detecta rostros en un frame.

        Returns:
            dict:
                {
                    "faces_count": int,
                    "boxes": list,
                    "processing_time_ms": int
                }
        """
        start_time = perf_counter()

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        faces = self.classifier.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )

        elapsed_ms = int(
            (perf_counter() - start_time) * 1000
        )

        boxes = [
            {
                "x": int(x),
                "y": int(y),
                "width": int(width),
                "height": int(height),
            }
            for x, y, width, height in faces
        ]

        return {
            "faces_count": len(boxes),
            "boxes": boxes,
            "processing_time_ms": elapsed_ms,
        }


class FaceDetector(HaarFaceDetector):
    """
    Alias compatible con camera_analyzer.py.

    Permite utilizar:
        FaceDetector()
    sin modificar el nombre original HaarFaceDetector.
    """

    pass