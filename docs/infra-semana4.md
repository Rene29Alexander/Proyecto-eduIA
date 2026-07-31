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

| Servicio | Plan | Costo estimado/mes | Notas |
|---|---|---|---|
| Google Gemini API | Free tier | $0 | Hasta 1,500 req/día gratis |
| Docker Desktop | Personal | $0 | Gratis para uso personal/educativo |
| Railway (PaaS alternativo) | Hobby | $5 USD | 512 MB RAM, suficiente para la API |
| Render (PaaS alternativo) | Free | $0 | Con limitación de sleep en inactividad |
| VPS mínimo (DigitalOcean) | $4/mes | $4 USD | 512 MB RAM, 10 GB SSD |
| **Total mínimo** | | **$0 USD** | Solo con free tiers |
| **Total recomendado** | | **~$5–9 USD/mes** | Con Railway o VPS básico |

### Conclusión de costos
Para el contexto académico actual, el costo es **$0** usando:
- Docker local en equipo del grupo
- Google Gemini Free tier
- GitHub para repositorio

Para un despliegue real en producción se recomienda Railway ($5/mes) o un VPS
básico ($4–6/mes).

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
