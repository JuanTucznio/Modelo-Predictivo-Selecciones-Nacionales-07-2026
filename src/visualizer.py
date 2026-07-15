"""
visualizer.py
=============

Genera los gráficos de la predicción con estilo de "tarjetas" sobre
fondo oscuro: matriz de resultados exactos, barra de distribución de
probabilidades y una ficha de estadísticas (xG, Elo, ancla dinámica).

Se usa matplotlib puro (sin seaborn) para tener control total sobre
colores y tipografía, y así lograr una estética consistente con la
identidad visual del proyecto (definida en config.py).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

import config

plt.rcParams["font.family"] = "DejaVu Sans"


def _aplicar_fondo_oscuro(fig, ax) -> None:
    """Aplica el estilo de fondo oscuro consistente a una figura."""
    fig.patch.set_facecolor(config.COLOR_FONDO)
    ax.set_facecolor(config.COLOR_FONDO)
    for spine in ax.spines.values():
        spine.set_visible(False)


def _dibujar_tarjeta(ax, x: float, y: float, ancho: float, alto: float, color: str) -> None:
    """Dibuja un rectángulo redondeado tipo "tarjeta" en las coordenadas dadas.

    Función auxiliar reutilizada por los 3 gráficos del módulo, para
    lograr el mismo look de "card" en todos lados sin repetir código
    (Zen: "Simple is better than complex" -- una sola función para el
    patrón visual que más se repite).

    Args:
        ax: ejes de matplotlib donde dibujar.
        x, y: esquina inferior izquierda de la tarjeta.
        ancho, alto: dimensiones de la tarjeta.
        color: color de fondo de la tarjeta.
    """
    tarjeta = FancyBboxPatch(
        (x, y), ancho, alto,
        boxstyle="round,pad=0,rounding_size=0.09",
        linewidth=0, facecolor=color,
    )
    ax.add_patch(tarjeta)


def graficar_matriz_resultados(prediccion: dict, ruta_salida: str) -> None:
    """Dibuja la matriz de probabilidad de cada marcador exacto.

    Cada celda es una tarjeta redondeada individual (no una grilla de
    imagen plana), coloreada según su probabilidad. La celda más
    probable se resalta con un borde blanco grueso.

    Args:
        prediccion: diccionario devuelto por ``predictor.predecir_partido``.
        ruta_salida: ruta del archivo de imagen a generar (ej: "salida.png").
    """
    matriz = np.array(prediccion["matriz"])
    n = matriz.shape[0]
    indice_max = np.unravel_index(np.argmax(matriz), matriz.shape)
    cmap = LinearSegmentedColormap.from_list("calor_partido", config.ESCALA_CALOR)

    tam_celda = 1.0
    margen = 0.12
    fig, ax = plt.subplots(figsize=(n * 1.15 + 1.6, n * 1.15 + 1.5))
    _aplicar_fondo_oscuro(fig, ax)

    for i in range(n):        # i = goles del local (fila)
        for j in range(n):    # j = goles del visitante (columna)
            valor = matriz[i, j]
            intensidad = valor / matriz.max() if matriz.max() > 0 else 0
            color_celda = cmap(0.15 + intensidad * 0.85)

            # y invertido: la fila 0 (menos goles) va arriba, como en
            # una tabla normal de lectura.
            x = j * tam_celda
            y = (n - 1 - i) * tam_celda

            _dibujar_tarjeta(
                ax, x + margen / 2, y + margen / 2,
                tam_celda - margen, tam_celda - margen, color_celda,
            )

            if (i, j) == indice_max:
                borde = FancyBboxPatch(
                    (x + margen / 2, y + margen / 2),
                    tam_celda - margen, tam_celda - margen,
                    boxstyle="round,pad=0,rounding_size=0.09",
                    linewidth=3, edgecolor="white", facecolor="none",
                )
                ax.add_patch(borde)

            color_texto = config.COLOR_TEXTO if intensidad > 0.3 else config.COLOR_TEXTO_SECUNDARIO
            ax.text(
                x + tam_celda / 2, y + tam_celda / 2 + 0.13, f"{valor:.1f}%",
                ha="center", va="center", color=color_texto,
                fontsize=15, fontweight="bold",
            )
            ax.text(
                x + tam_celda / 2, y + tam_celda / 2 - 0.20, f"{i}-{j}",
                ha="center", va="center", color=config.COLOR_TEXTO_SECUNDARIO,
                fontsize=9.5,
            )

    ax.set_xlim(0, n * tam_celda)
    ax.set_ylim(0, n * tam_celda)
    ax.set_aspect("equal")
    ax.axis("off")

    for j in range(n):
        ax.text(j * tam_celda + tam_celda / 2, n * tam_celda + 0.35, str(j),
                ha="center", va="center", color=config.COLOR_TEXTO_SECUNDARIO,
                fontsize=12, fontweight="bold")
    for i in range(n):
        ax.text(-0.35, (n - 1 - i) * tam_celda + tam_celda / 2, str(i),
                ha="center", va="center", color=config.COLOR_TEXTO_SECUNDARIO,
                fontsize=12, fontweight="bold")

    ax.text(
        n * tam_celda / 2, n * tam_celda + 0.85,
        f"GOLES · {prediccion['equipo_visitante'].upper()}",
        ha="center", va="center", color=config.COLOR_VISITANTE,
        fontsize=13, fontweight="bold",
    )
    ax.text(
        -1.05, n * tam_celda / 2, f"GOLES · {prediccion['equipo_local'].upper()}",
        ha="center", va="center", color=config.COLOR_LOCAL,
        fontsize=13, fontweight="bold", rotation=90,
    )

    etiqueta_sede = {
        "local": f"{prediccion['equipo_local']} de local",
        "visitante": f"{prediccion['equipo_visitante']} de local",
        "neutral": "cancha neutral",
    }[prediccion["sede"]]
    pie = (
        f"xG: {prediccion['xg_local']} - {prediccion['xg_visitante']}"
        f"   ·   {etiqueta_sede}"
    )
    fig.text(0.52, 0.01, pie, ha="center", color=config.COLOR_TEXTO_SECUNDARIO, fontsize=10)

    plt.tight_layout(rect=(0.03, 0.03, 1, 1))
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(ruta_salida, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def graficar_distribucion_resultado(prediccion: dict, ruta_salida: str) -> None:
    """Dibuja la barra horizontal de distribución Victoria/Empate/Derrota.

    Args:
        prediccion: diccionario devuelto por ``predictor.predecir_partido``.
        ruta_salida: ruta del archivo de imagen a generar.
    """
    probs = prediccion["probabilidades"]
    etiquetas = [
        f"GANA {prediccion['equipo_local'].upper()}",
        "EMPATE",
        f"GANA {prediccion['equipo_visitante'].upper()}",
    ]
    valores = [probs["local"], probs["empate"], probs["visitante"]]
    colores = [config.COLOR_LOCAL, config.COLOR_EMPATE, config.COLOR_VISITANTE]

    fig, ax = plt.subplots(figsize=(9.5, 3.1))
    _aplicar_fondo_oscuro(fig, ax)

    ax.text(0, 1.05, "DISTRIBUCIÓN DE RESULTADO", color=config.COLOR_TEXTO_SECUNDARIO,
            fontsize=12, fontweight="bold", ha="left")

    izquierda = 0
    espaciado = 0.6
    for valor, color in zip(valores, colores):
        ancho = max(valor - espaciado, 0.5)
        _dibujar_tarjeta(ax, izquierda, 0, ancho, 0.62, color)
        if valor > 6:
            ax.text(izquierda + ancho / 2, 0.31, f"{valor:.1f}%", ha="center", va="center",
                    color="#0b1018", fontsize=20, fontweight="bold")
        izquierda += valor

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, 1.25)
    ax.axis("off")

    ax.text(0, -0.35, etiquetas[0], color=colores[0], fontsize=12, fontweight="bold", ha="left")
    ax.text(50, -0.35, etiquetas[1], color=colores[1], fontsize=12, fontweight="bold", ha="center")
    ax.text(100, -0.35, etiquetas[2], color=colores[2], fontsize=12, fontweight="bold", ha="right")

    plt.tight_layout()
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(ruta_salida, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)


def graficar_ficha_resumen(prediccion: dict, ruta_salida: str) -> None:
    """Dibuja una ficha de estadísticas: xG de cada equipo + trazado del modelo.

    Muestra, en tarjetas separadas, el xG final de cada equipo y las
    métricas de transparencia del modelo (xG natural vs. anclado,
    expectativa de Elo) -- para poder explicar "por qué" el modelo
    llegó a este número, no solo mostrar el resultado.

    Args:
        prediccion: diccionario devuelto por ``predictor.predecir_partido``.
        ruta_salida: ruta del archivo de imagen a generar.
    """
    trazado = prediccion["trazado"]

    fig, ax = plt.subplots(figsize=(9, 5.6))
    _aplicar_fondo_oscuro(fig, ax)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.text(0.1, 9.6, "EXPECTED GOALS (xG)", color=config.COLOR_TEXTO_SECUNDARIO,
            fontsize=12, fontweight="bold", ha="left")

    # --- Tarjetas de xG por equipo (izq: local, der: visitante) ---
    _dibujar_tarjeta(ax, 0.1, 6.4, 4.6, 2.7, config.COLOR_FONDO_TARJETA)
    _dibujar_tarjeta(ax, 5.3, 6.4, 4.6, 2.7, config.COLOR_FONDO_TARJETA)
    ax.add_patch(FancyBboxPatch(
        (0.1, 6.4), 0.12, 2.7, boxstyle="square,pad=0",
        linewidth=0, facecolor=config.COLOR_LOCAL,
    ))
    ax.add_patch(FancyBboxPatch(
        (5.3, 6.4), 0.12, 2.7, boxstyle="square,pad=0",
        linewidth=0, facecolor=config.COLOR_VISITANTE,
    ))

    ax.text(0.55, 8.55, prediccion["equipo_local"].upper(), color=config.COLOR_TEXTO_SECUNDARIO,
            fontsize=11, fontweight="bold", ha="left")
    ax.text(0.55, 7.4, f"{prediccion['xg_local']}", color=config.COLOR_LOCAL,
            fontsize=38, fontweight="bold", ha="left")

    ax.text(5.75, 8.55, prediccion["equipo_visitante"].upper(), color=config.COLOR_TEXTO_SECUNDARIO,
            fontsize=11, fontweight="bold", ha="left")
    ax.text(5.75, 7.4, f"{prediccion['xg_visitante']}", color=config.COLOR_VISITANTE,
            fontsize=38, fontweight="bold", ha="left")

    # --- Tarjeta de "trazado del modelo" (transparencia) ---
    ax.text(0.1, 5.75, "TRAZADO DEL MODELO", color=config.COLOR_TEXTO_SECUNDARIO,
            fontsize=12, fontweight="bold", ha="left")
    _dibujar_tarjeta(ax, 0.1, 0.1, 9.8, 5.35, config.COLOR_FONDO_TARJETA)

    celdas = [
        ("ELO APROX. · " + prediccion["equipo_local"][:12].upper(),
         f"{trazado['elo_local']}", 0.6, 4.0),
        ("EXPECTATIVA ELO (LOCAL)", f"{trazado['elo_expectativa_local']}%", 5.3, 4.0),
        ("xG NATURAL (SIN AJUSTAR)", f"{trazado['xg_natural_total']}", 0.6, 1.9),
        ("xG ANCLADO (TOTAL FINAL)", f"{trazado['xg_anclado_total']}", 5.3, 1.9),
    ]
    for etiqueta, valor, x, y in celdas:
        ax.text(x, y + 0.75, etiqueta, color=config.COLOR_TEXTO_SECUNDARIO,
                fontsize=9.5, fontweight="bold", ha="left")
        ax.text(x, y, valor, color=config.COLOR_TEXTO, fontsize=26, fontweight="bold", ha="left")

    plt.tight_layout()
    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(ruta_salida, dpi=180, facecolor=fig.get_facecolor())
    plt.close(fig)
