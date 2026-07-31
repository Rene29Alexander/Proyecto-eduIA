# Infraestructura y Despliegue — EduIA Semana 4

---

## Ruta elegida: Docker local

El proyecto utiliza **contenedor Docker** para ejecutar la API FastAPI de forma
reproducible fuera del entorno personal de desarrollo.

La aplicación Streamlit (frontend) se mantiene en ejecución local por su
dependencia con SQLite y la sesión de usuario en memoria, mientras que la API
REST (FastAPI) se conteneriza por ser el componente más portátil y sin estado.

---

## Plan de infraestructura mínima

```
┌──────────────────────────────────────────────────────────────┐
│                     ENTORNO LOCAL / CLOUD                    │
│                                                              │
│   ┌─────────────────────────┐   ┌────────────────────────┐  │
│   │  Contenedor Docker       │   │  Streamlit (local)     │  │
│   │  eduia-api:1.0           │   │  python -m streamlit   │  │
│   │  FastAPI + Uvicorn       │   │  run main.py           │  │
│   │  Puerto: 8000            │   │  Puerto: 8501          │  │
│   └──────────┬──────────────┘   └──────────┬─────────────┘  │
│              │                             │                 │
│              ▼                             ▼                 │
│   ┌──────────────────────────────────────────────────────┐   │
│   │              Google Gemini API (Internet)            │   │
│   └──────────────────────────────────────────────────────┘   │
│              │                             │                 │
│              ▼                             ▼                 │
│   ┌──────────────────────────────────────────────────────┐   │
│   │            SQLite — learning_platform.db             │   │
│   │            (volumen montado en contenedor)           │   │
│   └──────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
```

### Componentes mínimos

| Componente | Tecnología | Puerto | Obligatorio |
|---|---|---|---|
| API REST | FastAPI + Uvicorn (Docker) | 8000 | Sí |
| Frontend | Streamlit | 8501 | Sí |
| Base de datos | SQLite (archivo local) | — | Sí |
| IA | Google Gemini API | 443 (HTTPS) | Para funciones IA |

---

## Estimación de costos iniciales

### Supuestos
- Equipo de desarrollo de 3 personas
- Uso académico / prototipo (no producción)
- ~100 usuarios máximo simultáneos
- ~500 llamadas a Gemini por día

| Servicio | Plan | Costo/mes | Notas |
|---|---|---|---|
| Google Gemini API | Free tier (1,500 req/día) | $0 | Google AI Studio, sin tarjeta de crédito |
| Docker Desktop | Personal | $0 | Gratis para uso personal y educativo |
| Render (PaaS despliegue) | Free tier | $0 | Despliega contenedores gratis, se duerme tras 15 min de inactividad |
| GitHub Actions (CI/CD) | Free tier (2,000 min/mes) | $0 | Ya integrado en el proyecto |
| GitHub (repositorio) | Free | $0 | Repositorio público gratuito |
| SQLite (base de datos) | Incluido en Python | $0 | No requiere servidor externo |
| **Total actual (académico)** | **Solo free tiers** | **$0 USD** | Stack completamente gratuito |
| **Total para producción real** | **Alternativas gratuitas** | **$0 USD** | Suficiente para prototipo académico |

### Supuestos del plan gratuito
- Uso académico con menos de 100 usuarios simultáneos
- Menos de 1,500 llamadas diarias a Gemini (límite del free tier)
- El "sleep" de Render en inactividad es aceptable para un prototipo
- El repositorio es público en GitHub

### Alternativas gratuitas si se necesita más disponibilidad
- **Hugging Face Spaces** — despliega apps Python/Docker gratis sin sleep
- **Koyeb** — free tier con 1 servicio siempre activo, sin tarjeta de crédito
- **Fly.io** — free tier con 3 VMs pequeñas incluidas

---

## Variables de entorno requeridas

| Variable | Dónde configurar | Obligatoria | Descripción |
|---|---|---|---|
| `GEMINI_API_KEY` | `-e` en docker run / secrets en PaaS | Sí (para IA) | Clave de Google AI Studio |
| `TESTING` | `-e TESTING=true` | No | Activa modo test (sin Gemini real) |
| `DEBUG` | `-e DEBUG=false` | No | Modo debug de la aplicación |

**Cómo pasar la variable al contenedor:**
```bash
docker run -d -p 8000:8000 \
  -e GEMINI_API_KEY=tu_api_key_aqui \
  -e TESTING=false \
  --name eduia-api \
  eduia-api:1.0
```

---

## Riesgos técnicos pendientes

| # | Riesgo | Impacto | Plan de mitigación |
|---|---|---|---|
| 1 | SQLite no soporta múltiples instancias del contenedor | Alto | Migrar a PostgreSQL en semana 5-6 |
| 2 | Librería `google-generativeai` está deprecada (FutureWarning) | Medio | Migrar a `google.genai` en semana 5 |
| 3 | Sin HTTPS en el contenedor local | Medio | Agregar reverse proxy (Nginx) en despliegue real |
| 4 | Sin autenticación en endpoints de la API | Alto | Agregar API Key o JWT en semana 5 |
| 5 | Imagen Docker incluye dependencias pesadas (scikit-learn) | Bajo | Ya mitigado usando `requirements-test.txt` en el contenedor |
| 6 | Sin límite de rate en la API | Medio | Agregar rate limiting con slowapi en semana 5 |

---

## Comandos de referencia rápida

```bash
# Construir imagen
docker build -t eduia-api:1.0 .

# Ejecutar contenedor
docker run -d -p 8000:8000 -e GEMINI_API_KEY=tu_key --name eduia-api eduia-api:1.0

# Ver logs en tiempo real
docker logs -f eduia-api

# Probar /health
curl http://localhost:8000/health

# Probar endpoint principal /api/evaluate
curl -X POST http://localhost:8000/api/evaluate \
  -H "Content-Type: application/json" \
  -d "{\"code\": \"def suma(a,b): return a+b\", \"language\": \"python\"}"

# Detener y eliminar contenedor
docker stop eduia-api
docker rm eduia-api
```
