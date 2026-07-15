"""
main.py
=======

Punto de entrada del programa. Le pregunta al usuario qué partido
quiere predecir (dos selecciones + dónde se juega), calcula la
predicción con src/predictor.py, la muestra por consola y genera +
abre automáticamente los gráficos.

Uso interactivo (por defecto):
    python main.py

Uso no interactivo (para pruebas o automatización), pasando los 2 o 3
argumentos directamente por línea de comandos:
    python main.py "Argentina" "Brasil"
    python main.py "Argentina" "Brasil" neutral
"""

import os
import subprocess
import sys

from src import predictor, visualizer

EQUIPO_LOCAL_DEMO = "Netherlands"
EQUIPO_VISITANTE_DEMO = "Sweden"

RUTA_MATRIZ = "assets/matriz_resultados.png"
RUTA_DISTRIBUCION = "assets/distribucion_resultado.png"
RUTA_FICHA = "assets/ficha_resumen.png"


def pedir_nombre_equipo(etiqueta: str) -> str:
    """Pide por consola el nombre de una selección, sin aceptar vacío.

    Args:
        etiqueta: texto descriptivo a mostrar (ej: "Rival 1").

    Returns:
        El nombre ingresado, sin espacios sobrantes.
    """
    while True:
        nombre = input(f"{etiqueta} (nombre en inglés, ej: Argentina, England): ").strip()
        if nombre:
            return nombre
        print("  -> No puede quedar vacío, escribí un nombre.")


def pedir_sede(equipo_local: str, equipo_visitante: str) -> str:
    """Pregunta interactivamente dónde se juega el partido.

    Usa un bucle de validación (Unidad 4/9): vuelve a preguntar ante
    cualquier entrada que no sea "1", "2" o "3", en vez de romper el
    programa con un ValueError sin capturar.

    Args:
        equipo_local: nombre de la primera selección.
        equipo_visitante: nombre de la segunda selección.

    Returns:
        Uno de "local", "visitante" o "neutral" (ver predictor.py).
    """
    print("\n¿Dónde se juega el partido?")
    print(f"  1) {equipo_local} de local")
    print(f"  2) {equipo_visitante} de local")
    print("  3) Cancha neutral (ej: fase de grupos de un Mundial)")

    opciones = {"1": "local", "2": "visitante", "3": "neutral"}
    while True:
        eleccion = input("Elegí una opción (1/2/3): ").strip()
        if eleccion in opciones:
            return opciones[eleccion]
        print("  -> Opción inválida, ingresá 1, 2 o 3.")


def mostrar_resumen(prediccion: dict) -> None:
    """Imprime en consola un resumen legible de la predicción.

    Args:
        prediccion: diccionario devuelto por ``predecir_partido``.
    """
    local = prediccion["equipo_local"]
    visitante = prediccion["equipo_visitante"]
    probs = prediccion["probabilidades"]

    etiqueta_sede = {
        "local": f"{local} juega de local",
        "visitante": f"{visitante} juega de local",
        "neutral": "cancha neutral",
    }[prediccion["sede"]]

    print("\n" + "=" * 55)
    print(f"  {local}  vs  {visitante}   ({etiqueta_sede})")
    print("=" * 55)
    print(f"xG estimado:  {local} {prediccion['xg_local']}  -  "
          f"{prediccion['xg_visitante']} {visitante}")
    print(f"Ranking FIFA: {local} #{prediccion['ranking_local']}  |  "
          f"{visitante} #{prediccion['ranking_visitante']}")
    print(f"Entorno de goles detectado: {prediccion['promedio_goles_entorno']} "
          f"goles/partido (ancla dinámica, no fija)")
    print("-" * 55)
    print(f"Gana {local}:  {probs['local']}%")
    print(f"Empate:        {probs['empate']}%")
    print(f"Gana {visitante}: {probs['visitante']}%")
    print("-" * 55)
    print("Marcadores más probables (en general):")
    for resultado in prediccion["top_marcadores"]:
        print(f"  {resultado['marcador']}  ->  {resultado['probabilidad']}%")
    print("-" * 55)
    print("Marcador más probable SI GANA cada uno (no es lo mismo que arriba: ")
    print("una victoria se reparte entre más marcadores distintos que un empate):")
    categorias = prediccion["mejor_por_categoria"]
    print(f"  Si gana {local}:    {categorias['local']['marcador']} "
          f"({categorias['local']['probabilidad']}%)")
    print(f"  Si empatan:      {categorias['empate']['marcador']} "
          f"({categorias['empate']['probabilidad']}%)")
    print(f"  Si gana {visitante}:  {categorias['visitante']['marcador']} "
          f"({categorias['visitante']['probabilidad']}%)")
    print("=" * 55)


def abrir_imagen(ruta: str) -> None:
    """Abre un archivo de imagen con el visor por defecto del sistema.

    Usa ``sys.platform`` (Unidad 13) para elegir el comando correcto
    según el sistema operativo. Si no se puede abrir automáticamente
    (ej. un servidor sin entorno gráfico), no rompe el programa: el
    usuario igual tiene la ruta del archivo para abrirlo a mano.

    Args:
        ruta: ruta del archivo de imagen a abrir.
    """
    try:
        if sys.platform.startswith("win"):
            os.startfile(ruta)
        elif sys.platform == "darwin":
            subprocess.run(
                ["open", ruta], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                ["xdg-open", ruta], check=False,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    except (OSError, FileNotFoundError):
        # No hay visor de imágenes disponible en este entorno: no es
        # un error grave, el usuario puede abrir el archivo a mano.
        pass


def obtener_equipos_y_sede() -> tuple[str, str, str]:
    """Determina los 2 equipos y la sede, interactiva o por argumentos.

    Si se pasan 2 o 3 argumentos por línea de comandos, se usan esos
    (modo no interactivo, útil para pruebas). Si no, se le pregunta al
    usuario paso a paso (modo interactivo, el uso normal del programa).

    Returns:
        Tupla (equipo_local, equipo_visitante, sede).
    """
    if len(sys.argv) in (3, 4):
        equipo_local, equipo_visitante = sys.argv[1], sys.argv[2]
        sede = sys.argv[3] if len(sys.argv) == 4 else "local"
        if sede not in predictor.SEDES_VALIDAS:
            print(f"[aviso] sede '{sede}' inválida, se usa 'local' por defecto.")
            sede = "local"
        return equipo_local, equipo_visitante, sede

    if len(sys.argv) != 1:
        print(
            "[aviso] Cantidad de argumentos inválida "
            f"({len(sys.argv) - 1}). Se esperaban 0, 2 o 3:\n"
            '  python main.py\n'
            '  python main.py "Equipo Local" "Equipo Visitante"\n'
            '  python main.py "Equipo Local" "Equipo Visitante" neutral\n'
            "Pasando a modo interactivo.\n"
        )

    print("=" * 55)
    print("  PREDICTOR DE RESULTADOS DE FÚTBOL")
    print("=" * 55)
    print("(Escribí los nombres en inglés: Argentina, England, Spain, ")
    print(" DR Congo, Zambia, etc. -- mismo idioma que usa la API)\n")
    equipo_local = pedir_nombre_equipo("Rival 1")
    equipo_visitante = pedir_nombre_equipo("Rival 2")
    sede = pedir_sede(equipo_local, equipo_visitante)
    return equipo_local, equipo_visitante, sede


def main() -> None:
    """Pide el partido (interactivo o por argumentos), predice y muestra."""
    equipo_local, equipo_visitante, sede = obtener_equipos_y_sede()

    try:
        prediccion = predictor.predecir_partido(equipo_local, equipo_visitante, sede=sede)
    except ValueError as error:
        print(f"\n[error] No se pudo generar la predicción: {error}")
        print(
            "Revisá que el nombre de la selección esté bien escrito. "
            "Si no tenés API_FOOTBALL_KEY configurada, el equipo debe "
            "existir en data/ejemplo_selecciones.json."
        )
        return

    mostrar_resumen(prediccion)

    visualizer.graficar_ficha_resumen(prediccion, RUTA_FICHA)
    visualizer.graficar_matriz_resultados(prediccion, RUTA_MATRIZ)
    visualizer.graficar_distribucion_resultado(prediccion, RUTA_DISTRIBUCION)
    print(f"\nGráficos guardados en {RUTA_FICHA}, {RUTA_MATRIZ} y {RUTA_DISTRIBUCION}")

    abrir_imagen(RUTA_FICHA)
    abrir_imagen(RUTA_MATRIZ)
    abrir_imagen(RUTA_DISTRIBUCION)


if __name__ == "__main__":
    main()
