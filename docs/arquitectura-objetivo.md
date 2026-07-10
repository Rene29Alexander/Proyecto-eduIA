# Arquitectura Objetivo — EduIA

> Evolución planificada del sistema durante el Módulo 4 (Semanas 2 a 6)

---

## Objetivo general

Separar la lógica de IA del frontend, agregar pruebas automatizadas, contenerizar la aplicación, agregar observabilidad y documentar todo para una defensa técnica.

La arquitectura objetivo **no reemplaza** la actual de una vez — evoluciona gradualmente semana a semana.

---

## Separación de responsabilidades objetivo

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLIENTE (Navegador)                           │
│                    Streamlit (frontend)                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP / REST
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API REST — FastAPI                            │
│  /api/exam/generate    /api/chat/ask    /api/course/adapt        │
│  Endpoints documentados con contratos de entrada/salida          │
└───────────┬─────────────────────────────────────┬───────────────┘
            │                                     │
            ▼                                     ▼
┌─────────────────────┐               ┌─────────────────────────┐
│  Servicio IA         │               │  Base de datos           │
│  Google Gemini API   │               │  SQLite → PostgreSQL     │
│  Prompts versionados │               │  (o SQLite con pool)     │
└─────────────────────┘               └─────────────────────────┘
            │
            ▼
┌─────────────────────┐
│  Observabilidad      │
│  Logs estructurados  │
│  Métricas de uso IA  │
└─────────────────────┘
```

---

## Evolución por semana

### Semana 2 — API inteligente
- Crear una API REST con FastAPI
- Definir endpoints para las funciones de IA: generación de exámenes, chat, evaluación de código
- Documentar contratos de entrada/salida (qué recibe, qué devuelve cada endpoint)
- Separar la lógica de IA (`utils_ai.py`) del código de vista

**Resultado esperado:** Al menos un endpoint funcional llamado desde Streamlit.

---

### Semana 3 — Pruebas y automatización
- Escribir pruebas unitarias para las funciones de IA y la lógica de negocio
- Implementar pruebas de integración para los endpoints de la API
- Configurar un pipeline CI/CD básico (GitHub Actions o similar)
- Automatizar la ejecución de pruebas en cada commit

**Resultado esperado:** El proyecto corre pruebas automáticamente al hacer cambios.

---

### Semana 4 — Contenedor y despliegue
- Crear un `Dockerfile` para la aplicación
- Crear `docker-compose.yml` para levantar app + base de datos juntos
- Probar el despliegue local con Docker
- Preparar configuración para despliegue en la nube (Render, Railway o similar)

**Resultado esperado:** La aplicación corre en un contenedor reproducible en cualquier máquina.

---

### Semana 5 — Observabilidad y rendimiento
- Agregar logs estructurados (qué se llamó, cuándo, con qué resultado)
- Registrar métricas de uso de la IA (latencia, tokens usados, errores)
- Identificar cuellos de botella en las consultas a la base de datos
- Evaluar si SQLite es suficiente o se necesita migrar

**Resultado esperado:** El equipo puede ver qué está pasando en la aplicación en tiempo real.

---

### Semana 6 — Seguridad, documentación y defensa
- Revisar manejo de API keys y secretos
- Agregar validaciones de entrada en los endpoints
- Completar la documentación técnica
- Preparar la defensa técnica del proyecto

**Resultado esperado:** Aplicación documentada, segura y lista para ser defendida.

---

## Comparación: actual vs objetivo

| Aspecto | Estado actual | Estado objetivo |
|---|---|---|
| Interfaz | Streamlit mezclada con lógica | Streamlit solo como frontend, llama a API |
| Backend | Distribuido en archivos `views_*.py` | FastAPI con endpoints definidos |
| IA | Llamadas directas desde las vistas | Servicio de IA desacoplado con contrato |
| Base de datos | SQLite local, sin pool | SQLite con connection pool o PostgreSQL |
| Pruebas | Sin pruebas automatizadas | Pruebas unitarias + CI/CD |
| Despliegue | Solo local | Contenerizado con Docker |
| Logs | `print()` y errores genéricos | Logs estructurados con niveles |
| Seguridad | API key en archivo local | Variables de entorno + validaciones |
