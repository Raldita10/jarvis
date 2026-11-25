"""Genera la hoja de marcadores para imprimir: python tools/marcadores.py

Imprime la hoja al 100% (sin "ajustar a la página"), recorta los 4 marcadores y pon
cada uno por fuera de su esquina del tablero, tocándola: 0 en a1, 1 en h1, 2 en h8, 3 en a8.
"""
from pathlib import Path

import cv2
import numpy as np

DPI = 300
MARKER_CM = 4
OUT = Path(__file__).resolve().parent.parent / "marcadores.png"


def main() -> None:
    px = int(MARKER_CM / 2.54 * DPI)
    page = np.full((int(29.7 / 2.54 * DPI), int(21 / 2.54 * DPI)), 255, np.uint8)  # A4
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    labels = {0: "a1", 1: "h1", 2: "h8", 3: "a8"}
    for i, name in labels.items():
        x = 250 + (i % 2) * (px + 600)
        y = 350 + (i // 2) * (px + 700)
        page[y:y + px, x:x + px] = cv2.aruco.generateImageMarker(dictionary, i, px)
        cv2.rectangle(page, (x - 40, y - 40), (x + px + 40, y + px + 40), 0, 2)  # línea de corte
        cv2.putText(page, f"{i}: esquina {name}", (x, y + px + 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.2, 0, 5)
    cv2.imwrite(str(OUT), page)
    print(f"Listo: {OUT}")


if __name__ == "__main__":
    main()
