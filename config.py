"""
config.py
=========

Configuración centralizada del proyecto Football Predictor.

Reunir acá todas las constantes evita "números mágicos" desperdigados
por el código (principio de Zen de Python: "Explicit is better than
implicit"). Si el día de mañana se quiere recalibrar el modelo, alcanza
con modificar este archivo.
"""

# -----------------------------------------------------------------------
# PARÁMETROS DEL MODELO ESTADÍSTICO
# -----------------------------------------------------------------------

# Cantidad de partidos recientes que se toman en cuenta por equipo.
PARTIDOS_RECIENTES: int = 30

# Cantidad de temporadas (años) hacia atrás a consultar en API-Football
# para juntar los últimos partidos. Es necesario porque el plan
# gratuito NO permite el parámetro "last" (confirmado por la propia
# API); en su lugar, se consulta por "season" año por año y se arma
# el recorte de partidos recientes del lado de Python.
ANIOS_HISTORIAL_API: int = 3

# Máximo de goles a evaluar por equipo al construir la matriz de
# resultados exactos (0 a MAX_GOLES para cada lado).
MAX_GOLES: int = 6

# Media de goles por partido de referencia. Funciona como VALOR DE
# RESPALDO cuando no hay partidos suficientes para calcular el ancla
# dinámica (ver model.promedio_goles_entorno, que es lo que se usa en
# la práctica: se auto-calcula en base a los partidos reales de los
# dos equipos que se enfrentan, en vez de este número fijo).
PROMEDIO_GOLES_TORNEO: float = 2.75

# Peso del ancla de goles (dinámica o de respaldo) sobre el xG calculado
# (0 a 1). Se bajó de 0.30 a 0.15 tras detectar que con 0.30 comprimía
# demasiado la diferencia de nivel en partidos muy dispares (ej. un
# candidato al título contra una selección de las últimas posiciones
# del ranking terminaba con un xG casi parejo, lo cual no es realista).
# 0.15 sigue evitando sobreajuste a rachas de pocos partidos, sin
# aplastar diferencias de nivel genuinas y grandes.
PESO_ANCLA_TORNEO: float = 0.15

# Constante de decaimiento temporal (en días).
# A mayor valor, los partidos viejos pierden peso más lentamente.
VIDA_MEDIA_DECAIMIENTO: int = 180  # ~6 meses

# Ventaja de localía: multiplicador aplicado al equipo que juega en casa.
FACTOR_LOCALIA: float = 1.10

# Ajuste sobre la probabilidad de empate (Zen: "In the face of ambiguity,
# refuse the temptation to guess" -> tau de Dixon-Coles, y no a ojo).
# Corrige el error conocido del Poisson simple, que subestima los
# marcadores 0-0, 1-0, 0-1 y 1-1. Valor negativo típico en la
# literatura (Dixon & Coles, 1997, estimaron rho ~ -0.13 para la
# Premier League inglesa; usamos un valor moderado y documentado).
RHO_DIXON_COLES: float = -0.10

# Peso de la expectativa de Elo (aproximado desde el ranking FIFA)
# sobre la fuerza de cada equipo. Escala cuánto influye la brecha de
# nivel entre ambos equipos (ver model.ajustar_por_ranking).
PESO_RANKING_FIFA: float = 0.15

# Peso del historial de enfrentamientos directos (head-to-head) sobre
# el xG final. Un equipo que históricamente le ganó mucho a este rival
# puntual recibe un empujón hacia arriba proporcional a este peso.
PESO_H2H: float = 0.12

# Tope máximo (en goles de xG) que el ajuste h2h puede mover el xG
# final, en cualquier dirección. Evita que un historial extremo (una
# goleada puntual) distorsione desproporcionadamente la predicción.
MAX_AJUSTE_H2H: float = 0.35

# -----------------------------------------------------------------------
# RUTAS DE ARCHIVOS
# -----------------------------------------------------------------------
RUTA_DATOS = "data"
ARCHIVO_EQUIPOS = f"{RUTA_DATOS}/teams_data.json"
ARCHIVO_HISTORIAL = f"{RUTA_DATOS}/matches_history.json"
ARCHIVO_RANKING = f"{RUTA_DATOS}/fifa_ranking.json"

# -----------------------------------------------------------------------
# PALETA DE COLORES PARA VISUALIZACIÓN (estilo dashboard oscuro)
# -----------------------------------------------------------------------
COLOR_FONDO = "#0d1520"
COLOR_FONDO_TARJETA = "#141d2b"
COLOR_TEXTO = "#e8edf2"
COLOR_TEXTO_SECUNDARIO = "#8b98a8"

COLOR_LOCAL = "#38b6d8"      # celeste (equipo A / local)
COLOR_VISITANTE = "#e2563f"  # rojo-naranja (equipo B / visitante)
COLOR_EMPATE = "#d9a441"     # dorado (empate)

# Escala de calor para la matriz de resultados exactos (de menos a más
# probable). matplotlib arma el degradé interpolando estos tres colores.
ESCALA_CALOR = ["#141d2b", "#2c5f78", "#38b6d8"]
