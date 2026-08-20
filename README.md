#  EduIA — Plataforma Educativa con Inteligencia Artificial

> Plataforma web educativa que integra IA para automatizar la generación de contenido, evaluaciones y retroalimentación personalizada para estudiantes, docentes y administradores.

**🌐 URL pública:** [https://eduiaiugb.streamlit.app/](https://eduiaiugb.streamlit.app/)
**📦 Repositorio:** [github.com/Rene29Alexander/Proyecto-eduIA](https://github.com/Rene29Alexander/Proyecto-eduIA)
**🏷️ Release:** `v1.0.0` — rama `migracion-base-de-datos`
**🔁 CI/CD:** ![CI](https://github.com/Rene29Alexander/Proyecto-eduIA/actions/workflows/ci.yml/badge.svg)

---

## 🌐 Producto público

| | |
|---|---|
| **URL pública** | https://eduiaiugb.streamlit.app/ |
| **Repositorio** | https://github.com/Rene29Alexander/Proyecto-eduIA |
| **Versión** | v1.0.0 |
| **Release** | [v1.0.0](https://github.com/Rene29Alexander/Proyecto-eduIA/releases/tag/v1.0.0) |
| **Commit** | `a8be18f` |
| **Pipeline CI/CD** | [![CI](https://github.com/Rene29Alexander/Proyecto-eduIA/actions/workflows/ci.yml/badge.svg)](https://github.com/Rene29Alexander/Proyecto-eduIA/actions) |
| **Informe final** | [docs/final/informe-final.md](docs/final/informe-final.md) |
| **Credenciales demo** | Usuario: `admin` / Contraseña: `admin123` |

---

##  Integrantes del grupo

- Rene Alexander Araujo Soto
- Jonathan Roberto Acosta Lopez
- Mario Alexander Hernandez Quevedo

---

## 1. Descripción del problema

Los docentes invierten demasiado tiempo en tareas repetitivas: crear exámenes desde cero, calificar entregas y dar retroalimentación individual. Al mismo tiempo, los estudiantes aprenden a ritmos distintos pero reciben el mismo contenido estático sin ninguna adaptación.

Este problema afecta a docentes con grupos numerosos y a estudiantes que necesitan apoyo personalizado que no pueden recibir por limitación de tiempo del profesor.

---

## 2. Usuarios o beneficiarios principales

| Usuario | Necesidad |
|---|---|
|  Docente | Crear evaluaciones y dar retroalimentación sin invertir horas extras |
|  Estudiante | Aprender a su ritmo con apoyo personalizado e inmediato |
|  Administrador | Gestionar la plataforma de forma eficiente |

---

## 3. Descripción general de la solución

EduIA es una plataforma web construida con Python y Streamlit que permite:
- Gestionar cursos, módulos, tareas y exámenes
- Generar evaluaciones automáticamente con IA a partir de PDFs o texto
- Ofrecer un chat educativo por módulo usando el material del curso como contexto
- Personalizar el aprendizaje de programación según el nivel de cada estudiante
- Comunicar a admin, docentes y estudiantes mediante chat privado y notificaciones

---

## 4. ¿Dónde está la Inteligencia Artificial?

La IA participa en tres momentos clave:

1. **Generación de exámenes** — el docente sube material y Gemini genera preguntas automáticamente
2. **Chat educativo por módulo** — el estudiante pregunta y Gemini responde usando el material configurado
3. **Academia Personal de Programación** — evaluación diagnóstica y plan de aprendizaje adaptado al nivel del estudiante

---

## 5. Tipo de IA, modelo y técnica utilizada

| Elemento | Detalle |
|---|---|
| Tipo | IA Generativa — Large Language Model (LLM) |
| Modelos soportados | `gemini-3.1-flash-lite-preview`, `gemini-2.5-flash-lite`, `gemini-3-flash`, `gemini-2.5-flash`, `gemini-2.0-flash`, `gemma-4-26b-a4b-it`, `gemma-3-27b-it` (y más, con fallback automático) |
| Servicio | Google AI Studio API (`google-generativeai`) |
| Técnica | Prompting con contexto dinámico (RAG simplificado) |
| Pool de keys | Hasta 5 API keys con rotación automática por cuota |

---

## 6. Datos de entrada y salida

| Dirección | Descripción |
|---|---|
| **Entrada** | Texto del docente, PDFs del material, código del estudiante, preguntas del chat, respuestas de evaluación diagnóstica |
| **Salida** | Preguntas de examen estructuradas, retroalimentación de código, respuestas del chat, plan de aprendizaje personalizado |

---

## 7. Instrucciones de instalación y ejecución

### Requisitos
- Python 3.11 o superior
- Cuenta y API Key de Google Gemini (gratis en [aistudio.google.com](https://aistudio.google.com))

### Instalación

```bash
# 1. Clonar o descomprimir el proyecto
cd Grupo-2-proyecto

# 2. Crear entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key (ver sección siguiente)

# 5. Ejecutar la aplicación
python -m streamlit run main.py
```

---

## 8. Variables de entorno requeridas

Crear el archivo `.streamlit/secrets.toml` con el siguiente contenido:

```toml
GEMINI_API_KEY = "tu_api_key_aqui"
```

Para usar PostgreSQL en producción (Supabase), agregar también:

```toml
GEMINI_API_KEY = "tu_api_key_aqui"
DATABASE_URL   = "postgresql://postgres:tu_password@db.xxxx.supabase.co:5432/postgres"
```

> Si `DATABASE_URL` no está definida, la app usa SQLite local automáticamente. No es necesario cambiarlo para desarrollo.

Para el pool de API keys (rotación automática cuando se agota la cuota):

```toml
GEMINI_API_KEY   = "tu_api_key_principal"
GEMINI_API_KEY_2 = "tu_api_key_alternativa_2"
GEMINI_API_KEY_3 = "tu_api_key_alternativa_3"
GEMINI_API_KEY_4 = "tu_api_key_alternativa_4"
GEMINI_API_KEY_5 = "tu_api_key_alternativa_5"
```

> Las keys también se pueden configurar directamente desde el panel de administración (Configuración del Sistema > Pool de API Keys), sin necesidad de editar archivos manualmente.

> No subir este archivo a repositorios públicos. Ver `.env.example` para referencia completa.

---

## 9. Arquitectura

-  [Arquitectura actual](docs/arquitectura-actual.md)
-  [Arquitectura objetivo](docs/arquitectura-objetivo.md)

---

## 10. Limitaciones conocidas del prototipo

- Depende de internet y disponibilidad de la API de Gemini
- La librería `google-generativeai` está deprecada — requiere migración a `google.genai`
- La generación de exámenes no siempre produce el número exacto de preguntas solicitadas
- Sin autenticación por tokens JWT (solo sesión en memoria de Streamlit)
- En modo SQLite (desarrollo local), no soporta múltiples instancias simultáneas — usar PostgreSQL para producción
- Streamlit Cloud duerme la app tras 7 días sin tráfico (~30s para despertar)

---

## 11. Pruebas automatizadas (Semana 3)

### Ejecutar todas las pruebas unitarias

```bash
# 111 tests unitarios — sin servidor, sin API Key real
python -m pytest tests/test_api_unit.py tests/test_analizador_sintaxis.py tests/test_analizador_logica.py tests/test_engagement_managers.py -v

# Pruebas de base de datos (SQLite local)
python scripts/test_database.py

# Resumen compacto
python -m pytest tests/test_api_unit.py tests/test_analizador_sintaxis.py tests/test_analizador_logica.py tests/test_engagement_managers.py -q
```

### Pruebas de integración (requiere servidor corriendo)

```bash
# 1. Levantar la API en otra terminal
uvicorn api:app --reload

# 2. Ejecutar script de evidencia
python tests/test_api_evidencia.py
```

### Descripción de los archivos de prueba

| Archivo | Tipo | Tests | Requiere servidor |
|---|---|---|---|
| `test_api_unit.py` | Unitaria | 29 | ❌ No |
| `test_analizador_sintaxis.py` | Unitaria | 26 | ❌ No |
| `test_analizador_logica.py` | Unitaria | 18 | ❌ No |
| `test_engagement_managers.py` | Unitaria | 38 | ❌ No |
| `test_api_evidencia.py` | Integración | — | ✅ Sí |
| `test_evaluation_properties.py` | Propiedad | — | ❌ No |
| `scripts/test_database.py` | BD | ~30 checks | ❌ No |
| **Total unitarios** | | **111 ✅** | |

### Pipeline CI/CD — 3 jobs

El proyecto incluye `.github/workflows/ci.yml` con tres jobs que se ejecutan en cada push:

| Job | Qué hace |
|---|---|
| `unit-tests` | 111 pruebas unitarias (API, analizadores, engagement) |
| `db-tests-sqlite` | Pruebas de BD con SQLite local |
| `db-tests-postgres` | Pruebas de BD con PostgreSQL real (servicio en el runner) |

Estado: [Ver pipeline en GitHub Actions](https://github.com/Rene29Alexander/Proyecto-eduIA/actions)

Ver errores detectados y correcciones en [`docs/registro-errores.md`](docs/registro-errores.md)

---

## 12. API REST — FastAPI (Semana 2)

La plataforma expone **todas** sus capacidades de IA a través de una API RESTful construida con FastAPI.

### Instalación de dependencias

```bash
pip install fastapi uvicorn
```

O instala todo el proyecto de una vez:

```bash
pip install -r requirements.txt
```

### Configurar la API Key de Gemini

Antes de levantar la API, define la variable de entorno con tu clave:

```bash
# Windows CMD
set GEMINI_API_KEY=tu_api_key_aqui

# Windows PowerShell
$env:GEMINI_API_KEY="tu_api_key_aqui"

# Linux / Mac
export GEMINI_API_KEY=tu_api_key_aqui
```

> La API Key también puede estar en `.streamlit/secrets.toml` si ya usas la app Streamlit.

### Levantar el servidor

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

El flag `--reload` reinicia el servidor automáticamente al detectar cambios.

### Acceder a la documentación interactiva

| Interfaz | URL |
|---|---|
| **Swagger UI** (probar endpoints desde el navegador) | http://127.0.0.1:8000/docs |
| **ReDoc** (documentación de referencia) | http://127.0.0.1:8000/redoc |

### Endpoints disponibles

| Método | Ruta | Tipo | Descripción |
|---|---|---|---|
| `GET` | `/health` | Sistema | Estado del servicio y BD |
| `GET` | `/metadata` | Sistema | Versión, tecnologías y capacidades |
| `GET` | `/api/stats` | Sistema | Métricas de cache, rate limiting y modelo IA |
| `POST` | `/api/evaluate` | IA | Evaluación inteligente de código |
| `POST` | `/api/courses/generate` | IA | Genera estructura de curso personalizado |
| `POST` | `/api/chat/ask` | IA | Chat educativo contextualizado por material |

### Ejemplos rápidos

**Evaluar código:**
```bash
curl -X POST http://127.0.0.1:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d '{"code": "def suma(a, b):\n    return a + b", "language": "python"}'
```

**Generar curso:**
```bash
curl -X POST http://127.0.0.1:8000/api/courses/generate \
  -H "Content-Type: application/json" \
  -d '{"language": "python", "level": "principiante", "sections_count": 5}'
```

**Chat educativo:**
```bash
curl -X POST http://127.0.0.1:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"context": "Python usa listas [] y tuplas (). Las listas son mutables.", "question": "¿Qué diferencia hay entre lista y tupla?"}'
```

> Documentación completa con todos los contratos, ejemplos de error y más comandos curl en [`docs/api.md`](docs/api.md)

---

## 12. Despliegue con Docker (Semana 4)

### Requisitos
- Docker Desktop instalado ([docker.com](https://www.docker.com/products/docker-desktop/))
- API Key de Google Gemini

### Construir la imagen

```bash
docker build -t eduia-api:1.0 .
```

### Ejecutar el contenedor

```bash
# Windows CMD
docker run -d -p 8000:8000 -e GEMINI_API_KEY=tu_api_key_aqui --name eduia-api eduia-api:1.0

# Windows PowerShell
docker run -d -p 8000:8000 -e GEMINI_API_KEY="tu_api_key_aqui" --name eduia-api eduia-api:1.0

# Linux / Mac
docker run -d -p 8000:8000 -e GEMINI_API_KEY=tu_api_key_aqui --name eduia-api eduia-api:1.0
```

### Verificar que está corriendo

```bash
# Ver estado del contenedor
docker ps

# Ver logs
docker logs eduia-api

# Probar endpoint /health
curl http://localhost:8000/health

# Detener el contenedor
docker stop eduia-api
```

### Acceder a la documentación interactiva

| Interfaz | URL |
|---|---|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## 13. Observabilidad, rendimiento y escalabilidad (Semana 5)

### Instrumentación implementada

La API incluye observabilidad completa mediante:

- **RequestIDMiddleware** — asigna un UUID único (`request_id`) a cada request, propagado en el header `X-Request-ID`
- **Logs estructurados** — cada request registra `request_id`, `method`, `path`, `status` y `duration_ms`
- **Rate limiting** — 60 req/min por IP para endpoints de IA, 300 req/min para endpoints de sistema
- **Cache en memoria** — respuestas de Gemini cacheadas por 5 minutos (TTL configurable)
- **Pool de API keys** — rotación automática entre hasta 5 keys cuando se agota la cuota
- **Singleton de AIManager** — instancia reutilizada entre requests (evita reinicialización costosa)
- **Endpoint `/api/stats`** — métricas operativas en tiempo real (cache, rate limiting, modelo IA)

### Ejemplo de log estructurado

```
2026-08-13 21:14:28 [INFO] eduia.api: request_id=129dcfc3 method=GET path=/health status=200 duration_ms=8.69
2026-08-13 21:14:28 [INFO] eduia.api: evaluate_code — request_id=31fe06ea language=python len=29
2026-08-13 21:14:28 [INFO] eduia.api: request_id=31fe06ea method=POST path=/api/evaluate status=503 duration_ms=2.2
2026-08-13 21:14:29 [INFO] eduia.api: request_id=9f650024 method=POST path=/api/evaluate status=422 duration_ms=0.71
```

### Pruebas de carga con Locust

```bash
# Instalar Locust
pip install locust==2.46.3

# UI interactiva (abrir http://localhost:8089)
locust -f locustfile.py --host http://127.0.0.1:8000

# Prueba mínima headless (20 usuarios — requisito de rúbrica)
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 20 -r 2 -t 60s --html docs/reporte_estres_20u.html --csv docs/reporte_estres_20u

# Prueba de estrés completa (200 usuarios)
locust -f locustfile.py --host http://127.0.0.1:8000 --headless -u 200 -r 10 -t 90s --html docs/reporte_estres_200u.html --csv docs/reporte_estres_200u

# Filtrar por tipo de prueba
locust -f locustfile.py --tags system       # solo health/metadata
locust -f locustfile.py --tags ai           # solo endpoints IA
locust -f locustfile.py --tags validation   # solo casos 422
```

### Resultados de la línea base (sin Gemini activo)

| Escenario | Usuarios | Requests | p50 | p95 | Máximo | Error |
|---|---|---|---|---|---|---|
| Prueba mínima | 20 | 528 | 2 ms | 4 ms | 11 ms | 0% |
| Prueba de estrés | 200 | 2,100+ | 3 ms | 8 ms | 29 ms | 0% |

### Reportes de evidencia

- [`docs/reporte_estres_20u.html`](docs/reporte_estres_20u.html) — reporte visual prueba 20 usuarios
- [`docs/reporte_estres_200u.html`](docs/reporte_estres_200u.html) — reporte visual prueba 200 usuarios
- [`docs/Semana5-Modulo4.pdf`](docs/Semana5-Modulo4.pdf) — entregable completo Semana 5

### Nuevos archivos agregados en Semana 5

| Archivo | Descripción |
|---|---|
| `utils_ai_core.py` | Núcleo de IA sin Streamlit: AICache, APIKeyPool, AIManagerCore con reintentos y backoff |
| `locustfile.py` | Script de pruebas de carga con 5 escenarios y filtrado por tags |
| `tests/test_engagement_managers.py` | 38 tests unitarios para managers del módulo engagement/ |

---

## 14. Migración de base de datos — SQLite → PostgreSQL (Supabase)

### Descripción

`database.py` soporta dos motores de forma transparente:

| Variable `DATABASE_URL` | Motor usado | Cuándo |
|---|---|---|
| No definida | **SQLite** (`learning_platform.db`) | Desarrollo local |
| Definida | **PostgreSQL** (Supabase) | Producción / nube |

Ningún otro archivo del proyecto necesita cambios — la detección es automática al arrancar.

### Helpers de compatibilidad

`database.py` expone dos funciones utilitarias para trabajar con fechas sin importar el motor:

```python
from database import parse_dt, fmt_date

# Convierte timestamp de BD a datetime (SQLite devuelve string, PostgreSQL devuelve datetime)
dt = parse_dt(row['created_at'])

# Formatea a string de forma segura
label = fmt_date(row['sent_at'], '%d/%m/%Y')
```

### Configurar PostgreSQL (Supabase)

1. Crear un proyecto en [supabase.com](https://supabase.com) (plan gratuito disponible)
2. Ir a **Settings → Database → Connection string → URI**
3. Copiar la URL y agregarla al archivo `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "tu_api_key"
DATABASE_URL   = "postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres"
```

O como variable de entorno:

```bash
# Windows PowerShell
$env:DATABASE_URL="postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres"

# Linux / Mac
export DATABASE_URL="postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres"
```

### Migrar datos de SQLite a PostgreSQL

Si ya tienes datos en SQLite y quieres moverlos a PostgreSQL:

```bash
# 1. Asegúrate de tener DATABASE_URL configurada
# 2. Ejecutar el script de migración
python scripts/migrate_to_postgres.py
```

El script:
- Crea el schema completo en PostgreSQL automáticamente (`init_db`)
- Respeta el orden correcto de foreign keys (~50 tablas)
- Convierte tipos de datos incompatibles (BLOB → BYTEA, etc.)
- Inyecta valores por defecto en columnas NOT NULL vacías
- Muestra progreso detallado por tabla y resumen final
- Es seguro de correr múltiples veces (`ON CONFLICT DO NOTHING`)

Ejemplo de salida:

```
============================================================
  MIGRACIÓN SQLite → PostgreSQL
============================================================
  Origen : learning_platform.db (1,240 KB)
  Destino: postgresql://postgres:***@db.xxxx.supabase.co...
============================================================

📦 Conectando a SQLite...
   47 tablas encontradas en SQLite
🐘 Conectando a PostgreSQL...
   Conexión exitosa
🏗  Creando schema en PostgreSQL (init_db)...
   Schema creado correctamente
🔄 Migrando 47 tablas...

  ✅ users: 15 filas
  ✅ courses: 8 filas
  ✅ modules: 24 filas
  ...

============================================================
  RESUMEN DE MIGRACIÓN
  ✅ Filas migradas exitosamente: 1,843
  ⚠  Filas omitidas (conflictos): 0
============================================================
```

### Dependencias adicionales para PostgreSQL

```bash
pip install psycopg2-binary>=2.9.9
```

Ya incluido en `requirements.txt`.

---

## 15. Plan de mejora — Semanas 2 a 6

| Semana | Objetivo |
|---|---|
| Semana 2 | ✅ Crear API REST con FastAPI para separar la lógica de IA del frontend |
| Semana 3 | ✅ Agregar pruebas automatizadas y pipeline CI/CD básico |
| Semana 4 | ✅ Contenerizar con Docker y preparar despliegue en la nube |
| Semana 5 | ✅ Observabilidad, instrumentación, pruebas de carga y escalabilidad |
| Semana 6 | ✅ Migración BD a PostgreSQL/Supabase, diseño responsive móvil, tests BD en CI, release v1.0.0 y defensa técnica |

---

##  Estructura del proyecto

```
Grupo-2-proyecto/
├── main.py                    # Punto de entrada Streamlit
├── api.py                     # API REST FastAPI con observabilidad completa
├── database.py                # BD dual SQLite/PostgreSQL (detección automática)
├── database_engagement.py     # BD del sistema de engagement
├── utils_ai_core.py           # Núcleo de IA: AICache, APIKeyPool, AIManagerCore
├── utils_ai.py                # Integración con Gemini (Streamlit)
├── utils_chat_ai.py           # Chat IA por módulo
├── utils_chat.py              # Chat privado entre usuarios
├── utils_notifications.py     # Sistema de notificaciones
├── utils_security.py          # Validaciones de seguridad
├── utils_performance.py       # Optimizaciones de rendimiento
├── utils_question_bank.py     # Banco de preguntas
├── utils_recommendation.py    # Sistema de recomendaciones
├── locustfile.py              # Script de pruebas de carga (Locust)
├── views_admin.py             # Vista del administrador
├── views_teacher.py           # Vista del docente
├── views_student.py           # Vista del estudiante
├── styles.py                  # Estilos CSS
├── config.py                  # Configuración general
├── ai_course_functions.py     # Cursos de programación personalizados con IA
├── engagement_system.py       # Sistema de gamificación principal
├── engagement/                # Módulos del sistema de engagement
│   ├── badge_manager.py
│   ├── challenge_manager.py
│   ├── daily_question_manager.py
│   ├── duel_manager.py
│   ├── leaderboard_manager.py
│   ├── notification_manager.py
│   ├── points_manager.py
│   ├── shop_manager.py
│   ├── statistics_manager.py
│   ├── streak_manager.py
│   └── team_manager.py
├── evaluacion/                # Módulo de evaluación de código
│   ├── evaluador_integrado.py
│   ├── analizador_logica.py
│   ├── analizador_sintaxis.py
│   ├── detector_errores.py
│   ├── generador_feedback.py
│   ├── logger_evaluacion.py
│   ├── sistema_calificacion.py
│   └── validador_consistencia.py
├── data/                      # Datos estáticos
│   └── question_bank.json
├── docs/                      # Documentación técnica y evidencias
│   ├── diagnostico-semana1.md
│   ├── arquitectura-actual.md
│   ├── arquitectura-objetivo.md
│   ├── riesgos-tecnicos.md
│   ├── plan-mejora.md
│   ├── api.md
│   ├── infra-semana4.md
│   ├── reporte_estres_20u.html    # Reporte Locust 20 usuarios
│   ├── reporte_estres_200u.html   # Reporte Locust 200 usuarios
│   ├── reporte_estres_20u_stats.csv
│   ├── reporte_estres_200u_stats.csv
│   ├── Semana4_Despliegue_Infraestructura_EduIA.pdf
│   ├── Semana5-Modulo4.pdf        # Entregable Semana 5
│   └── link proyecto grupo 2.txt
├── scripts/                   # Scripts de utilidad y mantenimiento
│   ├── migrate_to_postgres.py # Migración completa SQLite → PostgreSQL
│   ├── add_test_coins.py
│   ├── clean_chat.py
│   ├── create_daily_challenges.py
│   ├── test_database.py
│   ├── test_tutor_functions.py
│   └── supabase_sql_to_run.sql
├── tests/                     # Pruebas automatizadas
│   ├── test_api_unit.py
│   ├── test_analizador_sintaxis.py
│   ├── test_analizador_logica.py
│   ├── test_api_evidencia.py
│   ├── test_evaluation_properties.py
│   └── test_engagement_managers.py  # 38 tests engagement managers
├── requirements.txt           # Dependencias (incluye psycopg2-binary para PostgreSQL)
├── Dockerfile                 # Imagen Docker para despliegue
├── .env.example               # Plantilla de variables de entorno
└── .streamlit/
    └── secrets.toml           # API keys y DATABASE_URL (NO subir al repo)
```

---

## 16. Release v1.0.0 — Semana 6

| Elemento | Valor |
|---|---|
| **URL pública** | [https://eduiaiugb.streamlit.app/](https://eduiaiugb.streamlit.app/) |
| **Tag** | `v1.0.0` |
| **Rama** | `migracion-base-de-datos` |
| **Commit demostrado** | `4ec811d` |

### Rollback

Si la versión desplegada presenta problemas críticos:

```bash
# 1. Identificar el commit estable anterior
git log --oneline -5

# 2. Crear rama de rollback
git checkout -b rollback-estable <commit-hash>
git push -u origin rollback-estable

# 3. En Streamlit Cloud: cambiar la rama del deploy a rollback-estable
```

### Pruebas de humo post-deploy

```bash
# Verificar que la app está viva
curl https://eduiaiugb.streamlit.app/

# Verificar que la API responde (si está levantada localmente)
curl http://localhost:8000/health
curl http://localhost:8000/metadata
```

### Seguridad

- Secretos (`GEMINI_API_KEY`, `DATABASE_URL`) almacenados en Streamlit Cloud Secrets — nunca en el repositorio
- Rate limiting: 60 req/min por IP (endpoints IA), 300 req/min (sistema)
- Validación estricta de entradas con Pydantic — sin stacktraces expuestos al cliente
- Diseño responsive implementado — compatible con móvil y tablet

---

## Credenciales de prueba

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `admin123` |
| Docente | _(crear desde panel admin)_ | _(la que se asigne)_ |
| Estudiante | _(crear desde panel admin)_ | _(la que se asigne)_ |
