"""
data_fetcher.py
================

Responsable de conseguir los datos que necesita el modelo: partidos
recientes por selección y ranking FIFA.

Estrategia de datos (importante para la defensa del proyecto)
---------------------------------------------------------------
Este módulo sigue un patrón de **caché con fallback**:

1. Si existe un archivo JSON local con los datos, se usa ese (rápido,
   no depende de internet, no gasta cuota de la API).
2. Si no existe, y hay una API key configurada, se intenta consultar
   API-Football (conexión directa a api-sports.io, plan gratuito de
   100 requests/día) y se guarda el resultado en caché.
3. Si la API falla (sin conexión, sin clave, límite de peticiones
   agotado), se capturan las excepciones puntuales y se recurre a un
   conjunto de datos de ejemplo, para que el programa jamás se caiga
   por un problema externo fuera de nuestro control.

Esto es exactamente lo que se pide en la Unidad 9: no capturar
excepciones "a ciegas", sino identificar qué puede fallar y responder
en consecuencia (ver ``obtener_datos_equipo``).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import requests

import config

API_KEY = os.environ.get("API_FOOTBALL_KEY", "")
API_URL = "https://v3.football.api-sports.io"


class ErrorAPIFootball(RuntimeError):
    """Error explícito devuelto por API-Football dentro de una respuesta
    HTTP 200 (campo "errors"), distinto de "no hay API key configurada".

    Se diferencia de un RuntimeError genérico a propósito: un error de
    la API sobre UNA temporada puntual (ej. "esta season no está
    disponible en tu plan") se puede saltear y probar la siguiente
    temporada. La ausencia total de API key, en cambio, no tiene
    sentido reintentarla año por año -- hay que abortar de una.
    """


# -------------------------------------------------------------------
# UTILIDADES DE ARCHIVOS (Unidad 10: lectura/escritura de archivos)
# -------------------------------------------------------------------

def cargar_json(ruta: str) -> dict | None:
    """Carga un archivo JSON si existe.

    Args:
        ruta: ruta al archivo .json.

    Returns:
        El contenido parseado como diccionario, o None si el archivo
        no existe o está corrupto.
    """
    archivo = Path(ruta)
    if not archivo.exists():
        return None

    try:
        with open(archivo, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # El archivo existe pero tiene contenido inválido: lo tratamos
        # como si no existiera, en vez de romper la ejecución.
        return None


def guardar_json(ruta: str, datos: dict) -> None:
    """Guarda un diccionario como JSON, creando la carpeta si falta.

    Args:
        ruta: ruta destino del archivo .json.
        datos: contenido a serializar.
    """
    archivo = Path(ruta)
    archivo.parent.mkdir(parents=True, exist_ok=True)

    with open(archivo, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)


# -------------------------------------------------------------------
# CONSULTA A LA API (API-Football / api-sports.io)
# -------------------------------------------------------------------

def _consultar_api(endpoint: str, parametros: dict) -> dict:
    """Realiza una petición GET a API-Football (api-sports.io).

    IMPORTANTE: API-Football puede devolver HTTP 200 (respuesta
    "exitosa" a nivel de red) pero con una lista ``response`` vacía Y
    un campo ``errors`` que explica la razón real (límite de plan,
    cuota agotada, parámetro no permitido, etc.). Un ``raise_for_status``
    NO detecta esto, porque el problema no es de nivel HTTP -- por eso
    lo chequeamos explícitamente acá, en vez de asumir que "response
    vacío" significa simplemente "el equipo no tiene partidos".

    Args:
        endpoint: sub-ruta del endpoint (ej: "fixtures").
        parametros: query params de la petición.

    Returns:
        La respuesta ya parseada como diccionario.

    Raises:
        RuntimeError: si no hay API key configurada, o si la API
            devolvió un campo "errors" no vacío.
        requests.exceptions.RequestException: ante cualquier problema
            de red (timeout, DNS, conexión rechazada, etc.).
    """
    if not API_KEY:
        raise RuntimeError(
            "No hay API_FOOTBALL_KEY configurada como variable de entorno."
        )

    headers = {"x-apisports-key": API_KEY}
    respuesta = requests.get(
        f"{API_URL}/{endpoint}",
        headers=headers,
        params=parametros,
        timeout=10,
    )
    respuesta.raise_for_status()
    datos = respuesta.json()

    errores = datos.get("errors")
    # La API a veces devuelve "errors" como lista vacía y a veces como
    # diccionario vacío según el endpoint; en ambos casos vacío = OK.
    if errores:
        raise ErrorAPIFootball(f"API-Football devolvió un error explícito: {errores}")

    return datos


def _buscar_id_equipo(nombre_equipo: str) -> int:
    """Busca el ID interno que usa API-Football para una selección.

    La API no identifica equipos por nombre en los demás endpoints,
    sino por un ID numérico propio. Este es siempre el primer paso.

    Args:
        nombre_equipo: nombre de la selección (ej: "Argentina").

    Returns:
        El ID numérico del equipo según API-Football.

    Raises:
        ValueError: si la búsqueda no devuelve ningún equipo (nombre
            mal escrito, o la API respondió una lista vacía).
    """
    datos = _consultar_api("teams", {"search": nombre_equipo})
    resultados = datos.get("response", [])

    if not resultados:
        # Caso real que documenté arriba: la API puede responder 200 OK
        # con una lista vacía cuando no encuentra coincidencias.
        raise ValueError(f"API-Football no encontró ningún equipo para '{nombre_equipo}'.")

    return resultados[0]["team"]["id"]


def _obtener_partidos_recientes(equipo_id: int, cantidad: int) -> list[dict]:
    """Obtiene los últimos partidos de un equipo y los normaliza.

    IMPORTANTE: el plan gratuito de API-Football NO permite usar el
    parámetro ``last`` (confirmado por el propio campo "errors" de la
    API: "Free plans do not have access to the 'Last' parameter.").
    Por eso, en vez de pedirle a la API "los últimos N partidos"
    directamente, consultamos por ``season`` (que sí está permitido en
    el plan gratis) a lo largo de los últimos ``config.ANIOS_HISTORIAL_API``
    años, juntamos todos los partidos de esas temporadas, y recién ACÁ,
    en Python, los ordenamos por fecha y recortamos a los ``cantidad``
    más recientes -- el mismo resultado final, sin depender de un
    parámetro que el plan gratuito no permite.

    Args:
        equipo_id: ID del equipo según API-Football.
        cantidad: cantidad de partidos recientes a devolver.

    Returns:
        Lista de partidos en formato ``Partido`` (ver model.py),
        ordenada de más antiguo a más reciente (mismo orden que usa
        el dataset de ejemplo).
    """
    anio_actual = datetime.now().year
    partidos_crudos = []

    for anio in range(anio_actual, anio_actual - config.ANIOS_HISTORIAL_API, -1):
        try:
            datos = _consultar_api("fixtures", {"team": equipo_id, "season": anio})
        except ErrorAPIFootball:
            # Esta temporada puntual no está disponible (ej. plan
            # gratuito con restricciones de años); probamos la
            # siguiente en vez de abortar todo.
            continue
        partidos_crudos.extend(datos.get("response", []))

    partidos = []
    for partido in partidos_crudos:
        try:
            es_local = partido["teams"]["home"]["id"] == equipo_id
            goles_local_api = partido["goals"]["home"]
            goles_visitante_api = partido["goals"]["away"]
            fecha = partido["fixture"]["date"][:10]  # "AAAA-MM-DDTHH:MM" -> "AAAA-MM-DD"
            nombre_rival = (
                partido["teams"]["away"]["name"] if es_local
                else partido["teams"]["home"]["name"]
            )
        except (KeyError, TypeError):
            # Un partido individual con estructura inesperada no debe
            # tirar abajo la consulta completa: lo salteamos y seguimos
            # con el resto (Unidad 9: fallar en lo específico, no en
            # lo general).
            continue

        # Si los goles son None (partido suspendido/sin jugar), también
        # se saltea: un partido sin resultado no aporta información.
        if goles_local_api is None or goles_visitante_api is None:
            continue

        partidos.append({
            "fecha": fecha,
            "goles_favor": goles_local_api if es_local else goles_visitante_api,
            "goles_contra": goles_visitante_api if es_local else goles_local_api,
            "local": es_local,
            "rival": nombre_rival,
        })

    # Como juntamos varias temporadas, puede haber más partidos de los
    # que pedimos: ordenamos por fecha y nos quedamos con los más
    # recientes, que es lo que en definitiva se quería lograr.
    partidos.sort(key=lambda p: p["fecha"])
    return partidos[-cantidad:]


def _obtener_ranking_fifa(nombre_equipo: str) -> int:
    """Obtiene el ranking FIFA desde un archivo local.

    API-Football no expone el ranking FIFA como endpoint, así que este
    dato se mantiene en un JSON local que se actualiza manualmente
    (el ranking FIFA cambia pocas veces al año, no hace falta
    automatizarlo).

    Args:
        nombre_equipo: nombre de la selección.

    Returns:
        Posición en el ranking FIFA. Si el equipo no está en el
        archivo, devuelve 100 como valor conservador por defecto.
    """
    rankings = cargar_json(config.ARCHIVO_RANKING) or {}
    return rankings.get(nombre_equipo, 100)


# -------------------------------------------------------------------
# FUNCIÓN PRINCIPAL: OBTENER DATOS DE UNA SELECCIÓN
# -------------------------------------------------------------------

def obtener_datos_equipo(nombre_equipo: str) -> dict:
    """Obtiene los últimos partidos y el ranking de una selección.

    Aplica el patrón caché -> API -> datos de ejemplo descrito en el
    docstring del módulo.

    Args:
        nombre_equipo: nombre de la selección (ej: "Argentina").

    Returns:
        Diccionario con las claves "ranking_fifa" y "partidos"
        (lista de partidos recientes con fecha, goles a favor/contra
        y localía).
    """
    clave_cache = nombre_equipo.lower().replace(" ", "_")
    ruta_cache = f"{config.RUTA_DATOS}/{clave_cache}.json"

    datos_en_cache = cargar_json(ruta_cache)
    if datos_en_cache is not None:
        return datos_en_cache

    try:
        equipo_id = _buscar_id_equipo(nombre_equipo)
        partidos = _obtener_partidos_recientes(equipo_id, config.PARTIDOS_RECIENTES)

        if not partidos:
            # La API respondió, pero sin partidos útiles (caso real
            # documentado: puede pasar aunque el equipo exista).
            raise ValueError(f"API-Football no devolvió partidos para {nombre_equipo}.")

        datos = {
            "ranking_fifa": _obtener_ranking_fifa(nombre_equipo),
            "partidos": partidos,
        }
        guardar_json(ruta_cache, datos)
        return datos

    except RuntimeError as error:
        # Puede ser "no hay API key" (desarrollo/demo) O un error
        # explícito que devolvió la propia API (plan, cuota, parámetro
        # no permitido). Mostramos el motivo real en vez de asumir
        # siempre el mismo caso -- así se puede diagnosticar de verdad.
        print(f"[aviso] {error} Usando datos de ejemplo para {nombre_equipo}.")
    except requests.exceptions.RequestException as error:
        # Problema de red real: la API existe, pero no respondió bien.
        print(f"[error de red] {error}. Usando datos de ejemplo para {nombre_equipo}.")
    except ValueError as error:
        # La API respondió correctamente pero sin datos útiles
        # (equipo no encontrado, o sin partidos disponibles).
        print(f"[aviso] {error} Usando datos de ejemplo.")

    return _datos_de_ejemplo(nombre_equipo)


def _datos_de_ejemplo(nombre_equipo: str) -> dict:
    """Genera (o carga) un dataset de ejemplo para poder demostrar el
    modelo sin depender de una API externa.

    En un entorno real, este método no existiría: es exclusivamente
    para que el proyecto sea ejecutable durante la corrección sin
    necesitar una API key propia.
    """
    datos = cargar_json(f"{config.RUTA_DATOS}/ejemplo_selecciones.json")
    if datos and nombre_equipo in datos:
        return datos[nombre_equipo]

    raise ValueError(
        f"No se encontraron datos de ejemplo para '{nombre_equipo}'. "
        f"Revisá data/ejemplo_selecciones.json"
    )
