#  INFORME TÉCNICO: SISTEMA DE RACHAS (STREAKS)

##  RESUMEN EJECUTIVO

El Sistema de Rachas es un componente clave del sistema de engagement diseñado para generar dependencia diaria en los usuarios de la plataforma educativa. Implementa un mecanismo de recompensa psicológica que incentiva el acceso diario mediante el seguimiento de días consecutivos de actividad.

**Objetivo Principal**: Incrementar la retención diaria de usuarios mediante gamificación de la constancia.

**Impacto Esperado**:
- +40-60% en engagement diario
- +30-50% en retención a 7 días
- +25-35% en tiempo promedio en plataforma

---

##  ARQUITECTURA DEL SISTEMA

### 1. Componentes Principales

#### 1.1 Base de Datos (`database_engagement.py`)

**Tabla: `user_streaks`**
```sql
CREATE TABLE user_streaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    current_streak INTEGER DEFAULT 0,        -- Racha actual en días
    longest_streak INTEGER DEFAULT 0,        -- Récord personal
    last_activity_date DATE,                 -- Última actividad registrada
    freeze_count INTEGER DEFAULT 0,          -- Congeladores disponibles
    total_days_active INTEGER DEFAULT 0,     -- Total de días activos
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
)
```

**Campos Clave**:
- `current_streak`: Días consecutivos actuales (se reinicia si se rompe)
- `longest_streak`: Mejor racha histórica del usuario
- `last_activity_date`: Fecha de última actividad (formato: YYYY-MM-DD)
- `freeze_count`: Número de "congeladores" disponibles para proteger la racha
- `total_days_active`: Contador acumulativo de días con actividad

#### 1.2 Gestor de Rachas (`engagement/streak_manager.py`)

**Clase: `StreakManager`**

Métodos principales:

1. **`initialize_user_streak(user_id)`**
   - Inicializa el registro de racha para un nuevo usuario
   - Valores iniciales: current_streak=0, longest_streak=0, last_activity_date=NULL
   - Usa `INSERT OR IGNORE` para evitar duplicados

2. **`update_streak(user_id)`**  MÉTODO PRINCIPAL
   - Se ejecuta automáticamente en cada login del usuario
   - Lógica de actualización:
     ```
     SI última_actividad == hoy:
         → No hacer nada (ya registrado)
     
     SI última_actividad == ayer:
         → current_streak += 1 (día consecutivo)
     
     SI última_actividad > 1 día atrás:
         → current_streak = 1 (racha rota, reiniciar)
     
     SI es primera actividad:
         → current_streak = 1 (iniciar racha)
     ```
   - Actualiza `longest_streak` si `current_streak` lo supera
   - Incrementa `total_days_active`
   - Dispara verificación de badges de racha

3. **`get_streak_info(user_id)`**
   - Retorna información completa de la racha del usuario
   - Calcula si la racha está "en riesgo" (>= 1 día sin actividad)
   - Retorna diccionario con:
     ```python
     {
         'current_streak': int,
         'longest_streak': int,
         'last_activity_date': str,
         'freeze_count': int,
         'total_days_active': int,
         'is_at_risk': bool
     }
     ```

4. **`use_freeze(user_id)`**
   - Permite al usuario "congelar" su racha por 1 día
   - Consume 1 congelador del inventario
   - Extiende `last_activity_date` por +1 día
   - Retorna (success: bool, message: str)

5. **`add_freeze(user_id, count=1)`**
   - Agrega congeladores al inventario del usuario
   - Usado como recompensa en la tienda o por logros

---

##  FLUJO DE FUNCIONAMIENTO

### Flujo Principal: Actualización de Racha en Login

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Usuario inicia sesión                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. main.py ejecuta: StreakManager.update_streak(username)  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. StreakManager verifica última actividad                 │
│    - Obtiene last_activity_date de BD                       │
│    - Compara con fecha actual                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Calcula nueva racha según lógica:                       │
│    • Mismo día → No cambios                                 │
│    • Día consecutivo → current_streak + 1                   │
│    • Más de 1 día → current_streak = 1 (reinicio)          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Actualiza BD:                                            │
│    - current_streak                                         │
│    - longest_streak (si aplica)                             │
│    - last_activity_date = hoy                               │
│    - total_days_active + 1                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. BadgeManager.check_streak_badges(user_id, streak)       │
│    - Verifica si alcanzó hitos: 7, 30, 100, 365 días       │
│    - Otorga badges correspondientes                         │
└─────────────────────────────────────────────────────────────┘
```

---

## INTEGRACIÓN EN INTERFAZ DE USUARIO

### Ubicación: Sidebar del Dashboard Estudiantil

**Archivo**: `views_student.py` (líneas 1182-1188)

```python
# Racha
streak_info = StreakManager.get_streak_info(u['username'])
if streak_info['is_at_risk'] and streak_info['current_streak'] > 0:
    st.sidebar.warning(f" Racha en riesgo: {streak_info['current_streak']} días")
else:
    st.sidebar.success(f" Racha: {streak_info['current_streak']} días")
```

**Estados Visuales**:

1. **Racha Activa** (verde):
   ```
    Racha: 15 días
   ```
   - Se muestra cuando el usuario tiene actividad reciente
   - Color verde indica estado saludable

2. **Racha en Riesgo** (amarillo/naranja):
   ```
     Racha en riesgo: 15 días
   ```
   - Se muestra cuando han pasado >= 1 día sin actividad
   - Alerta al usuario para que no pierda su progreso

3. **Sin Racha** (neutral):
   ```
    Racha: 0 días
   ```
   - Usuario nuevo o racha rota recientemente

---

##  SISTEMA DE RECOMPENSAS ASOCIADO

### Badges de Racha

**Definidos en**: `database_engagement.py` (líneas 410-413)

| Badge | Nombre | Requisito | Puntos | Rareza |
|-------|--------|-----------|--------|--------|
|  streak_7 | Semana Completa | 7 días consecutivos | 100 | Común |
|  streak_30 | Mes Imparable | 30 días consecutivos | 500 | Raro |
|  streak_100 | Centenario | 100 días consecutivos | 2000 | Épico |
|  streak_365 | Año Legendario | 365 días consecutivos | 10000 | Legendario |

**Verificación Automática**:
- Se ejecuta en cada actualización de racha
- `BadgeManager.check_streak_badges(user_id, current_streak)`
- Otorga badge + puntos automáticamente al alcanzar hito

### Notificaciones de Racha

**Archivo**: `utils_notifications.py` (líneas 503-519)

```python
def notify_study_streak(self, student_id, days_streak):
    """Notifica racha de estudio consecutiva"""
    if days_streak in [3, 7, 14, 30, 60, 100]:
        # Enviar notificación de logro
```

**Hitos de Notificación**: 3, 7, 14, 30, 60, 100 días

---

##  SISTEMA DE PROTECCIÓN: CONGELADORES

### Concepto

Los "congeladores de racha" (streak freezes) permiten al usuario proteger su racha cuando sabe que no podrá acceder a la plataforma.

### Funcionamiento

1. **Uso de Congelador**:
   - Usuario activa congelador antes de perder la racha
   - Extiende `last_activity_date` por +1 día
   - Consume 1 congelador del inventario
   - La racha se mantiene intacta

2. **Obtención de Congeladores**:
   - Compra en la tienda de recompensas
   - Recompensa por logros especiales
   - Eventos promocionales

3. **Límites**:
   - Máximo configurable por usuario
   - No se pueden usar retroactivamente (solo preventivo)

---

##  MÉTRICAS Y ANÁLISIS

### Datos Rastreados

1. **Por Usuario**:
   - Racha actual (current_streak)
   - Récord personal (longest_streak)
   - Total de días activos (total_days_active)
   - Congeladores disponibles (freeze_count)

2. **Agregados** (potencial para analytics):
   - Distribución de rachas en la plataforma
   - Tasa de retención por nivel de racha
   - Días promedio antes de romper racha
   - Efectividad de congeladores

### KPIs Sugeridos

- **Tasa de Retención D1**: % usuarios que regresan al día siguiente
- **Tasa de Retención D7**: % usuarios con racha >= 7 días
- **Racha Promedio**: Media de current_streak de usuarios activos
- **Tasa de Uso de Congeladores**: % usuarios que usan congeladores vs. pierden racha

---

##  IMPLEMENTACIÓN TÉCNICA

### Inicialización en Login

**Archivo**: `main.py` (líneas 184-186)

```python
from engagement import StreakManager, PointsManager

# Actualizar racha
StreakManager.update_streak(username)
```

**Momento de Ejecución**: Inmediatamente después de autenticación exitosa

### Manejo de Errores

```python
try:
    c.execute('''INSERT OR IGNORE INTO user_streaks ...''')
    conn.commit()
    return True
except Exception as e:
    print(f"Error inicializando racha: {e}")
    return False
```

- Usa `INSERT OR IGNORE` para evitar duplicados
- Captura excepciones y retorna False en caso de error
- Logs de error para debugging

### Optimizaciones

1. **Verificación de Día Actual**:
   ```python
   if last_activity == today:
       return True  # Salida temprana
   ```
   - Evita actualizaciones innecesarias si ya se registró hoy

2. **Transacciones Atómicas**:
   - Todas las operaciones en una sola transacción
   - `conn.commit()` al final para garantizar consistencia

3. **Índices de BD**:
   ```sql
   CREATE INDEX idx_user_streaks_user ON user_streaks(user_id)
   ```
   - Búsquedas rápidas por usuario

---

##  PSICOLOGÍA DEL ENGAGEMENT

### Principios Aplicados

1. **Aversión a la Pérdida**:
   - Perder una racha de 30 días duele más que ganar 30 días
   - Motiva al usuario a no romper la cadena

2. **Progreso Visible**:
   - Contador siempre visible en sidebar
   - Refuerzo positivo constante

3. **Hitos y Recompensas**:
   - Badges en 7, 30, 100, 365 días
   - Sensación de logro en cada hito

4. **Urgencia Temporal**:
   - "Racha en riesgo" crea urgencia
   - Empuja al usuario a actuar hoy

5. **Protección Opcional**:
   - Congeladores dan sensación de control
   - Reducen frustración por circunstancias inevitables

---

##  RESULTADOS ESPERADOS

### Métricas de Éxito

| Métrica | Baseline | Objetivo | Impacto |
|---------|----------|----------|---------|
| DAU (Daily Active Users) | 100% | 140-160% | +40-60% |
| Retención D7 | 100% | 130-150% | +30-50% |
| Tiempo en plataforma | 100% | 125-135% | +25-35% |
| Tasa de abandono | 100% | 70-85% | -15-30% |

### Comportamientos Esperados

1. **Usuarios Nuevos** (0-7 días):
   - Descubren el sistema de rachas
   - Primeros 3 días son críticos
   - Notificación en día 3 refuerza hábito

2. **Usuarios Establecidos** (7-30 días):
   - Racha se convierte en hábito
   - Alta probabilidad de continuar
   - Buscan alcanzar badge de 30 días

3. **Usuarios Veteranos** (30+ días):
   - Racha es parte de identidad
   - Muy baja probabilidad de abandono
   - Usan congeladores estratégicamente

---

##  MEJORAS FUTURAS

### Corto Plazo

1. **Dashboard de Racha**:
   - Página dedicada con estadísticas detalladas
   - Gráfico de racha histórica
   - Comparación con otros usuarios

2. **Recordatorios Inteligentes**:
   - Email/push notification si racha en riesgo
   - Personalizado según horario habitual del usuario

3. **Racha Social**:
   - Ver rachas de amigos/compañeros
   - Competencia amistosa

### Largo Plazo

1. **Rachas por Actividad**:
   - Racha de desafíos diarios
   - Racha de tareas completadas
   - Racha de exámenes aprobados

2. **Recompensas Dinámicas**:
   - Multiplicadores de puntos por racha alta
   - Acceso a contenido exclusivo
   - Descuentos en tienda

3. **Análisis Predictivo**:
   - ML para predecir riesgo de abandono
   - Intervenciones personalizadas
   - Optimización de notificaciones

---

##  CONCLUSIONES

### Fortalezas del Sistema

 **Implementación Robusta**: Manejo de casos edge, transacciones atómicas
 **Integración Completa**: Login automático, UI visible, badges conectados
 **Psicología Efectiva**: Aversión a pérdida + progreso visible + recompensas
 **Escalable**: Diseño permite extensiones futuras sin refactorización

### Impacto en Engagement

El sistema de rachas es el componente más efectivo para generar dependencia diaria porque:

1. **Crea Hábito**: Acceso diario se convierte en rutina
2. **Genera Compromiso**: Usuarios invierten emocionalmente en su racha
3. **Reduce Abandono**: Aversión a perder progreso mantiene usuarios activos
4. **Aumenta Valor de Vida**: Usuarios con racha alta tienen mayor LTV

### Recomendaciones

1. **Monitorear Métricas**: Implementar analytics para validar hipótesis
2. **A/B Testing**: Probar diferentes umbrales de badges y recompensas
3. **Feedback de Usuarios**: Encuestas para entender motivaciones
4. **Iteración Continua**: Ajustar sistema según datos reales

---

##  REFERENCIAS TÉCNICAS

### Archivos Clave

- `engagement/streak_manager.py` - Lógica principal
- `database_engagement.py` - Esquema de BD
- `views_student.py` - Integración UI
- `main.py` - Inicialización en login
- `utils_notifications.py` - Notificaciones de racha

### Dependencias

- `datetime` - Manejo de fechas
- `database.db_manager` - Conexión a BD
- `engagement.badge_manager` - Verificación de badges
- `engagement.points_manager` - Sistema de puntos

---

**Fecha de Informe**: 2026
**Versión del Sistema**: 1.0
**Estado**:  Implementado y Funcional
