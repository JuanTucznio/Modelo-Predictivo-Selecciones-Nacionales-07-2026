"""
test_model.py
=============

Pruebas unitarias del núcleo matemático (src/model.py).

No son exhaustivas: cubren los casos más importantes para demostrar
que el modelo se comporta como se espera y que los casos límite
(lista vacía, decaimiento a cero) están controlados.
"""

from datetime import datetime

import pytest

import config
from src import model


def test_decaimiento_temporal_partido_de_hoy_es_maximo():
    """Un partido jugado hoy debe tener peso 1.0 (sin decaimiento)."""
    hoy = datetime.now()
    fecha_hoy = hoy.strftime("%Y-%m-%d")
    peso = model.decaimiento_temporal(fecha_hoy, hoy)
    assert peso == pytest.approx(1.0, abs=0.01)


def test_decaimiento_temporal_decrece_con_el_tiempo():
    """A mayor antigüedad, menor debe ser el peso del partido."""
    hoy = datetime.now()
    peso_reciente = model.decaimiento_temporal("2026-06-01", hoy)
    peso_viejo = model.decaimiento_temporal("2020-01-01", hoy)
    assert peso_reciente > peso_viejo


def test_calcular_fuerza_sin_partidos_lanza_error():
    """Sin datos históricos, no se puede estimar una fuerza: debe fallar
    explícitamente en vez de devolver un valor arbitrario."""
    with pytest.raises(ValueError):
        model.calcular_fuerza([])


def test_calcular_fuerza_promedio_simple():
    """Con partidos sin decaimiento relevante (todos de hoy), la fuerza
    debe acercarse al promedio simple de goles."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos = [
        {"fecha": hoy, "goles_favor": 2, "goles_contra": 1, "local": True, "rival": "Chile"},
        {"fecha": hoy, "goles_favor": 4, "goles_contra": 1, "local": False, "rival": "Perú"},
    ]
    ataque, defensa = model.calcular_fuerza(partidos)
    assert ataque == pytest.approx(3.0, abs=0.05)
    assert defensa == pytest.approx(1.0, abs=0.05)


def test_promedio_goles_entorno_detecta_torneo_ofensivo():
    """Si ambos equipos vienen de partidos con muchos goles, el ancla
    dinámica debe ser alta (torneo "abierto"), no un número fijo."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos_muchos_goles = [
        {"fecha": hoy, "goles_favor": 4, "goles_contra": 3, "local": True, "rival": "X"},
        {"fecha": hoy, "goles_favor": 3, "goles_contra": 3, "local": False, "rival": "Y"},
    ]
    ancla = model.promedio_goles_entorno(partidos_muchos_goles, partidos_muchos_goles)
    assert ancla > 5.0  # 4+3, 3+3, x2 -> promedio de goles totales alto


def test_promedio_goles_entorno_detecta_torneo_cerrado():
    """Si ambos equipos vienen de partidos con pocos goles, el ancla
    dinámica debe ser baja (torneo "cerrado"/táctico)."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos_pocos_goles = [
        {"fecha": hoy, "goles_favor": 0, "goles_contra": 1, "local": True, "rival": "X"},
        {"fecha": hoy, "goles_favor": 1, "goles_contra": 0, "local": False, "rival": "Y"},
    ]
    ancla = model.promedio_goles_entorno(partidos_pocos_goles, partidos_pocos_goles)
    assert ancla < 2.0


def test_promedio_goles_entorno_sin_partidos_usa_respaldo():
    """Sin ningún partido disponible, debe caer al valor fijo de
    config.py en vez de romper con una división por cero."""
    ancla = model.promedio_goles_entorno([], [])
    assert ancla == config.PROMEDIO_GOLES_TORNEO


def test_calcular_ajuste_h2h_sin_historial_da_cero():
    """Si el equipo nunca jugó contra este rival puntual, el ajuste debe
    ser 0.0: la ausencia de datos no debe beneficiar ni perjudicar."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos = [
        {"fecha": hoy, "goles_favor": 2, "goles_contra": 0, "local": True, "rival": "Chile"},
    ]
    ajuste = model.calcular_ajuste_h2h(partidos, "Uruguay")
    assert ajuste == 0.0


def test_calcular_ajuste_h2h_historial_dominante_es_positivo():
    """Un historial de goleadas contra este rival específico debe dar
    un ajuste positivo (empuja el xG hacia arriba)."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos = [
        {"fecha": hoy, "goles_favor": 4, "goles_contra": 0, "local": True, "rival": "Bolivia"},
        {"fecha": hoy, "goles_favor": 3, "goles_contra": 1, "local": False, "rival": "Bolivia"},
    ]
    ajuste = model.calcular_ajuste_h2h(partidos, "Bolivia")
    assert ajuste > 0


def test_calcular_ajuste_h2h_respeta_el_tope_maximo():
    """Un historial extremo (goleadas puntuales) no debe mover el xG
    más allá de config.MAX_AJUSTE_H2H, en ninguna dirección."""
    hoy = datetime.now().strftime("%Y-%m-%d")
    partidos = [
        {"fecha": hoy, "goles_favor": 9, "goles_contra": 0, "local": True, "rival": "San Marino"},
    ]
    ajuste = model.calcular_ajuste_h2h(partidos, "San Marino")
    assert ajuste == pytest.approx(config.MAX_AJUSTE_H2H, abs=0.001)


def test_marcadores_bajos_pesan_mas_que_marcadores_altos():
    """Un marcador bajo y balanceado (1-1) debe ser más probable que uno
    alto e inusual (5-4), incluso con equipos parejos y ofensivos.
    Esto es una propiedad esperada del Poisson (y no algo que haya que
    forzar a mano): la probabilidad decae a medida que el resultado se
    aleja del promedio esperado de goles."""
    matriz = model.matriz_resultados(xg_local=2.2, xg_visitante=2.0, max_goles=8)
    prob_1_1 = matriz[1][1]
    prob_5_4 = matriz[5][4]
    assert prob_1_1 > prob_5_4


def test_expectativa_elo_equipos_parejos_da_mitad():
    """Con el mismo Elo, la expectativa de victoria debe ser 50%."""
    expectativa = model.expectativa_elo(1800, 1800)
    assert expectativa == pytest.approx(0.5, abs=0.001)


def test_expectativa_elo_favorece_al_de_mayor_elo():
    """Un Elo mayor debe traducirse en una expectativa de victoria
    mayor a 50%, y a la inversa para el rival."""
    expectativa_favorito = model.expectativa_elo(2000, 1500)
    expectativa_no_favorito = model.expectativa_elo(1500, 2000)
    assert expectativa_favorito > 0.5
    assert expectativa_no_favorito < 0.5
    assert expectativa_favorito + expectativa_no_favorito == pytest.approx(1.0, abs=0.001)


def test_ajustar_por_ranking_no_comprime_diferencias_extremas():
    """Reproduce el caso que motivó este cambio: un equipo top 1 contra
    uno top 85 debe terminar con una fuerza claramente mayor que el
    rival, no casi empatada (lo que pasaba con la fórmula anterior)."""
    fuerza_favorito = model.ajustar_por_ranking(2.0, ranking_propio=1, ranking_rival=85)
    fuerza_no_favorito = model.ajustar_por_ranking(2.0, ranking_propio=85, ranking_rival=1)
    assert fuerza_favorito > fuerza_no_favorito * 1.3


def test_dixon_coles_aumenta_probabilidad_de_empates_bajos():
    rho = -0.10
    factor_0_0 = model._factor_dixon_coles(0, 0, 1.5, 1.2, rho)
    factor_1_1 = model._factor_dixon_coles(1, 1, 1.5, 1.2, rho)
    factor_1_0 = model._factor_dixon_coles(1, 0, 1.5, 1.2, rho)
    factor_0_1 = model._factor_dixon_coles(0, 1, 1.5, 1.2, rho)

    assert factor_0_0 > 1.0
    assert factor_1_1 > 1.0
    assert factor_1_0 < 1.0
    assert factor_0_1 < 1.0


def test_dixon_coles_no_afecta_marcadores_altos():
    """Fuera de las 4 celdas especiales, el factor debe ser exactamente
    1.0 (sin ningún efecto sobre el Poisson simple)."""
    factor = model._factor_dixon_coles(3, 2, 1.5, 1.2, rho=-0.10)
    assert factor == 1.0


def test_matriz_resultados_suma_cercana_a_cien():
    """La suma de todas las probabilidades de la matriz debe rondar
    el 100%, ya que cubre (casi) todo el espacio de resultados posibles."""
    matriz = model.matriz_resultados(xg_local=1.5, xg_visitante=1.2, max_goles=8)
    total = sum(sum(fila) for fila in matriz)
    assert total == pytest.approx(100, abs=2)


def test_probabilidades_resultado_suman_cien():
    """Victoria + Empate + Derrota deben sumar (casi) 100%."""
    matriz = model.matriz_resultados(xg_local=1.8, xg_visitante=0.9)
    probs = model.probabilidades_resultado(matriz)
    total = probs["local"] + probs["empate"] + probs["visitante"]
    assert total == pytest.approx(100, abs=1)


def test_top_resultados_exactos_devuelve_ordenado():
    """El resultado con mayor probabilidad debe ser el primero de la lista."""
    matriz = model.matriz_resultados(xg_local=2.0, xg_visitante=0.8)
    top = model.top_resultados_exactos(matriz, top_n=3)
    probabilidades = [r["probabilidad"] for r in top]
    assert probabilidades == sorted(probabilidades, reverse=True)


def test_mejor_marcador_por_categoria_respeta_su_propia_zona():
    """El marcador devuelto para 'local' debe ser efectivamente una
    victoria local (goles_local > goles_visitante), y análogamente
    para las otras dos categorías -- no puede devolver un marcador de
    otra categoría por error de clasificación."""
    matriz = model.matriz_resultados(xg_local=2.0, xg_visitante=0.8, max_goles=6)
    mejores = model.mejor_marcador_por_categoria(matriz)

    goles_local, goles_visitante = map(int, mejores["local"]["marcador"].split("-"))
    assert goles_local > goles_visitante

    goles_local, goles_visitante = map(int, mejores["empate"]["marcador"].split("-"))
    assert goles_local == goles_visitante

    goles_local, goles_visitante = map(int, mejores["visitante"]["marcador"].split("-"))
    assert goles_local < goles_visitante


def test_mejor_marcador_por_categoria_puede_diferir_del_top_general():
    """Reproduce el caso que motivó esta función: con equipos parejos,
    el marcador más probable EN GENERAL puede ser un empate (1-1),
    aunque 'local' sea la categoría agregada más probable. Esto no es
    una contradicción: son dos preguntas distintas."""
    matriz = model.matriz_resultados(xg_local=1.6, xg_visitante=1.1, max_goles=6)
    top_general = model.top_resultados_exactos(matriz, top_n=1)[0]
    mejores = model.mejor_marcador_por_categoria(matriz)

    # El marcador más probable en general puede coincidir con el mejor
    # de alguna categoría, o no -- lo que se verifica acá es que la
    # función de categorías siempre devuelve algo internamente
    # consistente, sea cual sea el caso.
    assert top_general["marcador"] in (
        mejores["local"]["marcador"],
        mejores["empate"]["marcador"],
        mejores["visitante"]["marcador"],
    )
