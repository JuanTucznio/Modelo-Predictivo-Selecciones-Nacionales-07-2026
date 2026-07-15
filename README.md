# ⚽ Football Predictor

Predictor de resultados de fútbol para selecciones nacionales, basado
en un modelo estadístico de **Expected Goals (xG)** y distribución de
**Poisson corregida (Dixon-Coles)**. Dado un partido entre dos
selecciones, calcula la probabilidad de victoria / empate / derrota,
la probabilidad de cada marcador exacto, y lo muestra en consola +
en gráficos con estética de dashboard.

Desarrollado como Trabajo Final de **Programación 1 — Ciencia de Datos**
(ISTEA, 2026).

```
 DR Congo  vs  Zambia   (cancha neutral)
 xG estimado:  1.44  -  1.39
 Gana DR Congo: 37.2%   Empate: 27.5%   Gana Zambia: 35.1%
 Marcador más probable: 1-1 (13.0%)
```

---

## 📊 ¿Cómo funciona el modelo?

1. **Fuerza de ataque/defensa**: se calcula a partir de los últimos
   30 partidos de cada selección, aplicando un **decaimiento temporal
   exponencial** (los partidos recientes pesan más que los viejos).
2. **Expectativa de Elo (aproximada) desde el ranking FIFA**: en vez
   de una resta lineal de posiciones, se convierte el ranking a una
   escala tipo Elo (logarítmica: la brecha entre el top 1 y el top 10
   pesa mucho más que entre el puesto 100 y el 110) y se usa la
   **fórmula estándar de expectativa de Elo** (la misma que ajedrez o
   eloratings.net) para ajustar la fuerza de cada equipo. Esto
   reemplazó una versión anterior más simple que, en partidos muy
   dispares (ej. un top 1 contra un top 85), terminaba comprimiendo
   demasiado la diferencia de nivel real entre ambos.
3. **Ancla de goles dinámica**: en vez de un número de torneo fijo,
   se calcula en base a los partidos reales de los dos equipos que se
   enfrentan, con un peso moderado (no dominante) para no aplastar
   diferencias de nivel genuinas y grandes.
4. **Historial de enfrentamientos directos (head-to-head)**: si dos
   selecciones tienen partidos previos entre sí en el historial
   cargado, ese antecedente puntual empuja levemente el xG a favor de
   quien históricamente dominó ese cruce específico (acotado, para que
   una goleada aislada no distorsione todo).
5. **Localía tri-estado**: el partido puede jugarse con el equipo 1
   de local, el equipo 2 de local, o en **cancha neutral** (el caso
   típico de un Mundial), y el modelo ajusta el factor de ventaja en
   consecuencia — no asume automáticamente que "el primero es local".
6. **Distribución de Poisson + corrección de Dixon-Coles (1997)**: con
   el xG final de cada equipo, se calcula la probabilidad de cada
   marcador exacto. La corrección de Dixon-Coles ajusta los 4
   marcadores de pocos goles (0-0, 1-0, 0-1, 1-1), donde el Poisson
   simple subestima sistemáticamente los empates. Como consecuencia
   natural de este enfoque, un marcador bajo y parejo (ej. 1-1) es
   siempre más probable que uno alto e inusual (ej. 5-4) para equipos
   de fuerza comparable — no hace falta forzarlo aparte.

Todos los parámetros del modelo (pesos, decaimiento, tope del ajuste
h2h, etc.) están centralizados y documentados en [`config.py`](./config.py).

> **Nota sobre idioma:** los nombres de selecciones se escriben en
> **inglés** (`Argentina`, `England`, `Spain`, `DR Congo`...), el mismo
> idioma que usa API-Football. Usar un único idioma en todo el sistema
> (API real y dataset de respaldo) evita que un mismo equipo tenga dos
> claves distintas según de dónde vinieron los datos.

> **Nota sobre el marcador "más probable":** la salida muestra dos
> cosas distintas a propósito. El marcador más probable **en general**
> suele ser un empate bajo (1-1, 0-0), porque el empate concentra su
> probabilidad en pocos marcadores mientras que una victoria se reparte
> entre muchos (1-0, 2-0, 2-1...). Por eso también se muestra el mejor
> marcador **dentro de cada categoría** ("si gana el local, ¿cuál es
> el marcador más probable?") — ninguna de las dos vistas está mal,
> responden preguntas distintas.

---

## 🗂️ Estructura del proyecto

```
football_predictor/
├── config.py               # Constantes y parámetros del modelo
├── main.py                 # Punto de entrada (interactivo)
├── requirements.txt        # Dependencias
├── src/
│   ├── data_fetcher.py     # Obtención y caché de datos (API / JSON)
│   ├── model.py            # Matemática pura: xG, decaimiento, Poisson, h2h
│   ├── predictor.py        # Orquesta data_fetcher + model
│   └── visualizer.py       # Gráficos (matriz de calor, distribución)
├── data/
│   ├── ejemplo_selecciones.json   # 67 selecciones de ejemplo (todas las confederaciones)
│   └── fifa_ranking.json          # Ranking sincronizado con el dataset de ejemplo
├── tests/
│   ├── test_model.py        # Tests del núcleo matemático
│   └── test_predictor.py    # Tests de integración
└── assets/                  # Gráficos generados (se crean al ejecutar)
```

---

## 🚀 Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repo>
cd football_predictor

# 2. Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate       # Linux/Mac
venv\Scripts\activate          # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

---

## ▶️ Uso

### Modo interactivo (el uso normal)

```bash
python main.py
```

El programa va a preguntar:

```
Rival 1 (nombre de la selección): Argentina
Rival 2 (nombre en inglés, ej: Argentina, England): England

¿Dónde se juega el partido?
  1) Argentina de local
  2) England de local
  3) Cancha neutral (ej: fase de grupos de un Mundial)
Elegí una opción (1/2/3): 3
```

Y automáticamente:
1. Calcula la predicción.
2. Muestra el resumen completo por consola (xG, probabilidades, top
   de marcadores, entorno de goles detectado).
3. Genera **3 gráficos** en `assets/` (ficha de xG/Elo, matriz de
   resultados exactos, distribución Victoria/Empate/Derrota) **y los
   abre solo**, sin que
   tengas que ir a buscarlos a mano.

Funciona con **cualquiera de las 67 selecciones** del dataset de
ejemplo (todas las confederaciones — desde Argentina-England hasta
DR Congo-Zambia), y con **cualquiera de las 211 selecciones FIFA**
si tenés una API key real configurada (ver más abajo).

### Modo no interactivo (para pruebas/automatización)

```bash
python main.py "Argentina" "Brasil"              # Argentina de local
python main.py "Argentina" "Brasil" neutral      # cancha neutral
python main.py "Argentina" "Brasil" visitante    # Brasil de local
```

### Datos reales vs. datos de ejemplo

El proyecto está preparado para consultar **API-Football**
directamente (sin marketplaces intermediarios). Para usar datos
reales y actuales de cualquier selección:

1. Registrate gratis en [dashboard.api-football.com/register](https://dashboard.api-football.com/register)
   (sin tarjeta de crédito — plan gratuito con 100 requests/día).
2. Copiá tu clave desde **Account → My Access** en el dashboard.
3. Configurala como variable de entorno:

```bash
export API_FOOTBALL_KEY="tu_clave_aqui"    # Linux/Mac
$env:API_FOOTBALL_KEY="tu_clave_aqui"      # Windows PowerShell
```

Si no hay clave configurada (caso por defecto), el sistema usa
automáticamente el dataset de ejemplo en `data/ejemplo_selecciones.json`
(67 selecciones, con rankings aproximados/ilustrativos — ver el
docstring de `scripts_generar_datos_ejemplo.py` para el detalle), para
que el proyecto sea ejecutable sin depender de un servicio externo.

---

## 🧪 Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

20 tests: cubren decaimiento temporal, cálculo de fuerza, ancla
dinámica, ajuste h2h, corrección de Dixon-Coles, y predicción de
punta a punta (integración).

---

## 🎨 Estilo de código

El proyecto sigue **PEP 8** (verificado con `flake8`) y documenta cada
función con **docstrings estilo PEP 257**.

```bash
pip install flake8
flake8 --max-line-length=100 config.py main.py src/ tests/
```

---

## 🐍 Zen de Python aplicado

Algunas decisiones concretas de diseño, explicadas por un principio del
Zen de Python (`import this`):

- **"Explicit is better than implicit"** → todos los parámetros del
  modelo están en `config.py`, con nombres y comentarios explícitos,
  en vez de números mágicos sueltos en el código.
- **"Simple is better than complex"** → cada módulo tiene una única
  responsabilidad (datos, matemática, orquestación, visualización).
- **"Errors should never pass silently"** → `data_fetcher.py` distingue
  explícitamente entre "no hay API key", "falló la conexión" y "un
  partido individual vino con datos raros", en vez de un `except`
  genérico que oculte el problema real.
- **"In the face of ambiguity, refuse the temptation to guess"** →
  el ajuste de la probabilidad de empate no se resolvió "a ojo"
  (restando un número que parecía razonable), sino aplicando la
  corrección de Dixon-Coles, publicada y verificable.

---

## 🔭 Próximos pasos

- Adaptar el modelo para clubes (por liga), no solo selecciones.
- Incorporar lesiones/suspensiones como factor de ajuste.
- Reemplazar el ranking FIFA estático por un sistema Elo dinámico
  (como hacen varios modelos de referencia, ver Referencias).
- Simulación de Monte Carlo para predecir un cuadro de torneo completo,
  no solo partido a partido.

---

## 📚 Librerías externas utilizadas

| Librería | Uso |
|----------|-----|
| `requests` | Consultas HTTP a API-Football |
| `scipy` | Distribución de Poisson (`scipy.stats.poisson`) |
| `numpy` | Cálculos numéricos en la generación de datos de ejemplo |
| `matplotlib` | Generación de gráficos |

---

## 📖 Referencias

- Dixon, M.J. y Coles, S.G. (1997). *Modelling Association Football
  Scores and Inefficiencies in the Football Betting Market*. Journal
  of the Royal Statistical Society, Series C, 46(2), 265-280. — fuente
  de la corrección aplicada en `_factor_dixon_coles()` (`src/model.py`).
- [API-Football — documentación oficial](https://www.api-football.com/documentation-v3)
- [scipy.stats.poisson — documentación oficial](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.poisson.html)
- Proyectos de referencia consultados en GitHub para comparar enfoques:
  [Hicruben/world-cup-2026-prediction-model](https://github.com/Hicruben/world-cup-2026-prediction-model)
  (Elo + Dixon-Coles + Monte Carlo para el Mundial 2026).

---

**Autor:** Juan Pablo Tucznio
**Materia:** Programación 1 — 1C - Ciencia de Datos Miercoles
**Profesor:** Juan Pablo Sosa
