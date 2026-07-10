#  Riesgos Técnicos y Deuda Técnica — EduIA

> Identificación honesta de riesgos y problemas conocidos del proyecto.

---

## Tabla de riesgos

| # | Categoría | Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|---|---|
| 1 | **Modelo / IA** | La API de Gemini no responde o devuelve JSON malformado | Alta | Alto | Reintentos automáticos, validación del formato, mensaje de error claro al usuario |
| 2 | **Modelo / IA** | Gemini genera menos preguntas de las solicitadas | Alta | Medio | Segunda llamada para completar preguntas faltantes (ya implementado parcialmente) |
| 3 | **Dependencias** | Sin internet no funciona ninguna función de IA | Alta | Alto | Mostrar mensaje claro; en futuro, caché de respuestas frecuentes |
| 4 | **Datos** | SQLite no soporta múltiples usuarios simultáneos en producción | Media | Alto | Migrar a PostgreSQL en Semana 4 o usar connection pooling |
| 5 | **Datos** | La base de datos local se puede perder o corromper | Media | Alto | Sistema de backups automáticos ya implementado; migrar a nube en semanas 4-5 |
| 6 | **Código** | Frontend y backend mezclados dificultan el mantenimiento | Alta | Medio | Separar lógica en Semana 2 al crear la API REST |
| 7 | **Código** | Archivos de vista muy grandes (+8000 líneas en views_student.py) | Alta | Medio | Refactorizar gradualmente en módulos más pequeños |
| 8 | **Configuración** | API key expuesta si se sube el repositorio sin revisar | Media | Muy Alto | `.gitignore` incluye `secrets.toml`; agregar `.env.example` como guía |
| 9 | **Seguridad** | Sin autenticación por tokens (solo sesión en memoria de Streamlit) | Media | Alto | Implementar JWT o middleware de autenticación en la API de Semana 2 |
| 10 | **Despliegue** | La aplicación no tiene Dockerfile ni configuración de nube | Alta | Medio | Crear Dockerfile en Semana 4 |
| 11 | **Equipo** | Dependencia de un solo desarrollador que conoce todo el código | Media | Alto | Documentar el código y distribuir conocimiento entre el equipo |
| 12 | **Código** | Sin pruebas automatizadas que cubran las funciones principales | Alta | Medio | Implementar en Semana 3 como parte del plan de mejora |

---

## Deuda técnica identificada

###  Crítica (bloquea avance)
- Los imports de `views_admin.py` y `views_teacher.py` en `main.py` deben actualizarse tras el movimiento a `app/`
- Sin pruebas automatizadas — cualquier cambio puede romper funcionalidades sin saberlo

###  Media (afecta calidad)
- Frontend y backend mezclados en los mismos archivos
- Archivos de vista muy extensos (difíciles de mantener)
- Sin manejo estructurado de logs (solo `print()` y `try/except` genéricos)
- La generación de exámenes con IA no garantiza el número exacto de preguntas

###  Baja (mejora eventual)
- Sin documentación de API (no hay contratos de entrada/salida documentados)
- Sin versión móvil
- Sin sistema de reportes avanzados para el administrador
- Embeddings o memoria de conversación no implementados en el chat IA

---

## Dependencias técnicas actuales

| Dependencia | Versión | Propósito | Riesgo |
|---|---|---|---|
| `streamlit` | ≥1.28.0 | Interfaz web | Bajo |
| `google-generativeai` | ≥0.3.0 | API de Gemini | Medio (depende de Google) |
| `bcrypt` | ≥4.0.0 | Hash de contraseñas | Bajo |
| `pandas` | ≥2.0.0 | Procesamiento de datos | Bajo |
| `openpyxl` | ≥3.1.0 | Exportación Excel | Bajo |
| `pypdf` | ≥3.0.0 | Extracción de texto de PDFs | Bajo |
| `scikit-learn` | 1.5.2 | Recomendaciones | Bajo |
| `Pillow` | ≥10.0.0 | Procesamiento de imágenes | Bajo |

---

## Datos, archivos y credenciales necesarios

| Recurso | Dónde | Obligatorio |
|---|---|---|
| API Key de Google Gemini | `.streamlit/secrets.toml` |  Sí (para funciones IA) |
| Base de datos | `learning_platform.db` (se crea automáticamente) |  Sí |
| Python 3.11+ | Sistema operativo |  Sí |
| Conexión a internet | Red | Solo para funciones de IA |
