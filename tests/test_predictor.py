"""
test_predictor.py
==================

Pruebas del orquestador (src/predictor.py). A diferencia de
test_model.py, estas pruebas SÍ dependen de datos (el dataset de
ejemplo en data/ejemplo_selecciones.json), porque predictor.py conecta
la matemática con la obtención de datos real.
"""

import pytest

from src import predictor


def test_sede_invalida_lanza_error():
    """Una sede que no sea 'local', 'visitante' o 'neutral' debe
    fallar explícitamente, no ser ignorada en silencio."""
    with pytest.raises(ValueError):
        predictor.predecir_partido("Argentina", "Brazil", sede="Marte")


def test_sede_neutral_no_favorece_a_ningun_equipo():
    """En cancha neutral, ninguno de los dos xG debe llevar el factor
    de localía: el xG del 'local' en modo neutral tiene que ser menor
    o igual al mismo cálculo con sede='local' (donde sí lo recibe)."""
    prediccion_neutral = predictor.predecir_partido("Argentina", "Brazil", sede="neutral")
    prediccion_local = predictor.predecir_partido("Argentina", "Brazil", sede="local")

    assert prediccion_neutral["xg_local"] < prediccion_local["xg_local"]


def test_probabilidades_de_prediccion_completa_suman_cien():
    """Prueba de integración: de punta a punta, las 3 probabilidades
    finales de un partido real (con datos de ejemplo) deben sumar 100%."""
    prediccion = predictor.predecir_partido("Spain", "France", sede="neutral")
    probs = prediccion["probabilidades"]
    total = probs["local"] + probs["empate"] + probs["visitante"]
    assert total == pytest.approx(100, abs=1)


def test_equipo_inexistente_lanza_value_error():
    """Un nombre de selección que no existe ni en caché ni en el
    dataset de ejemplo debe fallar con un error claro, no con un
    KeyError críptico en medio del cálculo."""
    with pytest.raises(ValueError):
        predictor.predecir_partido("Equipo Inventado XYZ", "Argentina", sede="neutral")
