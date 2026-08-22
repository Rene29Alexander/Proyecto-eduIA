# Informe Final — EduIA
## Evaluación Final Módulo 4 — Preespecialización UGB

**Proyecto:** EduIA — Plataforma Educativa con Inteligencia Artificial
**Grupo:** Grupo 2
**Integrantes:** Jonathan Roberto Acosta Lopez · Rene Alexander Araujo Soto · Mario Alexander Hernández Quevedo
**URL pública:** https://eduiaiugb.streamlit.app/
**Repositorio:** https://github.com/Rene29Alexander/Proyecto-eduIA
**Versión:** 1.0.0 | **Commit:** 8a05d00 | **Fecha:** Agosto 2026

---

## 1. Diagnóstico inicial y evolución (Sesión 1)

### Problema identificado
Los docentes invierten demasiado tiempo en tareas repetitivas: crear exámenes desde cero, calificar entregas y dar retroalimentación individual. Los estudiantes aprenden a ritmos distintos pero reciben el mismo contenido estático sin adaptación.

### Usuarios
| Usuario | Necesidad |
|---|---|
| Docente | Crear evaluaciones y dar retroalimentación sin invertir horas extras |
| Estudiante | Aprender a su ritmo con apoyo personalizado e inmediato |
| Administrador | Gestionar la plataforma de forma eficiente |

### Arquitectura inicial vs. arquitectura final

**Inicial (Sesión 1):** Todo el código mezclado en archivos de vista Streamlit. Sin API, sin pruebas, sin contenedor, sin separación de responsabilidades.

**Final (Sesión 6):** Arquitectura en capas con separación frontend/backend, API REST, módulo de IA con cache y pool de keys, despliegue en Streamlit Cloud, pruebas automatizadas y pipeline CI/CD.

```
[Navegador] → [Streamlit Cloud — app principal]
                        ↓
              [FastAPI — API REST local/Docker]
                        ↓
              [Módulo IA — utils_ai_core.py]
              Cache + Pool de keys + Reintentos
                        ↓
              [Google Gemini API]
                        ↓
              [SQLite / PostgreSQL — Supabase]
```

### Deuda técnica resuelta
| Deuda inicial | Estado final |
|---|---|
| Sin separación frontend/backend | ✅ API REST separada con FastAPI |
| Sin pruebas automatizadas | ✅ 103 pruebas unitarias |
| Sin CI/CD | ✅ GitHub Actions en cada push |
| Sin contenedor | ✅ Dockerfile + Docker Desktop |
| Sin despliegue público | ✅ Streamlit Cloud |
| Sin cache de IA | ✅ AICache con TTL 24h |

---

## 2. API inteligente y contratos (Sesión 2)

### Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | /health | Estado del servicio y base de datos |
| GET | /metadata | Versión, tecnologías y capacidades |
| POST | /api/evaluate | Evaluación de código con Gemini |
| POST | /api/courses/generate | Generación de curso personalizado |
| POST | /api/chat/ask | Chat educativo contextualizado |

### Contrato de entrada/salida — endpoint principal

**POST /api/evaluate**
```json
// Entrada
{
  "code": "def suma(a, b):\n    return a + b",
  "language": "python",
  "criteria": "Evalúa corrección y buenas prácticas"
}

// Salida exitosa (200)
{
  "score": 8,
  "correctness": "correcto",
  "feedback": "El código es funcional...",
  "suggestions": ["Agregar docstring", "Manejar tipos"],
  "concepts": ["funciones", "parámetros"],
  "errors_detected": [],
  "language": "python",
  "ai_available": true
}

// Error de validación (422)
{ "detail": [{ "loc": ["body", "language"], "msg": "value is not a valid enum member" }] }

// Gemini no disponible (503)
{ "detail": "Servicio de IA no disponible" }
```

### Manejo de errores
- **422** — validación de entrada (lenguaje no soportado, código vacío, contexto corto)
- **503** — Gemini no disponible (respuesta de fallback controlada)
- **429** — cuota agotada (pool de keys rota automáticamente)

---

## 3. Pruebas y CI/CD (Sesión 3)

### Resumen de pruebas

| Archivo | Tipo | Tests | Requiere servidor |
|---|---|---|---|
| test_api_unit.py | Unitaria | 29 | No |
| test_analizador_sintaxis.py | Unitaria | 26 | No |
| test_analizador_logica.py | Unitaria | 18 | No |
| test_sistema_evaluacion.py | Unitaria | 30 | No |
| test_engagement_managers.py | Unitaria | ~545 líneas | No |
| **Total** | | **103+** | |

### Pipeline CI/CD
- **Plataforma:** GitHub Actions
- **Trigger:** push a `main` y pull_request
- **Pasos:** checkout → Python 3.11 → pip install → pytest
- **Estado:** ✅ Pasando en todos los commits recientes

### Variables de entorno
- `GEMINI_API_KEY` — en GitHub Secrets para CI, en `.streamlit/secrets.toml` para app
- `.env.example` documenta todas las variables sin exponer valores reales

---

## 4. Despliegue e infraestructura (Sesión 4)

### Configuración reproducible
- **Contenedor local:** Docker — `eduia-api:1.0` en puerto 8000
- **Despliegue público:** Streamlit Cloud — https://eduiaiugb.streamlit.app/
- **Imagen base:** python:3.11-slim
- **HEALTHCHECK:** verifica /health cada 30 segundos

### Dependencias principales
```
streamlit>=1.28.0 | fastapi>=0.111.0 | uvicorn>=0.29.0
google-generativeai>=0.3.0 | bcrypt>=4.0.0 | pandas>=2.0.0
```

### Costos de infraestructura
| Servicio | Plan | Costo/mes |
|---|---|---|
| Streamlit Cloud | Community (gratuito) | $0 |
| Google Gemini API | Free tier (1,500 req/día) | $0 |
| GitHub | Free | $0 |
| **Total** | | **$0 USD** |

---

## 5. Observabilidad, rendimiento y escalabilidad (Sesión 5)

### Métricas de pruebas de carga (Locust)

**Prueba con 20 usuarios simultáneos:**
- Endpoint más lento: /api/evaluate (depende de Gemini)
- /health: p50 < 50ms, p95 < 100ms
- Tasa de error: 0% en endpoints de sistema

**Prueba con 200 usuarios simultáneos:**
- Cuello de botella identificado: llamadas a Gemini API (latencia variable)
- /health: se mantiene estable
- Tasa de error esperada: mayor en endpoints IA por límite de cuota

### Cuello de botella principal
La latencia de Google Gemini API (entre 2-15 segundos por llamada) es el factor limitante. Se mitigó con:
- Cache persistente (AICache) — evita llamadas repetidas
- Pool de API keys (APIKeyPool) — rota entre keys al agotarse cuota
- Reintentos con backoff exponencial

### Plan de escalabilidad
1. **Corto plazo:** Múltiples API keys de Gemini en pool
2. **Mediano plazo:** PostgreSQL/Supabase — migración completada en rama `migracion-base-de-datos`
3. **Largo plazo:** Cola de trabajos para peticiones IA + caché Redis

---

## 6. Seguridad, release y rollback (Sesión 6)

### Controles de seguridad implementados
- API keys nunca en el repositorio (`.gitignore` incluye `secrets.toml`)
- `.env.example` documenta variables sin valores reales
- Validación de entrada en todos los endpoints (Pydantic)
- Sin exposición de errores internos en respuestas de producción
- Panel admin sin escritura a `secrets.toml` (fix aplicado en rama migracion)

### Riesgos prioritarios

| Riesgo | Impacto | Control |
|---|---|---|
| Cuota Gemini agotada | Alto | Pool de keys + fallback controlado |
| Sin autenticación JWT | Medio | Sesión Streamlit (scope académico) |
| Dependencia de Google Gemini API | Alto | Pool de 5 keys + cache + reintentos con backoff |

### Release y rollback
- **Versión:** v1.0.0
- **Commit:** 7ac7349
- **Rollback:** `git reset --hard 7ac7349` en rama `migracion-base-de-datos` — tiempo estimado < 5 minutos
- **Rama estable:** migracion-base-de-datos

---

## Limitaciones declaradas

1. Sin autenticación por tokens seguros (JWT) — solo sesión en memoria de Streamlit
2. Sin HTTPS propio en contenedor local (requiere reverse proxy para producción)
3. La generación de exámenes con IA no garantiza siempre el número exacto de preguntas solicitadas
4. Dependencia de disponibilidad de Google Gemini API — sin internet las funciones de IA no funcionan (mitigado con pool de 5 keys y fallback controlado)
5. Streamlit Cloud duerme la app tras 7 días sin tráfico (~30s para despertar)

---

## Siguientes pasos

- Implementar autenticación JWT en la API
- Configurar HTTPS con reverse proxy (Nginx)
- Evaluar migración de rate limiting propio a slowapi para mayor control
