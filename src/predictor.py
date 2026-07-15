"""
predictor.py
============

Orquesta ``data_fetcher`` (obtención de datos) y ``model`` (matemática)
para producir una predicción completa y lista para mostrar o graficar.

Separar esta capa de "orquestación" del resto permite que, si mañana
cambiamos de fuente de datos o de fórmula matemática, esta función
principal (``predecir_partido``) no tenga que modificarse.
"""

from __future__ import annotations

from src import data_fetcher, model

SEDES_VALIDAS = ("local", "visitante", "neutral")


def predecir_partido(
    equipo_local: str,
    equipo_visitante: str,
    sede: str = "local",
) -> dict:
    """Genera la predicción completa de un partido entre dos selecciones.

    Args:
        equipo_local: nombre de la primera selección.
        equipo_visitante: nombre de la segunda selección.
        sede: quién tiene ventaja de localía. Uno de:
            - "local": ``equipo_local`` juega en su país (por defecto).
            - "visitante": ``equipo_visitante`` juega en su país.
            - "neutral": cancha neutral, sin ventaja para ninguno
              (el caso típico de un Mundial, salvo el país anfitrión).

    Returns:
        Diccionario con toda la información de la predicción:
        equipos, xG de cada uno, ranking, probabilidades de
        victoria/empate/derrota, matriz completa y top de marcadores
        exactos.

    Raises:
        ValueError: si ``sede`` no es uno de los 3 valores válidos.
    """
    if sede not in SEDES_VALIDAS:
        raise ValueError(f"sede debe ser uno de {SEDES_VALIDAS}, recibido: {sede!r}")

    datos_local = data_fetcher.obtener_datos_equipo(equipo_local)
    datos_visitante = data_fetcher.obtener_datos_equipo(equipo_visitante)
    historial_local = datos_local["partidos"]
    historial_visitante = datos_visitante["partidos"]

    ataque_local, defensa_local = model.calcular_fuerza(historial_local)
    ataque_visitante, defensa_visitante = model.calcular_fuerza(historial_visitante)

    # Ancla dinámica: se auto-calcula a partir de los partidos reales de
    # AMBOS equipos, en vez de un número de torneo fijo. Si vienen de un
    # contexto de muchos goles, el ancla sube sola; si vienen de un
    # contexto cerrado, baja sola (ver model.promedio_goles_entorno).
    promedio_entorno = model.promedio_goles_entorno(historial_local, historial_visitante)

    # Ajuste por historial de enfrentamientos directos entre estos DOS
    # equipos puntuales (head-to-head), no contra rivales en general.
    ajuste_h2h_local = model.calcular_ajuste_h2h(historial_local, equipo_visitante)
    ajuste_h2h_visitante = model.calcular_ajuste_h2h(historial_visitante, equipo_local)

    # La localía es tri-estado: solo uno de los dos (o ninguno) recibe
    # el factor de ventaja de local, según el parámetro `sede`.
    local_tiene_ventaja = sede == "local"
    visitante_tiene_ventaja = sede == "visitante"

    xg_local = model.calcular_xg(
        ataque_local=ataque_local,
        defensa_visitante=defensa_visitante,
        ranking_local=datos_local["ranking_fifa"],
        ranking_visitante=datos_visitante["ranking_fifa"],
        es_local=local_tiene_ventaja,
        promedio_torneo=promedio_entorno,
        ajuste_h2h=ajuste_h2h_local,
    )
    xg_visitante = model.calcular_xg(
        ataque_local=ataque_visitante,
        defensa_visitante=defensa_local,
        ranking_local=datos_visitante["ranking_fifa"],
        ranking_visitante=datos_local["ranking_fifa"],
        es_local=visitante_tiene_ventaja,
        promedio_torneo=promedio_entorno,
        ajuste_h2h=ajuste_h2h_visitante,
    )

    # --- Métricas de transparencia (para mostrar "por qué" el modelo
    # llegó a este número, no solo el resultado final) ---
    xg_natural_local = (ataque_local + defensa_visitante) / 2
    xg_natural_visitante = (ataque_visitante + defensa_local) / 2
    elo_local = model.ranking_a_elo_aproximado(datos_local["ranking_fifa"])
    elo_visitante = model.ranking_a_elo_aproximado(datos_visitante["ranking_fifa"])
    elo_expectativa_local = model.expectativa_elo(elo_local, elo_visitante)

    matriz = model.matriz_resultados(xg_local, xg_visitante)
    probabilidades = model.probabilidades_resultado(matriz)
    top_marcadores = model.top_resultados_exactos(matriz, top_n=5)
    mejor_por_categoria = model.mejor_marcador_por_categoria(matriz)

    return {
        "equipo_local": equipo_local,
        "equipo_visitante": equipo_visitante,
        "sede": sede,
        "xg_local": xg_local,
        "xg_visitante": xg_visitante,
        "ranking_local": datos_local["ranking_fifa"],
        "ranking_visitante": datos_visitante["ranking_fifa"],
        "promedio_goles_entorno": round(promedio_entorno, 2),
        "probabilidades": probabilidades,
        "matriz": matriz,
        "top_marcadores": top_marcadores,
        "mejor_por_categoria": mejor_por_categoria,
        "trazado": {
            "xg_natural_total": round(xg_natural_local + xg_natural_visitante, 2),
            "xg_anclado_total": round(xg_local + xg_visitante, 2),
            "elo_local": round(elo_local),
            "elo_visitante": round(elo_visitante),
            "elo_expectativa_local": round(elo_expectativa_local * 100, 1),
        },
    }
