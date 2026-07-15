"""
model.py
========

Núcleo matemático del predictor. Este módulo NO sabe nada de APIs,
archivos ni JSON: solo recibe números y listas de partidos, y devuelve
probabilidades. Mantenerlo "puro" (sin efectos secundarios) lo hace
fácil de testear y de entender de forma aislada.

Enfoque del modelo
-------------------
1. Se calcula la fuerza de ataque y de defensa de cada equipo a partir
   de sus últimos partidos, aplicando un decaimiento temporal
   (los partidos recientes pesan más que los viejos).
2. Esa fuerza se ajusta por el ranking FIFA del rival (ganarle a un
   equipo top 10 vale más que ganarle a un top 100).
3. Se combina con un "ancla" (el promedio de goles del torneo) para
   evitar que una racha puntual distorsione la predicción.
4. Con el xG final de cada equipo, se usa la distribución de Poisson
   para calcular la probabilidad de cada marcador exacto posible.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import TypedDict

from scipy.stats import poisson

import config


class Partido(TypedDict):
    """Estructura de un partido histórico usado como insumo del modelo."""
    fecha: str          # formato ISO: "2026-03-15"
    goles_favor: int
    goles_contra: int
    local: bool          # True si el equipo jugó de local ese partido
    rival: str           # nombre del equipo rival en ese partido puntual


# -------------------------------------------------------------------
# 1. DECAIMIENTO TEMPORAL
# -------------------------------------------------------------------

def decaimiento_temporal(fecha_partido: str, fecha_referencia: datetime) -> float:
    """Calcula el peso de un partido según su antigüedad.

    Usa un decaimiento exponencial: cuanto más viejo es el partido,
    menor es su peso en el promedio. Un partido de hoy pesa 1.0;
    uno jugado hace ``VIDA_MEDIA_DECAIMIENTO`` días pesa ~0.5.

    Args:
        fecha_partido: fecha del partido en formato "AAAA-MM-DD".
        fecha_referencia: fecha desde la cual se cuenta la antigüedad
            (normalmente, hoy).

    Returns:
        Un peso entre 0 y 1 (1 = partido muy reciente).
    """
    fecha = datetime.strptime(fecha_partido, "%Y-%m-%d")
    dias_transcurridos = (fecha_referencia - fecha).days
    dias_transcurridos = max(dias_transcurridos, 0)

    return math.exp(-dias_transcurridos / config.VIDA_MEDIA_DECAIMIENTO)


# -------------------------------------------------------------------
# 2. FUERZA DE ATAQUE Y DEFENSA
# -------------------------------------------------------------------

def calcular_fuerza(
    partidos: list[Partido],
    fecha_referencia: datetime | None = None,
) -> tuple[float, float]:
    """Calcula la fuerza de ataque y defensa de un equipo.

    La "fuerza de ataque" es el promedio ponderado de goles a favor;
    la "fuerza de defensa" es el promedio ponderado de goles en contra
    (acá un número BAJO es una defensa fuerte).

    Args:
        partidos: lista de partidos recientes del equipo.
        fecha_referencia: fecha desde la que se calcula el decaimiento.
            Si no se pasa, se usa la fecha actual.

    Returns:
        Tupla (fuerza_ataque, fuerza_defensa).

    Raises:
        ValueError: si la lista de partidos está vacía, porque no hay
            forma de estimar una fuerza sin datos.
    """
    if not partidos:
        raise ValueError("No se puede calcular la fuerza sin partidos históricos.")

    fecha_referencia = fecha_referencia or datetime.now()

    suma_pesos = 0.0
    suma_goles_favor = 0.0
    suma_goles_contra = 0.0

    for partido in partidos:
        peso = decaimiento_temporal(partido["fecha"], fecha_referencia)
        suma_pesos += peso
        suma_goles_favor += partido["goles_favor"] * peso
        suma_goles_contra += partido["goles_contra"] * peso

    fuerza_ataque = suma_goles_favor / suma_pesos
    fuerza_defensa = suma_goles_contra / suma_pesos

    return fuerza_ataque, fuerza_defensa


# -------------------------------------------------------------------
# 2B. ANCLA DINÁMICA DE GOLES (detecta si el contexto es de muchos o
#     pocos goles, en vez de asumir un promedio fijo para siempre)
# -------------------------------------------------------------------

def promedio_goles_entorno(
    partidos_local: list[Partido],
    partidos_visitante: list[Partido],
) -> float:
    """Calcula el promedio de goles totales por partido de ambos equipos.

    Reemplaza al número fijo ``config.PROMEDIO_GOLES_TORNEO`` por un
    valor calculado en base a los partidos recientes reales de los dos
    equipos que se están enfrentando. Esto resuelve el problema de que
    un mismo número fijo no sirve igual para un Mundial con muchos
    goles que para uno de partidos cerrados y tácticos: si ambos
    equipos vienen de un promedio alto de goles (torneo "abierto"), el
    ancla sube sola; si vienen de partidos con pocos goles (torneo
    "cerrado"), el ancla baja sola.

    Args:
        partidos_local: partidos recientes del equipo local.
        partidos_visitante: partidos recientes del equipo visitante.

    Returns:
        Promedio de goles totales (de ambos equipos sumados) por
        partido. Si no hay partidos de ninguno de los dos, devuelve el
        valor fijo de ``config.PROMEDIO_GOLES_TORNEO`` como respaldo.
    """
    todos_los_partidos = partidos_local + partidos_visitante
    if not todos_los_partidos:
        return config.PROMEDIO_GOLES_TORNEO

    goles_totales = sum(p["goles_favor"] + p["goles_contra"] for p in todos_los_partidos)
    return goles_totales / len(todos_los_partidos)


# -------------------------------------------------------------------
# 2C. AJUSTE POR ENFRENTAMIENTOS HISTÓRICOS (head-to-head)
# -------------------------------------------------------------------

def calcular_ajuste_h2h(
    partidos_equipo: list[Partido],
    nombre_rival: str,
    fecha_referencia: datetime | None = None,
) -> float:
    """Calcula un ajuste de xG en base al historial contra este rival puntual.

    Filtra, de todo el historial de un equipo, únicamente los partidos
    jugados contra ``nombre_rival``, y calcula la diferencia de goles
    promedio (ponderada por decaimiento temporal, igual que en
    ``calcular_fuerza``) en esos enfrentamientos puntuales. Un historial
    dominante contra ese rival específico empuja el xG levemente hacia
    arriba; un historial adverso lo empuja levemente hacia abajo.

    Args:
        partidos_equipo: historial completo del equipo (todos los rivales).
        nombre_rival: nombre del rival contra el que se juega ahora.
        fecha_referencia: fecha desde la que se calcula el decaimiento.

    Returns:
        Ajuste (puede ser negativo) a sumar al xG base. Si no hay
        antecedentes contra ese rival, devuelve 0.0 (sin ajuste): la
        ausencia de historial no debe ni beneficiar ni perjudicar.
    """
    fecha_referencia = fecha_referencia or datetime.now()

    enfrentamientos = [p for p in partidos_equipo if p.get("rival") == nombre_rival]
    if not enfrentamientos:
        return 0.0

    suma_pesos = 0.0
    suma_diferencia = 0.0
    for partido in enfrentamientos:
        peso = decaimiento_temporal(partido["fecha"], fecha_referencia)
        diferencia = partido["goles_favor"] - partido["goles_contra"]
        suma_diferencia += diferencia * peso
        suma_pesos += peso

    diferencia_promedio = suma_diferencia / suma_pesos
    ajuste = diferencia_promedio * config.PESO_H2H

    # Acotamos el ajuste para que un historial extremo (ej. 5-0 una
    # sola vez) no distorsione el xG más de lo razonable.
    return max(-config.MAX_AJUSTE_H2H, min(config.MAX_AJUSTE_H2H, ajuste))


# -------------------------------------------------------------------
# 3. AJUSTE POR RANKING FIFA (vía Elo aproximado)
# -------------------------------------------------------------------

def ranking_a_elo_aproximado(ranking: int) -> float:
    """Convierte una posición de ranking FIFA a un Elo aproximado.

    IMPORTANTE (honestidad para la defensa): esto NO es un sistema Elo
    real -- un Elo de verdad se actualiza partido a partido con la
    fórmula de actualización estándar (ganar/perder/empatar contra un
    rival de tal fuerza suma o resta puntos). Nosotros no tenemos ese
    historial cruzado entre TODOS los equipos para reconstruirlo bien.

    Lo que hacemos acá es una aproximación monótona y documentada:
    transformamos la posición de ranking en un número en una escala
    tipo Elo (más alto = mejor equipo), usando una escala logarítmica
    para que la diferencia entre el puesto 1 y el puesto 10 pese mucho
    más que entre el puesto 100 y el 110 -- así se refleja mejor que en
    la elite las diferencias de nivel son grandes, y en la mitad de
    tabla para abajo se empiezan a achicar.

    Args:
        ranking: posición en el ranking FIFA (1 = mejor).

    Returns:
        Un número en una escala aproximada tipo Elo (rango ~1200-2000).
    """
    ranking = max(ranking, 1)
    return max(1200.0, 2150 - 480 * math.log10(ranking + 1))


def expectativa_elo(elo_propio: float, elo_rival: float) -> float:
    """Fórmula estándar de expectativa de victoria de un sistema Elo.

    Esta es LA fórmula de Elo real (la misma que usa ajedrez, la misma
    que usa el ranking Elo no oficial de selecciones eloratings.net):
    la probabilidad esperada de ganar es una función logística de la
    diferencia de puntaje Elo entre los dos rivales.

    Args:
        elo_propio: Elo (aproximado) del equipo evaluado.
        elo_rival: Elo (aproximado) del rival.

    Returns:
        Un valor entre 0 y 1: la expectativa de victoria del equipo
        evaluado, según su diferencia de Elo contra el rival.
    """
    return 1 / (1 + 10 ** ((elo_rival - elo_propio) / 400))


def ajustar_por_ranking(fuerza: float, ranking_propio: int, ranking_rival: int) -> float:
    """Ajusta una fuerza de ataque según la expectativa de Elo.

    A diferencia de una resta lineal de posiciones de ranking, usar la
    fórmula de expectativa de Elo hace que la brecha entre un equipo
    top 5 y uno top 100 pese mucho más que la brecha entre dos equipos
    ambos fuera del top 100 -- que es como se comporta el nivel real
    del fútbol (las diferencias se agrandan en los extremos).

    Args:
        fuerza: fuerza de ataque original (goles esperados promedio).
        ranking_propio: posición del equipo en el ranking FIFA (1 = mejor).
        ranking_rival: posición del rival en el ranking FIFA.

    Returns:
        Fuerza de ataque ajustada.
    """
    elo_propio = ranking_a_elo_aproximado(ranking_propio)
    elo_rival = ranking_a_elo_aproximado(ranking_rival)
    expectativa = expectativa_elo(elo_propio, elo_rival)

    # expectativa va de 0 a 1 (0.5 = parejos). Lo centramos en 0 y lo
    # convertimos en un multiplicador alrededor de 1, escalado por
    # PESO_RANKING_FIFA para poder seguir calibrando su impacto desde
    # config.py sin tocar esta fórmula.
    multiplicador = 1 + (expectativa - 0.5) * config.PESO_RANKING_FIFA * 2

    # Evitamos que el ajuste sea desproporcionado en casos extremos.
    multiplicador = max(0.5, min(1.8, multiplicador))

    return fuerza * multiplicador


# -------------------------------------------------------------------
# 4. CÁLCULO FINAL DE xG POR PARTIDO
# -------------------------------------------------------------------

def calcular_xg(
    ataque_local: float,
    defensa_visitante: float,
    ranking_local: int,
    ranking_visitante: int,
    es_local: bool,
    promedio_torneo: float = config.PROMEDIO_GOLES_TORNEO,
    ajuste_h2h: float = 0.0,
) -> float:
    """Combina ataque propio, defensa rival, ranking, ancla y h2h.

    Fórmula base: el xG de un equipo es el promedio entre su propia
    fuerza de ataque y la debilidad defensiva del rival, ajustado por
    ranking FIFA, localía, el ancla de goles del entorno (dinámica,
    ver ``promedio_goles_entorno``) y el historial de enfrentamientos
    directos contra este rival puntual (ver ``calcular_ajuste_h2h``).

    Args:
        ataque_local: fuerza de ataque del equipo que se está evaluando.
        defensa_visitante: fuerza de defensa del rival.
        ranking_local: ranking FIFA del equipo evaluado.
        ranking_visitante: ranking FIFA del rival.
        es_local: True si el equipo evaluado juega de local (False
            también para partidos en cancha neutral).
        promedio_torneo: ancla de goles a utilizar. Por defecto usa el
            valor fijo de config.py, pero se recomienda pasar el valor
            calculado por ``promedio_goles_entorno`` para que el
            modelo se auto-calibre al contexto real (torneo con
            muchos o pocos goles).
        ajuste_h2h: corrección por historial contra este rival
            específico, calculada con ``calcular_ajuste_h2h``.

    Returns:
        xG estimado para ese equipo en el partido.
    """
    xg_base = (ataque_local + defensa_visitante) / 2
    xg_ajustado = ajustar_por_ranking(xg_base, ranking_local, ranking_visitante)

    if es_local:
        xg_ajustado *= config.FACTOR_LOCALIA

    # Anclamos parcialmente al promedio del entorno (dinámico) para no
    # sobreajustar a rachas de pocos partidos.
    xg_final = (
        xg_ajustado * (1 - config.PESO_ANCLA_TORNEO)
        + promedio_torneo / 2 * config.PESO_ANCLA_TORNEO
    )

    xg_final += ajuste_h2h

    return round(max(xg_final, 0.05), 3)


# -------------------------------------------------------------------
# 5. DISTRIBUCIÓN DE POISSON: MATRIZ DE RESULTADOS EXACTOS
# -------------------------------------------------------------------

def _factor_dixon_coles(
    goles_local: int,
    goles_visitante: int,
    xg_local: float,
    xg_visitante: float,
    rho: float,
) -> float:
    """Calcula el factor de corrección tau de Dixon-Coles (1997).

    El Poisson simple asume que los goles del local y del visitante son
    completamente independientes entre sí. En la práctica, esto lleva a
    subestimar sistemáticamente 4 marcadores puntuales de partidos con
    pocos goles (0-0, 1-0, 0-1, 1-1), porque la dinámica real de un
    partido muy cerrado no es igual a la de un partido con muchos goles.

    Dixon y Coles publicaron una corrección que se aplica ÚNICAMENTE a
    esas 4 celdas de la matriz; el resto de los marcadores queda igual
    que en el Poisson simple.

    Args:
        goles_local: goles del equipo local en esta celda de la matriz.
        goles_visitante: goles del equipo visitante en esta celda.
        xg_local: xG esperado del equipo local (lambda).
        xg_visitante: xG esperado del equipo visitante (mu).
        rho: parámetro de correlación (típicamente entre -0.05 y -0.20).

    Returns:
        Factor multiplicador a aplicar sobre la probabilidad de Poisson
        simple de esa celda. Vale 1.0 (sin cambios) para cualquier
        marcador que no sea uno de los 4 casos especiales.
    """
    if goles_local == 0 and goles_visitante == 0:
        return 1 - (xg_local * xg_visitante * rho)
    if goles_local == 0 and goles_visitante == 1:
        return 1 + (xg_local * rho)
    if goles_local == 1 and goles_visitante == 0:
        return 1 + (xg_visitante * rho)
    if goles_local == 1 and goles_visitante == 1:
        return 1 - rho
    return 1.0


def matriz_resultados(
    xg_local: float,
    xg_visitante: float,
    max_goles: int = config.MAX_GOLES,
    rho: float = config.RHO_DIXON_COLES,
) -> list[list[float]]:
    """Genera la matriz de probabilidad de cada marcador exacto.

    Se asume que los goles de cada equipo siguen una distribución de
    Poisson, con media igual al xG calculado, corregida con el factor
    de Dixon-Coles (ver ``_factor_dixon_coles``) para los marcadores
    de pocos goles, donde el Poisson simple se aleja más de la realidad.

    Args:
        xg_local: goles esperados del equipo local.
        xg_visitante: goles esperados del equipo visitante.
        max_goles: cantidad máxima de goles a evaluar por equipo.
        rho: parámetro de corrección de Dixon-Coles.

    Returns:
        Matriz de tamaño (max_goles+1) x (max_goles+1), donde la celda
        [i][j] es la probabilidad (en %) de que el resultado sea
        local=i, visitante=j.
    """
    matriz = []
    for goles_local in range(max_goles + 1):
        fila = []
        prob_local = float(poisson.pmf(goles_local, xg_local))
        for goles_visitante in range(max_goles + 1):
            prob_visitante = float(poisson.pmf(goles_visitante, xg_visitante))
            correccion = _factor_dixon_coles(
                goles_local, goles_visitante, xg_local, xg_visitante, rho,
            )
            probabilidad = prob_local * prob_visitante * correccion
            fila.append(round(probabilidad * 100, 2))
        matriz.append(fila)

    return matriz


def probabilidades_resultado(matriz: list[list[float]]) -> dict[str, float]:
    """Suma la matriz de resultados exactos en Victoria / Empate / Derrota.

    A diferencia de una versión anterior de esta función, ya NO aplica
    ningún ajuste manual sobre el empate: la corrección de la
    probabilidad de empate ahora se hace correctamente en el origen,
    dentro de ``matriz_resultados`` (ver ``_factor_dixon_coles``), en
    vez de "parchearse" después de sumar. Esta función se limita a
    clasificar y sumar lo que ya viene bien calculado.

    Args:
        matriz: matriz de probabilidades generada por ``matriz_resultados``.

    Returns:
        Diccionario con las claves "local", "empate" y "visitante",
        cuyos valores suman ~100 (en porcentaje).
    """
    prob_local = 0.0
    prob_empate = 0.0
    prob_visitante = 0.0

    for i, fila in enumerate(matriz):
        for j, probabilidad in enumerate(fila):
            if i > j:
                prob_local += probabilidad
            elif i == j:
                prob_empate += probabilidad
            else:
                prob_visitante += probabilidad

    return {
        "local": round(prob_local, 1),
        "empate": round(prob_empate, 1),
        "visitante": round(prob_visitante, 1),
    }


def top_resultados_exactos(matriz: list[list[float]], top_n: int = 5) -> list[dict]:
    """Devuelve los ``top_n`` marcadores exactos más probables.

    Args:
        matriz: matriz de probabilidades generada por ``matriz_resultados``.
        top_n: cantidad de resultados a devolver.

    Returns:
        Lista de diccionarios ordenada de mayor a menor probabilidad,
        con las claves "marcador" y "probabilidad".
    """
    resultados = []
    for goles_local, fila in enumerate(matriz):
        for goles_visitante, probabilidad in enumerate(fila):
            resultados.append({
                "marcador": f"{goles_local}-{goles_visitante}",
                "probabilidad": probabilidad,
            })

    resultados.sort(key=lambda r: r["probabilidad"], reverse=True)
    return resultados[:top_n]


def mejor_marcador_por_categoria(matriz: list[list[float]]) -> dict[str, dict]:
    """Devuelve el marcador más probable DENTRO de cada categoría.

    ``top_resultados_exactos`` responde "¿cuál es la celda individual
    más probable de toda la matriz?", que casi siempre es un empate
    bajo (0-0 o 1-1): el empate concentra su probabilidad en pocos
    marcadores, mientras que una victoria se reparte entre muchos
    (1-0, 2-0, 2-1, 3-1...). Por eso el marcador más probable en
    general puede ser un empate incluso cuando "victoria" es la
    categoría más probable en conjunto -- ambas cosas son ciertas al
    mismo tiempo y no se contradicen.

    Esta función responde una pregunta distinta y complementaria:
    "si el resultado fuera victoria local, ¿cuál sería el marcador más
    probable?" (y lo mismo para empate y victoria visitante). Ninguna
    de las dos funciones está "mal"; miden cosas distintas.

    Args:
        matriz: matriz de probabilidades generada por ``matriz_resultados``.

    Returns:
        Diccionario con claves "local", "empate", "visitante", cada
        una con el marcador y probabilidad más altos dentro de esa
        categoría específica.
    """
    mejor_local = {"marcador": None, "probabilidad": -1.0}
    mejor_empate = {"marcador": None, "probabilidad": -1.0}
    mejor_visitante = {"marcador": None, "probabilidad": -1.0}

    for i, fila in enumerate(matriz):
        for j, probabilidad in enumerate(fila):
            candidato = {"marcador": f"{i}-{j}", "probabilidad": probabilidad}
            if i > j and probabilidad > mejor_local["probabilidad"]:
                mejor_local = candidato
            elif i == j and probabilidad > mejor_empate["probabilidad"]:
                mejor_empate = candidato
            elif i < j and probabilidad > mejor_visitante["probabilidad"]:
                mejor_visitante = candidato

    return {"local": mejor_local, "empate": mejor_empate, "visitante": mejor_visitante}
