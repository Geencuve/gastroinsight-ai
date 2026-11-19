import platform

import cv2


def webcam_backend():
    """Backend de OpenCV para webcams según el sistema operativo."""
    if platform.system() == "Windows":
        return cv2.CAP_DSHOW
    return cv2.CAP_V4L2
