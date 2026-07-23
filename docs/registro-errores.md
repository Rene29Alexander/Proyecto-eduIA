# Registro de Errores, Correcciones y Bloqueos — EduIA

> Documento requerido por la Evaluación Semana 3.
> Registra errores encontrados durante el desarrollo, sus causas y soluciones.

---

## Error 1 — SyntaxError en api.py (línea 301)

**Fecha:** Semana 2 / Semana 3  
**Archivo:** `api.py`  
**Tipo:** Error de sintaxis Python

**Descripción:**
```
SyntaxError: unterminated string literal (detected at line 301)
```

**Causa raíz:**  
El campo `examples=` del modelo Pydantic `ChatAskRequest` contenía un string con saltos de línea literales (`\n` reales) dentro de comillas simples. Python no permite strings multilínea entre comillas simples sin usar `\` o triple comilla.

**Corrección aplicada:**  
Se reemplazó el string multilínea por concatenación de strings adyacentes (Python los une en tiempo de compilación):

```python
# Antes (incorrecto)
examples=["Texto largo
con saltos de línea
reales aquí"]

# Después (correcto)
examples=[
    "Texto largo "
    "continuado en la siguiente línea "
    "sin saltos literales."
]
```

**Estado:** ✅ Resuelto

---

## Error 2 — Logs con datos de ejecución subidos al repositorio

**Fecha:** Semana 2  
**Archivos:** `logs/consistency_adjustments.json`, `logs/evaluation_events.json`, `logs/evaluation_metrics.json`  
**Tipo:** Problema de limpieza del repositorio

**Descripción:**  
Los archivos de logs fueron incluidos en el commit inicial. Aunque no contienen credenciales, sí contienen datos de ejecución internos que no deberían estar en el repositorio público.

**Corrección aplicada:**
1. Se ejecutó `git rm --cached` para sacarlos del tracking sin eliminarlos localmente
2. Se actualizó `.gitignore` para excluir toda la carpeta `logs/`

```bash
git rm --cached logs/consistency_adjustments.json logs/evaluation_events.json logs/evaluation_metrics.json
```

**Estado:** ✅ Resuelto

---

## Error 3 — Archivos sensibles y de cache no excluidos del repo

**Fecha:** Semana 2  
**Archivos:** `*.db-shm`, `*.db-wal`, `ai_cache.pkl`, `__pycache__/`  
**Tipo:** Limpieza del entregable

**Descripción:**  
El `.gitignore` inicial no cubría todos los archivos generados en tiempo de ejecución: archivos WAL/SHM de SQLite, cache de respuestas de IA (`ai_cache.pkl`) y carpetas de cache de Python.

**Corrección aplicada:**  
Se amplió el `.gitignore` para cubrir:
- `*.db-shm`, `*.db-wal` (archivos auxiliares de SQLite en modo WAL)
- `ai_cache.pkl` (cache de respuestas de Gemini)
- `.cache/` (cache de Streamlit)
- `__pycache__/`, `*.pyc` (bytecode de Python)
- `backups/` (copias de la base de datos)

**Estado:** ✅ Resuelto

---

## Bloqueo 1 — Las pruebas de integración requieren servidor externo

**Fecha:** Semana 3  
**Archivo:** `tests/test_api_evidencia.py`  
**Tipo:** Bloqueo técnico de CI/CD

**Descripción:**  
El archivo `test_api_evidencia.py` realiza peticiones HTTP reales a `http://127.0.0.1:8000`. Esto impide ejecutarlo en el pipeline CI/CD porque no hay un servidor corriendo en el entorno de GitHub Actions.

**Solución implementada:**  
Se creó `tests/test_api_unit.py` usando `TestClient` de FastAPI, que prueba los endpoints directamente en memoria sin necesidad de levantar un servidor. Este archivo sí corre en CI/CD.

`test_api_evidencia.py` se mantiene para pruebas manuales locales con el servidor corriendo.

**Estado:** ✅ Resuelto con enfoque alternativo

---

## Advertencia detectada — Librería `google-generativeai` deprecada

**Fecha:** Semana 3  
**Archivo:** `utils_ai.py`  
**Tipo:** Warning de deprecación

**Descripción:**  
Durante la ejecución de pruebas aparece:
```
FutureWarning: All support for the `google.generativeai` package has ended.
Please switch to the `google.genai` package as soon as possible.
```

**Estado:** ⚠️ Pendiente — requiere migrar `utils_ai.py` a `google.genai` en semana futura  
**Impacto:** No rompe la funcionalidad actual, solo es una advertencia

---

## Resumen de estado

| # | Problema | Tipo | Estado |
|---|---|---|---|
| 1 | SyntaxError en api.py línea 301 | Bug de sintaxis | ✅ Resuelto |
| 2 | Logs subidos al repo | Limpieza | ✅ Resuelto |
| 3 | .gitignore incompleto | Limpieza | ✅ Resuelto |
| 4 | Tests de integración no corren en CI | Bloqueo técnico | ✅ Resuelto con alternativa |
| 5 | Librería Gemini deprecada | Advertencia | ⚠️ Pendiente Semana 4 |
