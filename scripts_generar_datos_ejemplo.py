"""
Script único (no forma parte del paquete src/) para generar un dataset
de ejemplo amplio -- todas las confederaciones -- y así poder ejecutar
y defender el proyecto sin depender de una API key propia, incluso
para selecciones poco frecuentes (ej. DR Congo vs Zambia).

IMPORTANTE: los nombres de equipo están en INGLÉS a propósito, no en
español. API-Football (la fuente de datos reales) identifica a las
selecciones por su nombre en inglés ("England", no "Inglaterra";
"Spain", no "España"). Si el dataset de respaldo usara nombres en
español, un mismo partido tendría una clave distinta según si los
datos vinieron de la API o del respaldo -- una inconsistencia real que
ya nos pasó una vez. Usar el mismo idioma en todo el sistema evita
ese problema de raíz.

Los goles se simulan con distribución de Poisson usando una fuerza de
ataque/defensa derivada del ranking aproximado de cada selección, para
que los números sean coherentes (un equipo mejor rankeado mete más
goles y recibe menos, en promedio) y no puramente aleatorios.

IMPORTANTE (para la defensa del proyecto): estos rankings son
aproximados e ilustrativos, pensados para poder demostrar el modelo
end-to-end sin depender de una API externa. Con una API_FOOTBALL_KEY
configurada, el programa consulta datos reales y actuales para
CUALQUIER selección de las 211 afiliadas a FIFA, sin esta limitación.

fifa_ranking.json se genera desde esta MISMA fuente de datos (no un
archivo separado escrito a mano), para que ranking y goles nunca queden
desincronizados entre sí.
"""
import json
from datetime import datetime, timedelta

import numpy as np

np.random.seed(42)

# (nombre en inglés -- igual que API-Football, ranking_fifa_aproximado, confederación)
# Rankings ilustrativos basados en tiers generales de julio 2026;
# no reemplazan una consulta real al ranking oficial de FIFA.
SELECCIONES_RAW = [
    # --- UEFA ---
    ("Spain", 2, "UEFA"), ("France", 3, "UEFA"), ("England", 4, "UEFA"),
    ("Portugal", 6, "UEFA"), ("Netherlands", 7, "UEFA"), ("Belgium", 8, "UEFA"),
    ("Germany", 9, "UEFA"), ("Italy", 10, "UEFA"), ("Croatia", 11, "UEFA"),
    ("Switzerland", 17, "UEFA"), ("Denmark", 18, "UEFA"), ("Sweden", 22, "UEFA"),
    ("Poland", 24, "UEFA"), ("Austria", 25, "UEFA"), ("Serbia", 27, "UEFA"),
    ("Norway", 33, "UEFA"), ("Scotland", 34, "UEFA"), ("Ukraine", 35, "UEFA"),
    ("Turkey", 39, "UEFA"), ("Wales", 43, "UEFA"), ("Hungary", 44, "UEFA"),
    ("Czech Republic", 48, "UEFA"), ("Romania", 46, "UEFA"), ("Greece", 50, "UEFA"),
    # --- CONMEBOL ---
    ("Argentina", 1, "CONMEBOL"), ("Brazil", 5, "CONMEBOL"), ("Colombia", 12, "CONMEBOL"),
    ("Uruguay", 13, "CONMEBOL"), ("Ecuador", 21, "CONMEBOL"), ("Chile", 37, "CONMEBOL"),
    ("Peru", 38, "CONMEBOL"), ("Paraguay", 48, "CONMEBOL"), ("Venezuela", 49, "CONMEBOL"),
    ("Bolivia", 78, "CONMEBOL"),
    # --- CAF (África) ---
    ("Morocco", 14, "CAF"), ("Senegal", 19, "CAF"), ("Nigeria", 26, "CAF"),
    ("Tunisia", 28, "CAF"), ("Egypt", 29, "CAF"), ("Algeria", 30, "CAF"),
    ("Ghana", 31, "CAF"), ("Ivory Coast", 36, "CAF"), ("Cameroon", 42, "CAF"),
    ("South Africa", 60, "CAF"), ("Mali", 56, "CAF"), ("Cape Verde", 57, "CAF"),
    ("Burkina Faso", 63, "CAF"), ("DR Congo", 65, "CAF"),
    ("Zambia", 85, "CAF"), ("Guinea", 68, "CAF"), ("Benin", 90, "CAF"),
    # --- CONCACAF ---
    ("Mexico", 16, "CONCACAF"), ("United States", 15, "CONCACAF"),
    ("Canada", 41, "CONCACAF"), ("Costa Rica", 45, "CONCACAF"),
    ("Panama", 44, "CONCACAF"), ("Jamaica", 52, "CONCACAF"),
    ("Honduras", 66, "CONCACAF"),
    # --- AFC (Asia) ---
    ("Japan", 20, "AFC"), ("South Korea", 23, "AFC"), ("Iran", 32, "AFC"),
    ("Australia", 40, "AFC"), ("Saudi Arabia", 46, "AFC"), ("Qatar", 51, "AFC"),
    ("Iraq", 58, "AFC"), ("Uzbekistan", 62, "AFC"),
    # --- OFC (Oceanía) ---
    ("New Zealand", 89, "OFC"),
]

datos_finales = {}
ranking_final = {}
hoy = datetime.now()

# Agrupamos nombres por confederación, para poder simular rivales que
# se enfrentan con más frecuencia dentro de su propia región (mismo
# criterio que en el fútbol real: clasificatorias, copas regionales).
por_confederacion = {}
for nombre, ranking, confederacion in SELECCIONES_RAW:
    por_confederacion.setdefault(confederacion, []).append(nombre)

for nombre, ranking, confederacion in SELECCIONES_RAW:
    # Ataque/defensa derivados del ranking con una fórmula (no a mano
    # equipo por equipo): mejor ranking (número más chico) -> más
    # ataque y menos defensa concedida. Se agrega algo de ruido para
    # que dos equipos con ranking parecido no queden idénticos.
    ruido_ataque = np.random.normal(0, 0.08)
    ruido_defensa = np.random.normal(0, 0.08)
    ataque = max(0.65, round(2.3 - ranking * 0.012 + ruido_ataque, 2))
    defensa = max(0.55, round(0.65 + ranking * 0.010 + ruido_defensa, 2))

    rivales_regionales = [r for r in por_confederacion[confederacion] if r != nombre]
    rivales_globales = [r for r, _, _ in SELECCIONES_RAW if r != nombre]

    partidos = []
    for _ in range(30):
        dias_atras = int(np.random.uniform(5, 400))
        fecha = (hoy - timedelta(days=dias_atras)).strftime("%Y-%m-%d")
        es_local = bool(np.random.randint(0, 2))

        # 70% de los partidos son contra rivales de la misma confederación
        # (clasificatorias/copas regionales) -> genera enfrentamientos
        # repetidos, necesarios para poder calcular el ajuste h2h.
        if rivales_regionales and np.random.random() < 0.70:
            rival = str(np.random.choice(rivales_regionales))
        else:
            rival = str(np.random.choice(rivales_globales))

        goles_favor = int(np.random.poisson(ataque))
        goles_contra = int(np.random.poisson(defensa))

        partidos.append({
            "fecha": fecha,
            "goles_favor": goles_favor,
            "goles_contra": goles_contra,
            "local": es_local,
            "rival": rival,
        })

    partidos.sort(key=lambda p: p["fecha"])
    datos_finales[nombre] = {"ranking_fifa": ranking, "partidos": partidos}
    ranking_final[nombre] = ranking

with open("data/ejemplo_selecciones.json", "w", encoding="utf-8") as f:
    json.dump(datos_finales, f, ensure_ascii=False, indent=2)

with open("data/fifa_ranking.json", "w", encoding="utf-8") as f:
    json.dump(ranking_final, f, ensure_ascii=False, indent=2)

print(f"Generadas {len(SELECCIONES_RAW)} selecciones (en inglés) en data/ejemplo_selecciones.json")
print(f"Ranking sincronizado en data/fifa_ranking.json ({len(ranking_final)} equipos)")
