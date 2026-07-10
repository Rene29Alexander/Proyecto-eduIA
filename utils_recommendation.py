# -*- coding: utf-8 -*-
"""
Sistema de Recomendación IA para EduIA Platform.

Genera retos NUEVOS con Gemini basados en el perfil real del estudiante:
- Lenguajes que más usa
- Dificultad apropiada según su score promedio
- Temas que ya domina (para variar) y áreas que no ha tocado
- Cada llamada produce retos únicos y distintos
"""

from __future__ import annotations
import json
import logging
import random
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Perfil del estudiante
# ─────────────────────────────────────────────────────────────────────────────

def _get_student_profile(conn, student_id: str) -> Dict[str, Any]:
    """
    Construye perfil desde historial.
    Los ultimos 20 intentos tienen peso 3x para reflejar preferencias recientes.
    """
    all_rows = conn.execute("""
        SELECT dc.language, dc.difficulty, dca.score, dca.completed, dc.title
        FROM daily_challenge_attempts dca
        JOIN daily_challenges dc ON dca.challenge_id = dc.id
        WHERE dca.user_id = ?
        ORDER BY dca.id DESC
        LIMIT 100
    """, (student_id,)).fetchall()

    if not all_rows:
        return {"preferred_lang": "Python", "recommended_diff": "easy",
                "avg_score": 0, "done_titles": [], "total": 0,
                "top_langs": ["Python"], "lang_weight": {}}

    lang_scores: Dict[str, float] = {}
    diff_scores: Dict[str, list] = {}
    done_titles = []

    for idx, r in enumerate(all_rows):
        lang = r["language"] or "Python"
        diff = r["difficulty"] or "easy"
        score = float(r["score"] or 0)
        title = r["title"] or ""
        title_key = f"{lang}::{title}"
        # Peso reciente: los primeros 20 (mas recientes) valen 3x
        weight = 3.0 if idx < 20 else 1.0
        lang_scores[lang] = lang_scores.get(lang, 0) + weight
        diff_scores.setdefault(diff, []).append(score)
        if title_key not in done_titles:
            done_titles.append(title_key)

    top_langs = sorted(lang_scores, key=lang_scores.get, reverse=True)
    preferred_lang = top_langs[0] if top_langs else "Python"
    second_lang = top_langs[1] if len(top_langs) > 1 else None
    third_lang = top_langs[2] if len(top_langs) > 2 else None

    all_scores = [float(r["score"] or 0) for r in all_rows]
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

    diff_avgs = {d: sum(s)/len(s) for d, s in diff_scores.items()}
    if diff_avgs.get("medium", 0) >= 75 and avg_score >= 75:
        recommended_diff = "hard"
    elif diff_avgs.get("easy", 0) >= 70 and avg_score >= 65:
        recommended_diff = "medium"
    else:
        recommended_diff = "easy"

    return {
        "preferred_lang": preferred_lang,
        "second_lang": second_lang,
        "third_lang": third_lang,
        "top_langs": top_langs[:4],
        "recommended_diff": recommended_diff,
        "avg_score": avg_score,
        "done_titles": done_titles[:30],
        "lang_weight": lang_scores,
        "total": len(done_titles),
    }

# ─────────────────────────────────────────────────────────────────────────────
# Generación IA de retos
# ─────────────────────────────────────────────────────────────────────────────

def _generate_ai_challenges(model, profile: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    """
    Pide a Gemini que genere `limit` retos únicos y complejos
    adaptados al perfil del estudiante.
    """
    if model is None:
        return []

    preferred_lang = profile.get("preferred_lang", "Python")
    second_lang    = profile.get("second_lang", "")
    third_lang     = profile.get("third_lang", "")
    top_langs      = profile.get("top_langs", [preferred_lang])
    diff           = profile.get("recommended_diff", "medium")
    avg_score      = profile.get("avg_score", 0)
    done_titles    = profile.get("done_titles", [])
    total          = profile.get("total", 0)

    diff_label = {"easy": "fácil", "medium": "intermedio", "hard": "avanzado"}.get(diff, "intermedio")

    # Descripción detallada del perfil con TODOS los lenguajes usados
    langs_str = ", ".join(top_langs) if top_langs else preferred_lang
    profile_desc = f"El estudiante ha intentado {total} ejercicios únicos en distintos lenguajes. "
    profile_desc += f"Sus lenguajes más usados RECIENTEMENTE son: {langs_str}. "
    profile_desc += f"Score promedio: {avg_score:.0f}%. Nivel recomendado: {diff_label}."

    done_str = ", ".join(done_titles[:10]) if done_titles else "ninguno aún"
    seed_hint = random.randint(1000, 9999)

    # Distribuir los retos entre los top lenguajes del estudiante
    lang_assignments = []
    for i in range(limit):
        lang_assignments.append(top_langs[i % len(top_langs)] if top_langs else "Python")
    langs_for_prompt = ", ".join(f"reto {i+1} en {l}" for i, l in enumerate(lang_assignments))

    prompt = f"""Eres un experto en programación creando retos de código personalizados.

PERFIL DEL ESTUDIANTE:
{profile_desc}

RETOS YA REALIZADOS (NO REPETIR):
{done_str}

SEMILLA DE VARIEDAD: {seed_hint}

TAREA: Genera EXACTAMENTE {limit} retos de programación COMPLETAMENTE DIFERENTES entre sí.

REGLAS OBLIGATORIAS:
1. Nivel de dificultad: {diff_label.upper()}
2. DISTRIBUCION DE LENGUAJES (obligatorio): {langs_for_prompt}
3. Los retos deben ser COMPLEJOS y TRABAJADOS — NO ejercicios triviales
4. Cada reto debe tener un problema real con contexto, restricciones y ejemplos
5. NO repetir ninguno de los retos ya realizados
6. Cada reto debe ser ÚNICO y DIFERENTE al resto
7. Usa la semilla {seed_hint} para garantizar variedad

TIPOS DE RETOS ACEPTABLES (nivel {diff_label}):
- Algoritmos de búsqueda/ordenamiento con variaciones
- Estructuras de datos (árboles, grafos, pilas, colas)
- Procesamiento de texto con reglas complejas
- Simulaciones de sistemas reales
- Algoritmos de optimización
- Manipulación de matrices/grids
- Parsers o validadores con múltiples reglas
- Problemas de lógica matemática aplicada

FORMATO JSON (responde SOLO el JSON, sin markdown):
[
  {{
    "title": "Título descriptivo y específico del reto",
    "description": "Descripción detallada del problema (3-5 oraciones) con contexto real",
    "language": "LENGUAJE_SEGUN_DISTRIBUCION",
    "difficulty": "{diff}",
    "example_input": "Ejemplo concreto de entrada",
    "example_output": "Salida esperada para ese ejemplo",
    "hint": "Una pista útil sin revelar la solución"
  }}
]"""

    try:
        from google.generativeai.types import RequestOptions
        request_options = RequestOptions(timeout=30)
        response_obj = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.9,
                "max_output_tokens": 2000,
                "top_p": 0.95,
            },
            request_options=request_options
        )
        response = response_obj.text if response_obj and hasattr(response_obj, "text") else ""

        if not response:
            return []

        # Extraer JSON
        start = response.find("[")
        end = response.rfind("]")
        if start == -1 or end == -1:
            return []

        data = json.loads(response[start:end+1])
        if not isinstance(data, list):
            return []

        challenges = []
        for item in data[:limit]:
            if not isinstance(item, dict):
                continue
            # Construir descripción completa
            full_desc = item.get("description", "")
            if item.get("example_input"):
                full_desc += f"\n\nEjemplo:\nEntrada: {item['example_input']}\nSalida: {item['example_output']}"
            if item.get("hint"):
                full_desc += f"\n\nPista: {item['hint']}"

            challenges.append({
                "id": f"ai_{random.randint(10000, 99999)}",
                "title": item.get("title", "Reto generado por IA"),
                "description": full_desc,
                "language": item.get("language", preferred_lang),
                "difficulty": item.get("difficulty", diff),
                "recommendation_score": 1.0,
                "recommendation_reason": f"Generado por IA · {item.get('language', preferred_lang)} {item.get('difficulty', diff)} · Personalizado para ti",
                "points": 50,
                "bonus_points": 20,
                "ai_generated": True,
            })

        return challenges

    except Exception as e:
        logger.error("Error generando retos con IA: %s", e)
        return []


def _fallback_from_db(conn, student_id: str, profile: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    """Fallback: usa BD cuando la IA no está disponible, con aleatoriedad."""
    seed = sum(ord(c) for c in student_id) + int(datetime.now().timestamp() / 60)
    rng = random.Random(seed)

    done_ids = set()
    rows_done = conn.execute(
        "SELECT DISTINCT challenge_id FROM daily_challenge_attempts WHERE user_id=?",
        (student_id,)
    ).fetchall()
    done_ids = {r["challenge_id"] for r in rows_done}

    rows = conn.execute(
        "SELECT * FROM daily_challenges ORDER BY id DESC LIMIT 50"
    ).fetchall()

    pool = [dict(r) for r in rows if r["id"] not in done_ids]
    if not pool:
        pool = [dict(r) for r in rows]

    # Deduplicar por título
    seen, unique = set(), []
    for item in pool:
        t = item.get("title", "").lower()
        if t not in seen:
            seen.add(t)
            unique.append(item)

    rng.shuffle(unique)
    result = unique[:limit]

    for r in result:
        r["recommendation_score"] = 0.0
        r["recommendation_reason"] = "Reto del banco · IA no disponible"
        r["ai_generated"] = False
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def get_content_recommendations(
    student_id: str,
    db_connection,
    limit: int = 3,
    model=None,
) -> List[Dict[str, Any]]:
    """
    Genera recomendaciones personalizadas con IA.
    Cada llamada produce retos nuevos y únicos basados en el perfil del estudiante.
    """
    conn = db_connection
    profile = _get_student_profile(conn, student_id)

    # Si hay modelo IA disponible → generar retos nuevos
    if model is not None:
        challenges = _generate_ai_challenges(model, profile, limit)
        if challenges:
            return challenges

    # Fallback: BD con aleatoriedad por timestamp
    return _fallback_from_db(conn, student_id, profile, limit)
