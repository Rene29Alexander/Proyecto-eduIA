# -*- coding: utf-8 -*-
"""
Evidencia de prueba automatizada — Evaluacion Semana 2
Ejecutar con:  python tests/test_api_evidencia.py

Genera en consola los resultados para cada caso de prueba documentado.
Requiere que la API esté corriendo:  uvicorn api:app --reload
"""

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
PASS = "✅ PASS"
FAIL = "❌ FAIL"
SEP  = "─" * 60


def request(method: str, path: str, body: dict = None) -> tuple[int, dict]:
    """Hace una petición HTTP simple sin dependencias externas."""
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as exc:
        return 0, {"error": str(exc)}


def print_case(title: str, status: int, body: dict, expected_status: int, check_fn=None):
    ok = status == expected_status
    if check_fn:
        ok = ok and check_fn(body)
    icon = PASS if ok else FAIL
    print(f"\n{icon}  {title}")
    print(f"    HTTP {status} (esperado {expected_status})")
    print(f"    Respuesta: {json.dumps(body, ensure_ascii=False, indent=4)[:500]}")
    return ok


results = []

print(f"\n{'='*60}")
print("  EduIA — Evidencia de Prueba API  (Semana 2)")
print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*60}")

# ─── BLOQUE 1: Endpoints de sistema ──────────────────────────────────────────
print(f"\n{SEP}")
print("BLOQUE 1 — Endpoints de Sistema")
print(SEP)

# 1a. GET /health — exitoso
code, body = request("GET", "/health")
results.append(print_case(
    "GET /health — servicio activo",
    code, body, 200,
    lambda b: b.get("status") == "ok"
))

# 1b. GET /metadata — exitoso
code, body = request("GET", "/metadata")
results.append(print_case(
    "GET /metadata — información del servicio",
    code, body, 200,
    lambda b: b.get("version") == "1.0.0"
))

# ─── BLOQUE 2: POST /api/evaluate ─────────────────────────────────────────────
print(f"\n{SEP}")
print("BLOQUE 2 — POST /api/evaluate")
print(SEP)

# 2a. Código Python correcto
code, body = request("POST", "/api/evaluate", {
    "code": "def suma(a, b):\n    return a + b",
    "language": "python",
    "criteria": "Función que suma dos números."
})
results.append(print_case(
    "POST /api/evaluate — código Python correcto",
    code, body, 200,
    lambda b: "score" in b and "feedback" in b
))

# 2b. Código con errores — esperar score bajo
code, body = request("POST", "/api/evaluate", {
    "code": "def suma(a b\n    retun a + b",
    "language": "python"
})
results.append(print_case(
    "POST /api/evaluate — código con errores sintácticos",
    code, body, 200,
    lambda b: "errors_detected" in b or b.get("score", 10) <= 7
))

# 2c. Validación — lenguaje no soportado → 422
code, body = request("POST", "/api/evaluate", {
    "code": "PROGRAM Hello; BEGIN writeln('Hola'); END.",
    "language": "pascal"
})
results.append(print_case(
    "POST /api/evaluate — lenguaje no soportado (422 esperado)",
    code, body, 422
))

# 2d. Validación — código vacío → 422
code, body = request("POST", "/api/evaluate", {
    "code": "   ",
    "language": "python"
})
results.append(print_case(
    "POST /api/evaluate — código sólo espacios (422 esperado)",
    code, body, 422
))

# 2e. Validación — falta campo requerido → 422
code, body = request("POST", "/api/evaluate", {
    "language": "python"
})
results.append(print_case(
    "POST /api/evaluate — sin campo 'code' (422 esperado)",
    code, body, 422
))

# ─── BLOQUE 3: POST /api/courses/generate ─────────────────────────────────────
print(f"\n{SEP}")
print("BLOQUE 3 — POST /api/courses/generate")
print(SEP)

# 3a. Petición exitosa
code, body = request("POST", "/api/courses/generate", {
    "language": "python",
    "level": "principiante",
    "sections_count": 3
})
results.append(print_case(
    "POST /api/courses/generate — Python principiante (3 temas)",
    code, body, 200,
    lambda b: isinstance(b.get("topics"), list) and len(b["topics"]) > 0
))

# 3b. Validación — nivel inválido → 422
code, body = request("POST", "/api/courses/generate", {
    "language": "python",
    "level": "experto"
})
results.append(print_case(
    "POST /api/courses/generate — nivel inválido (422 esperado)",
    code, body, 422
))

# 3c. Validación — sections_count fuera de rango → 422
code, body = request("POST", "/api/courses/generate", {
    "language": "python",
    "level": "intermedio",
    "sections_count": 0
})
results.append(print_case(
    "POST /api/courses/generate — sections_count=0 (422 esperado)",
    code, body, 422
))

# ─── BLOQUE 4: POST /api/chat/ask ─────────────────────────────────────────────
print(f"\n{SEP}")
print("BLOQUE 4 — POST /api/chat/ask")
print(SEP)

CONTEXT = (
    "Python es un lenguaje interpretado de alto nivel. "
    "Sus estructuras de datos principales son: listas [], tuplas (), "
    "diccionarios {} y conjuntos set(). "
    "Las listas son mutables y las tuplas son inmutables. "
    "Los diccionarios almacenan pares clave-valor."
)

# 4a. Pregunta simple con contexto
code, body = request("POST", "/api/chat/ask", {
    "context": CONTEXT,
    "question": "¿Qué diferencia hay entre una lista y una tupla?",
    "history": []
})
results.append(print_case(
    "POST /api/chat/ask — pregunta sobre el contexto",
    code, body, 200,
    lambda b: isinstance(b.get("response"), str) and len(b["response"]) > 10
))

# 4b. Con historial
code, body = request("POST", "/api/chat/ask", {
    "context": CONTEXT,
    "question": "¿Y los diccionarios cómo funcionan?",
    "history": [
        {
            "message": "¿Qué diferencia hay entre una lista y una tupla?",
            "response": "Las listas son mutables y las tuplas son inmutables."
        }
    ]
})
results.append(print_case(
    "POST /api/chat/ask — con historial de conversación",
    code, body, 200,
    lambda b: isinstance(b.get("response"), str)
))

# 4c. Validación — contexto muy corto → 422
code, body = request("POST", "/api/chat/ask", {
    "context": "Hola",
    "question": "¿Qué es Python?"
})
results.append(print_case(
    "POST /api/chat/ask — contexto demasiado corto (422 esperado)",
    code, body, 422
))

# 4d. Validación — pregunta vacía → 422
code, body = request("POST", "/api/chat/ask", {
    "context": CONTEXT,
    "question": "   "
})
results.append(print_case(
    "POST /api/chat/ask — pregunta vacía (422 esperado)",
    code, body, 422
))

# ─── RESUMEN ──────────────────────────────────────────────────────────────────
total  = len(results)
passed = sum(results)
failed = total - passed

print(f"\n{'='*60}")
print(f"  RESUMEN: {passed}/{total} casos pasaron")
if failed:
    print(f"  {failed} caso(s) fallaron — verifica que la API esté corriendo")
    print(f"  Comando: uvicorn api:app --reload")
print(f"{'='*60}\n")

sys.exit(0 if failed == 0 else 1)
