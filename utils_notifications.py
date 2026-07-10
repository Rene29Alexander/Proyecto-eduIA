"""
Sistema de notificaciones para la plataforma
"""

import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from database import db_manager
import json

class NotificationManager:
    """Gestor de notificaciones del sistema"""
    
    def __init__(self):
        self.conn = db_manager.get_connection()
    
    def create_notification(self, user_id, title, message, notification_type='info', link=None):
        """Crea una nueva notificación (versión simplificada)"""
        try:
            # Validación básica
            if not user_id or not title or not message:
                return False
            
            # Limitar longitud
            title = str(title)[:100]
            message = str(message)[:500]
            
            self.conn.execute('''
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, title, message, notification_type, link))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error de BD creando notificación: {e}")
            return False
        except Exception as e:
            print(f"Error inesperado creando notificación: {e}")
            return False
    
    def get_user_notifications(self, user_id, unread_only=True, limit=20):
        """Obtiene notificaciones del usuario"""
        query = '''
            SELECT * FROM notifications 
            WHERE user_id = ?
        '''
        
        if unread_only:
            query += " AND is_read = 0"
        
        query += " ORDER BY created_at DESC LIMIT ?"
        
        try:
            return self.conn.execute(query, (user_id, limit)).fetchall()
        except:
            return []
    
    def mark_as_read(self, notification_id, user_id=None):
        """Marca notificación como leída"""
        try:
            if user_id:
                self.conn.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
                    (notification_id, user_id)
                )
            else:
                self.conn.execute(
                    "UPDATE notifications SET is_read = 1 WHERE id = ?",
                    (notification_id,)
                )
            self.conn.commit()
            return True
        except:
            return False
    
    def mark_all_as_read(self, user_id):
        """Marca todas las notificaciones como leídas"""
        try:
            self.conn.execute(
                "UPDATE notifications SET is_read = 1 WHERE user_id = ?",
                (user_id,)
            )
            self.conn.commit()
            return True
        except:
            return False
    
    def get_unread_count(self, user_id):
        """Obtiene conteo de notificaciones no leídas"""
        try:
            result = self.conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,)
            ).fetchone()
            return result[0] if result else 0
        except:
            return 0
    
    def create_assignment_notification(self, course_id, task_title, due_date=None):
        """Crea notificación de nueva tarea para todos los estudiantes del curso"""
        try:
            # Obtener todos los estudiantes del curso
            students = self.conn.execute('''
                SELECT u.username FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ? AND u.role = 'student'
            ''', (course_id,)).fetchall()
            
            for student in students:
                message = f"Nueva tarea: {task_title}"
                if due_date:
                    message += f" - Vence: {due_date}"
                
                self.create_notification(
                    user_id=student['username'],
                    title="📝 Nueva Tarea",
                    message=message,
                    notification_type='assignment',
                    link=f"?course={course_id}&task={task_title}"
                )
            
            return len(students)
        except Exception as e:
            print(f"Error creando notificaciones de tarea: {e}")
            return 0
    
    def create_exam_notification(self, course_id, exam_title, start_date=None):
        """Crea notificación de nuevo examen"""
        try:
            students = self.conn.execute('''
                SELECT u.username FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ? AND u.role = 'student'
            ''', (course_id,)).fetchall()
            
            for student in students:
                message = f"Nuevo examen: {exam_title}"
                if start_date:
                    message += f" - Disponible desde: {start_date}"
                
                self.create_notification(
                    user_id=student['username'],
                    title="✅ Nuevo Examen",
                    message=message,
                    notification_type='exam',
                    link=f"?course={course_id}&exam={exam_title}"
                )
            
            return len(students)
        except Exception as e:
            print(f"Error creando notificaciones de examen: {e}")
            return 0
    
    def notify_task_submission(self, task_id, student_id, course_id):
        """Notifica al profesor cuando un estudiante entrega una tarea"""
        try:
            # Obtener información de la tarea
            task = self.conn.execute(
                "SELECT title FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            
            # Obtener información del estudiante
            student = self.conn.execute(
                "SELECT full_name FROM users WHERE username = ?", (student_id,)
            ).fetchone()
            
            # Obtener profesor del curso
            teacher = self.conn.execute('''
                SELECT teacher_id FROM courses WHERE id = ?
            ''', (course_id,)).fetchone()
            
            if task and student and teacher:
                self.create_notification(
                    user_id=teacher['teacher_id'],
                    title="📝 Nueva Entrega de Tarea",
                    message=f"{student['full_name']} ha entregado la tarea '{task['title']}'",
                    notification_type='submission',
                    link=f"?course={course_id}&task={task_id}"
                )
                return True
            return False
        except Exception as e:
            print(f"Error notificando entrega de tarea: {e}")
            return False
    
    def notify_exam_submission(self, exam_id, student_id, course_id, score=None):
        """Notifica al profesor cuando un estudiante completa un examen"""
        try:
            # Obtener información del examen
            exam = self.conn.execute(
                "SELECT title FROM exams WHERE id = ?", (exam_id,)
            ).fetchone()
            
            # Obtener información del estudiante
            student = self.conn.execute(
                "SELECT full_name FROM users WHERE username = ?", (student_id,)
            ).fetchone()
            
            # Obtener profesor del curso
            teacher = self.conn.execute(
                "SELECT teacher_id FROM courses WHERE id = ?", (course_id,)
            ).fetchone()
            
            if exam and student and teacher:
                message = f"{student['full_name']} ha completado el examen '{exam['title']}'"
                if score is not None:
                    message += f" - Puntuación: {score}"
                
                self.create_notification(
                    user_id=teacher['teacher_id'],
                    title="✅ Examen Completado",
                    message=message,
                    notification_type='submission',
                    link=f"?course={course_id}&exam={exam_id}"
                )
                return True
            return False
        except Exception as e:
            print(f"Error notificando entrega de examen: {e}")
            return False
    
    def notify_grade_posted(self, student_id, task_id, grade, feedback=None):
        """Notifica al estudiante cuando recibe una calificación"""
        try:
            # Obtener información de la tarea
            task = self.conn.execute(
                "SELECT title, points FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
            
            if task:
                message = f"Has recibido {grade}/{task['points']} puntos en '{task['title']}'"
                if feedback:
                    message += f" - Comentario: {feedback[:100]}"
                
                self.create_notification(
                    user_id=student_id,
                    title="📊 Nueva Calificación",
                    message=message,
                    notification_type='grade',
                    link=f"?task={task_id}"
                )
                return True
            return False
        except Exception as e:
            print(f"Error notificando calificación: {e}")
            return False
    
    def notify_new_module(self, course_id, module_title):
        """Notifica a estudiantes sobre nuevo módulo/contenido"""
        try:
            students = self.conn.execute('''
                SELECT u.username FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ? AND u.role = 'student'
            ''', (course_id,)).fetchall()
            
            for student in students:
                self.create_notification(
                    user_id=student['username'],
                    title="📚 Nuevo Contenido Disponible",
                    message=f"Se ha publicado nuevo contenido: {module_title}",
                    notification_type='content',
                    link=f"?course={course_id}"
                )
            
            return len(students)
        except Exception as e:
            print(f"Error notificando nuevo módulo: {e}")
            return 0
    
    def notify_new_material(self, course_id, material_title, module_title):
        """Notifica sobre nuevo material de estudio"""
        try:
            students = self.conn.execute('''
                SELECT u.username FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ? AND u.role = 'student'
            ''', (course_id,)).fetchall()
            
            for student in students:
                self.create_notification(
                    user_id=student['username'],
                    title="📄 Nuevo Material de Estudio",
                    message=f"Material '{material_title}' agregado en {module_title}",
                    notification_type='content',
                    link=f"?course={course_id}"
                )
            
            return len(students)
        except Exception as e:
            print(f"Error notificando nuevo material: {e}")
            return 0
    
    def notify_ai_course_enrollment(self, student_id, course_title):
        """Notifica cuando un estudiante se inscribe en un curso IA"""
        try:
            self.create_notification(
                user_id=student_id,
                title="🤖 Inscripción a Curso IA",
                message=f"Te has inscrito exitosamente en '{course_title}'. ¡Comienza tu aprendizaje personalizado!",
                notification_type='enrollment',
                link="?view=ai_course"
            )
            return True
        except Exception as e:
            print(f"Error notificando inscripción IA: {e}")
            return False
    
    def notify_course_enrollment(self, student_id, course_name):
        """Notifica cuando un estudiante se inscribe en un curso regular"""
        try:
            self.create_notification(
                user_id=student_id,
                title="📚 Inscripción a Curso",
                message=f"Te has inscrito exitosamente en '{course_name}'. Accede al contenido desde tu dashboard.",
                notification_type='enrollment'
            )
            return True
        except Exception as e:
            print(f"Error notificando inscripción: {e}")
            return False
    
    def notify_forum_reply(self, original_author, replier_name, topic_title, course_id):
        """Notifica cuando alguien responde a un mensaje del foro"""
        try:
            self.create_notification(
                user_id=original_author,
                title="💬 Nueva Respuesta en Foro",
                message=f"{replier_name} ha respondido a tu mensaje en '{topic_title}'",
                notification_type='forum',
                link=f"?course={course_id}&forum=true"
            )
            return True
        except Exception as e:
            print(f"Error notificando respuesta de foro: {e}")
            return False
    
    def notify_forum_mention(self, mentioned_user, mentioner_name, topic_title, course_id):
        """Notifica cuando alguien menciona a un usuario en el foro"""
        try:
            self.create_notification(
                user_id=mentioned_user,
                title="💬 Te Mencionaron en el Foro",
                message=f"{mentioner_name} te mencionó en '{topic_title}'",
                notification_type='forum',
                link=f"?course={course_id}&forum=true"
            )
            return True
        except Exception as e:
            print(f"Error notificando mención: {e}")
            return False
    
    def notify_deadline_reminder(self, student_id, task_title, days_remaining):
        """Notifica recordatorio de fecha límite próxima"""
        try:
            if days_remaining == 1:
                message = f"⚠️ La tarea '{task_title}' vence mañana. ¡No olvides entregarla!"
            elif days_remaining == 0:
                message = f"🚨 La tarea '{task_title}' vence HOY. ¡Última oportunidad!"
            else:
                message = f"La tarea '{task_title}' vence en {days_remaining} días"
            
            self.create_notification(
                user_id=student_id,
                title="⏰ Recordatorio de Entrega",
                message=message,
                notification_type='reminder'
            )
            return True
        except Exception as e:
            print(f"Error notificando recordatorio: {e}")
            return False
    
    def notify_exam_reminder(self, student_id, exam_title, hours_remaining):
        """Notifica recordatorio de examen próximo"""
        try:
            if hours_remaining <= 24:
                message = f"⚠️ El examen '{exam_title}' estará disponible en {hours_remaining} horas"
            else:
                days = hours_remaining // 24
                message = f"El examen '{exam_title}' estará disponible en {days} días"
            
            self.create_notification(
                user_id=student_id,
                title="⏰ Recordatorio de Examen",
                message=message,
                notification_type='reminder'
            )
            return True
        except Exception as e:
            print(f"Error notificando recordatorio de examen: {e}")
            return False
    
    def notify_course_completion(self, student_id, course_name, final_grade):
        """Notifica cuando un estudiante completa un curso"""
        try:
            message = f"¡Felicidades! Has completado '{course_name}' con una calificación final de {final_grade}%"
            
            self.create_notification(
                user_id=student_id,
                title="🎓 Curso Completado",
                message=message,
                notification_type='achievement'
            )
            return True
        except Exception as e:
            print(f"Error notificando completación de curso: {e}")
            return False
    
    def notify_ai_course_progress(self, student_id, course_title, progress_percent):
        """Notifica progreso en curso IA"""
        try:
            milestones = [25, 50, 75, 100]
            
            for milestone in milestones:
                if abs(progress_percent - milestone) < 1:  # Cerca del hito
                    if milestone == 100:
                        message = f"🎉 ¡Has completado el 100% de '{course_title}'! ¡Excelente trabajo!"
                    else:
                        message = f"¡Has alcanzado el {milestone}% de progreso en '{course_title}'! Sigue así."
                    
                    self.create_notification(
                        user_id=student_id,
                        title=f"📈 Progreso: {milestone}%",
                        message=message,
                        notification_type='progress'
                    )
                    return True
            
            return False
        except Exception as e:
            print(f"Error notificando progreso: {e}")
            return False
    
    def notify_feedback_received(self, student_id, task_title, teacher_name):
        """Notifica cuando el profesor deja retroalimentación"""
        try:
            self.create_notification(
                user_id=student_id,
                title="💬 Nueva Retroalimentación",
                message=f"{teacher_name} ha dejado comentarios en tu tarea '{task_title}'",
                notification_type='feedback'
            )
            return True
        except Exception as e:
            print(f"Error notificando retroalimentación: {e}")
            return False
    
    def notify_resubmission_allowed(self, student_id, task_title, attempts_remaining):
        """Notifica cuando se permite reenvío de tarea"""
        try:
            message = f"Puedes reenviar la tarea '{task_title}'. Intentos restantes: {attempts_remaining}"
            
            self.create_notification(
                user_id=student_id,
                title="🔄 Reenvío Permitido",
                message=message,
                notification_type='info'
            )
            return True
        except Exception as e:
            print(f"Error notificando reenvío: {e}")
            return False
    
    def notify_class_announcement(self, course_id, announcement_title, announcement_text):
        """Notifica anuncio importante del curso"""
        try:
            students = self.conn.execute('''
                SELECT u.username FROM users u
                JOIN enrollments e ON u.username = e.student_id
                WHERE e.course_id = ? AND u.role = 'student'
            ''', (course_id,)).fetchall()
            
            for student in students:
                self.create_notification(
                    user_id=student['username'],
                    title=f"📢 Anuncio: {announcement_title}",
                    message=announcement_text[:200],
                    notification_type='announcement',
                    link=f"?course={course_id}"
                )
            
            return len(students)
        except Exception as e:
            print(f"Error notificando anuncio: {e}")
            return 0
    
    def notify_peer_achievement(self, student_id, peer_name, achievement_description):
        """Notifica logros de compañeros para motivación"""
        try:
            self.create_notification(
                user_id=student_id,
                title="🌟 Logro de Compañero",
                message=f"{peer_name} {achievement_description}. ¡Tú también puedes lograrlo!",
                notification_type='social'
            )
            return True
        except Exception as e:
            print(f"Error notificando logro de compañero: {e}")
            return False
    
    def notify_study_streak(self, student_id, days_streak):
        """Notifica racha de estudio consecutiva"""
        try:
            if days_streak in [3, 7, 14, 30, 60, 100]:
                message = f"🔥 ¡Increíble! Llevas {days_streak} días consecutivos estudiando. ¡Sigue así!"
                
                self.create_notification(
                    user_id=student_id,
                    title=f"🔥 Racha de {days_streak} Días",
                    message=message,
                    notification_type='achievement'
                )
                return True
            return False
        except Exception as e:
            print(f"Error notificando racha: {e}")
            return False
    
    def create_welcome_notifications(self, user_id, user_role='student'):
        """Crea notificaciones de bienvenida con información sobre funciones disponibles"""
        try:
            # Notificaciones base para todos los usuarios
            base_notifications = [
                {
                    'title': '🎉 ¡Bienvenido a la Plataforma!',
                    'message': 'Explora todas las funciones disponibles. Revisa tus notificaciones para conocer las características.',
                    'type': 'welcome'
                },
                {
                    'title': '🔔 Sistema de Notificaciones',
                    'message': 'Recibirás notificaciones sobre nuevas tareas, exámenes, calificaciones y funciones disponibles.',
                    'type': 'info'
                }
            ]
            
            # Notificaciones específicas para estudiantes
            if user_role == 'student':
                student_notifications = [
                    {
                        'title': '📚 Mis Cursos',
                        'message': 'Accede a todos tus cursos regulares y cursos IA personalizados desde el dashboard principal.',
                        'type': 'feature'
                    },
                    {
                        'title': '🤖 Academia Personal IA',
                        'message': 'Crea cursos personalizados con IA. Evalúa tu nivel y genera contenido adaptado a tus necesidades.',
                        'type': 'feature'
                    },
                    {
                        'title': '💻 Evaluador de Código IA',
                        'message': 'Evalúa tu código en tiempo real con IA. Soporta Python, Java, C++, JavaScript, SQL, NoSQL y HTML/CSS.',
                        'type': 'feature'
                    },
                    {
                        'title': '🆘 Asistente de Errores IA',
                        'message': 'Obtén ayuda específica para resolver errores en tu código con explicaciones detalladas.',
                        'type': 'feature'
                    },
                    {
                        'title': '💡 Generador de Soluciones IA',
                        'message': 'Solicita soluciones completas para ejercicios cuando necesites ayuda adicional.',
                        'type': 'feature'
                    },
                    {
                        'title': '🎯 Desafíos Personalizados IA',
                        'message': 'Genera desafíos únicos adaptados a tu nivel para practicar y mejorar tus habilidades.',
                        'type': 'feature'
                    },
                    {
                        'title': '📊 Historial de Actividades',
                        'message': 'Revisa tu progreso, calificaciones y estadísticas de rendimiento en todas las actividades.',
                        'type': 'feature'
                    },
                    {
                        'title': '💬 Foro de Discusión',
                        'message': 'Participa en discusiones con otros estudiantes y profesores. Comparte dudas y conocimientos.',
                        'type': 'feature'
                    },
                    {
                        'title': '📝 Tareas y Exámenes',
                        'message': 'Completa tareas, realiza exámenes y recibe retroalimentación automática de tus envíos.',
                        'type': 'feature'
                    },
                    {
                        'title': '📈 Progreso en Tiempo Real',
                        'message': 'Monitorea tu progreso en cursos IA con métricas detalladas y recomendaciones personalizadas.',
                        'type': 'feature'
                    }
                ]
                base_notifications.extend(student_notifications)
            
            # Notificaciones específicas para profesores
            elif user_role == 'teacher':
                teacher_notifications = [
                    {
                        'title': '👨‍🏫 Panel de Profesor',
                        'message': 'Gestiona tus cursos, crea contenido, asigna tareas y monitorea el progreso de estudiantes.',
                        'type': 'feature'
                    },
                    {
                        'title': '📋 Gestión de Cursos',
                        'message': 'Crea y edita cursos, módulos, lecciones. Organiza el contenido de manera estructurada.',
                        'type': 'feature'
                    },
                    {
                        'title': '✅ Sistema de Evaluación',
                        'message': 'Crea exámenes, asigna tareas y califica automáticamente con IA o manualmente.',
                        'type': 'feature'
                    },
                    {
                        'title': '📊 Análisis de Rendimiento',
                        'message': 'Revisa estadísticas detalladas del rendimiento de tus estudiantes y cursos.',
                        'type': 'feature'
                    },
                    {
                        'title': '💬 Moderación de Foro',
                        'message': 'Modera discusiones, responde preguntas y guía las conversaciones en el foro.',
                        'type': 'feature'
                    }
                ]
                base_notifications.extend(teacher_notifications)
            
            # Notificaciones específicas para administradores
            elif user_role == 'admin':
                admin_notifications = [
                    {
                        'title': '⚙️ Panel de Administración',
                        'message': 'Gestiona usuarios, cursos, configuraciones del sistema y monitorea la plataforma.',
                        'type': 'feature'
                    },
                    {
                        'title': '👥 Gestión de Usuarios',
                        'message': 'Crea, edita y administra cuentas de estudiantes, profesores y otros administradores.',
                        'type': 'feature'
                    },
                    {
                        'title': '🏫 Gestión Institucional',
                        'message': 'Configura cursos, inscripciones, períodos académicos y estructura organizacional.',
                        'type': 'feature'
                    },
                    {
                        'title': '📈 Reportes del Sistema',
                        'message': 'Accede a reportes completos de uso, rendimiento y estadísticas de la plataforma.',
                        'type': 'feature'
                    },
                    {
                        'title': '🔧 Configuración Avanzada',
                        'message': 'Configura parámetros del sistema, integraciones IA y opciones de personalización.',
                        'type': 'feature'
                    }
                ]
                base_notifications.extend(admin_notifications)
            
            # Crear todas las notificaciones
            created_count = 0
            for notif in base_notifications:
                if self.create_notification(
                    user_id=user_id,
                    title=notif['title'],
                    message=notif['message'],
                    notification_type=notif['type']
                ):
                    created_count += 1
            
            return created_count
            
        except Exception as e:
            print(f"Error creando notificaciones de bienvenida: {e}")
            return 0
    
    def create_feature_update_notification(self, title, message, target_role=None):
        """Crea notificación sobre nuevas funciones o actualizaciones"""
        try:
            # Si no se especifica rol, enviar a todos los usuarios
            if target_role:
                users = self.conn.execute(
                    "SELECT username FROM users WHERE role = ?", (target_role,)
                ).fetchall()
            else:
                users = self.conn.execute("SELECT username FROM users").fetchall()
            
            created_count = 0
            for user in users:
                if self.create_notification(
                    user_id=user['username'],
                    title=f"🆕 {title}",
                    message=message,
                    notification_type='update'
                ):
                    created_count += 1
            
            return created_count
            
        except Exception as e:
            print(f"Error creando notificaciones de actualización: {e}")
            return 0
    
    def create_tip_notification(self, user_id, tip_title, tip_message):
        """Crea notificación con consejos de uso"""
        return self.create_notification(
            user_id=user_id,
            title=f"💡 Consejo: {tip_title}",
            message=tip_message,
            notification_type='tip'
        )
    
    def notify_new_message(
        self, 
        recipient_id: str, 
        sender_name: str, 
        message_preview: str, 
        conversation_id: int, 
        has_attachment: bool = False
    ) -> bool:
        """
        Crea notificación de nuevo mensaje de chat.
        
        Args:
            recipient_id: Username del destinatario
            sender_name: Nombre completo del remitente
            message_preview: Primeros 100 caracteres del mensaje
            conversation_id: ID de la conversación
            has_attachment: Indica si el mensaje tiene archivo adjunto
            
        Returns:
            True si se creó la notificación exitosamente
        """
        try:
            # Truncar preview a 100 caracteres
            preview = message_preview[:100]
            if len(message_preview) > 100:
                preview += "..."
            
            # Agregar indicador de adjunto si aplica
            if has_attachment:
                preview += " 📎"
            
            # Crear notificación
            return self.create_notification(
                user_id=recipient_id,
                title=f"💬 Mensaje de {sender_name}",
                message=preview,
                notification_type='chat',
                link=f"?chat=true&conversation={conversation_id}"
            )
            
        except Exception as e:
            print(f"Error creando notificación de chat: {e}")
            return False
    
    def create_achievement_notification(self, user_id, achievement_title, achievement_message):
        """Crea notificación de logro o reconocimiento"""
        return self.create_notification(
            user_id=user_id,
            title=f"🏆 Logro: {achievement_title}",
            message=achievement_message,
            notification_type='achievement'
        )
    
    def send_daily_tips(self):
        """Envía consejos diarios a usuarios activos"""
        tips = [
            {
                'title': 'Evaluador de Código',
                'message': 'Usa el evaluador IA para obtener retroalimentación instantánea sobre tu código antes de enviarlo.'
            },
            {
                'title': 'Academia Personal IA',
                'message': 'Crea cursos personalizados que se adapten a tu ritmo y nivel de conocimiento.'
            },
            {
                'title': 'Desafíos Diarios',
                'message': 'Genera un nuevo desafío cada día para mantener tus habilidades afiladas.'
            },
            {
                'title': 'Foro de Discusión',
                'message': 'Participa en el foro para resolver dudas y ayudar a otros estudiantes.'
            },
            {
                'title': 'Historial de Progreso',
                'message': 'Revisa tu historial para identificar áreas de mejora y celebrar tus logros.'
            }
        ]
        
        try:
            # Obtener usuarios activos (que han iniciado sesión en los últimos 7 días)
            active_users = self.conn.execute("""
                SELECT DISTINCT username FROM users 
                WHERE role = 'student' AND last_login > datetime('now', '-7 days')
            """).fetchall()
            
            import random
            tip = random.choice(tips)
            
            created_count = 0
            for user in active_users:
                if self.create_tip_notification(
                    user_id=user['username'],
                    tip_title=tip['title'],
                    tip_message=tip['message']
                ):
                    created_count += 1
            
            return created_count
            
        except Exception as e:
            print(f"Error enviando consejos diarios: {e}")
            return 0
    
    def render_notification_bell(self):
        """Renderiza campana de notificaciones en la interfaz"""
        if not st.session_state.get('logged_in'):
            return
        
        user_id = st.session_state.user['username']
        unread_count = self.get_unread_count(user_id)
        
        col1, col2 = st.columns([10, 1])
        with col2:
            st.markdown(f"🔔 {unread_count}")
            
            if st.button("🔔", key="notif_bell"):
                st.session_state.show_notifications = True
            
            if st.session_state.get('show_notifications'):
                self.render_notifications_sidebar()

    def render_notifications_sidebar(self):
        """Renderiza panel de notificaciones en sidebar"""
        with st.sidebar:
            st.markdown("### 🔔 Notificaciones")
            
            user_id = st.session_state.user['username']
            notifications = self.get_user_notifications(user_id, unread_only=False, limit=15)
            
            if not notifications:
                st.info("No hay notificaciones")
            else:
                unread_count = sum(1 for n in notifications if not n['is_read'])
                
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**{len(notifications)}** notificaciones")
                with col2:
                    if unread_count > 0 and st.button("✓ Todas", key="mark_all_read"):
                        self.mark_all_as_read(user_id)
                        st.rerun()
                
                # Filtros de tipo
                filter_type = st.selectbox(
                    "Filtrar por tipo:",
                    ["Todas", "Bienvenida", "Funciones", "Tareas", "Exámenes", "Entregas", 
                     "Calificaciones", "Contenido", "Inscripciones", "Foro", "Recordatorios",
                     "Progreso", "Retroalimentación", "Anuncios", "Consejos", "Logros", "Actualizaciones"],
                    key="notif_filter"
                )
                
                # Filtrar notificaciones
                filtered_notifications = notifications
                if filter_type != "Todas":
                    type_mapping = {
                        "Bienvenida": "welcome",
                        "Funciones": "feature", 
                        "Tareas": "assignment",
                        "Exámenes": "exam",
                        "Entregas": "submission",
                        "Calificaciones": "grade",
                        "Contenido": "content",
                        "Inscripciones": "enrollment",
                        "Foro": "forum",
                        "Recordatorios": "reminder",
                        "Progreso": "progress",
                        "Retroalimentación": "feedback",
                        "Anuncios": "announcement",
                        "Consejos": "tip",
                        "Logros": "achievement",
                        "Actualizaciones": "update"
                    }
                    target_type = type_mapping.get(filter_type, "info")
                    filtered_notifications = [n for n in notifications if n['type'] == target_type]
                
                # Mostrar notificaciones
                for notification in filtered_notifications:
                    self._render_notification_card(notification)

    def _render_notification_card(self, notification):
        """Renderiza una tarjeta de notificación individual"""
        # Colores y iconos por tipo
        type_config = {
            'welcome': {'color': '#4CAF50', 'icon': '🎉'},
            'feature': {'color': '#2196F3', 'icon': '⭐'},
            'assignment': {'color': '#FF9800', 'icon': '📝'},
            'exam': {'color': '#9C27B0', 'icon': '✅'},
            'tip': {'color': '#00BCD4', 'icon': '💡'},
            'achievement': {'color': '#FFD700', 'icon': '🏆'},
            'update': {'color': '#8BC34A', 'icon': '🆕'},
            'info': {'color': '#607D8B', 'icon': '🔔'},
            'success': {'color': '#4CAF50', 'icon': '✅'},
            'warning': {'color': '#FF5722', 'icon': '⚠️'},
            'submission': {'color': '#3F51B5', 'icon': '📬'},
            'grade': {'color': '#E91E63', 'icon': '📊'},
            'content': {'color': '#009688', 'icon': '📚'},
            'enrollment': {'color': '#673AB7', 'icon': '🎓'},
            'forum': {'color': '#00BCD4', 'icon': '💬'},
            'reminder': {'color': '#FF5722', 'icon': '⏰'},
            'progress': {'color': '#4CAF50', 'icon': '📈'},
            'feedback': {'color': '#FF9800', 'icon': '💬'},
            'announcement': {'color': '#F44336', 'icon': '📢'},
            'social': {'color': '#9C27B0', 'icon': '🌟'}
        }
        
        config = type_config.get(notification['type'], type_config['info'])
        bg_color = "#1e2329" if not notification['is_read'] else "#0e1117"
        border_color = config['color'] if not notification['is_read'] else "#333"
        
        # Limpiar y escapar el contenido
        import html
        title = html.escape(str(notification['title']))
        message = html.escape(str(notification['message']))
        
        with st.container():
            # Usar un enfoque más simple sin HTML complejo
            if not notification['is_read']:
                st.markdown(f"**🆕 {config['icon']} {title}**")
            else:
                st.markdown(f"{config['icon']} {title}")
            
            st.markdown(f"*{message}*")
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.caption(f"📅 {notification['created_at'][:16]} • #{notification['type'].upper()}")
            
            with col2:
                if not notification['is_read']:
                    if st.button("✓", key=f"read_{notification['id']}", help="Marcar como leída"):
                        self.mark_as_read(notification['id'])
                        st.rerun()
            
            st.markdown("---")

# Instancia global
notification_manager = NotificationManager()

def send_feature_tips_to_user(user_id, user_role='student'):
    """Envía consejos específicos sobre funciones disponibles"""
    tips_by_role = {
        'student': [
            {
                'title': 'Evaluador de Código Inteligente',
                'message': 'Usa el Tutor IA para evaluar tu código antes de enviarlo. Obtén retroalimentación instantánea y mejora tu puntuación.'
            },
            {
                'title': 'Desafíos Adaptativos',
                'message': 'El Gimnasio de Código genera desafíos únicos según tu nivel. Practica diariamente para mejorar tus habilidades.'
            },
            {
                'title': 'Academia Personal IA',
                'message': 'Crea cursos personalizados que se adapten a tu ritmo de aprendizaje. La IA evalúa tu nivel y genera contenido específico.'
            },
            {
                'title': 'Asistente de Errores',
                'message': 'Cuando tengas errores en tu código, usa el Tutor IA para obtener explicaciones detalladas y soluciones paso a paso.'
            },
            {
                'title': 'Progreso Visual',
                'message': 'Revisa tu historial de calificaciones para identificar patrones y áreas de mejora en tu aprendizaje.'
            }
        ],
        'teacher': [
            {
                'title': 'Evaluación Automática',
                'message': 'Configura evaluaciones automáticas con IA para ahorrar tiempo y proporcionar retroalimentación consistente.'
            },
            {
                'title': 'Análisis de Rendimiento',
                'message': 'Usa las estadísticas de curso para identificar estudiantes que necesitan apoyo adicional.'
            },
            {
                'title': 'Contenido Dinámico',
                'message': 'Crea ejercicios que se adapten automáticamente al nivel de cada estudiante usando IA.'
            }
        ]
    }
    
    tips = tips_by_role.get(user_role, tips_by_role['student'])
    
    try:
        import random
        tip = random.choice(tips)
        
        return notification_manager.create_tip_notification(
            user_id=user_id,
            tip_title=tip['title'],
            tip_message=tip['message']
        )
    except Exception as e:
        print(f"Error enviando consejo: {e}")
        return False

# Función para crear notificaciones de logros automáticas
def check_and_create_achievements(user_id):
    """Verifica y crea notificaciones de logros basadas en actividad del usuario"""
    try:
        conn = notification_manager.conn
        
        # Logro: Primer código evaluado
        eval_count = conn.execute("""
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = ? AND title LIKE '%Código Evaluado%'
        """, (user_id,)).fetchone()[0]
        
        if eval_count == 1:  # Primera evaluación
            notification_manager.create_achievement_notification(
                user_id=user_id,
                achievement_title="Primer Código Evaluado",
                achievement_message="¡Felicidades! Has usado el evaluador IA por primera vez. Sigue practicando para mejorar."
            )
        
        # Logro: Múltiples evaluaciones
        elif eval_count == 5:
            notification_manager.create_achievement_notification(
                user_id=user_id,
                achievement_title="Evaluador Frecuente",
                achievement_message="¡Excelente! Has evaluado 5 códigos con IA. Tu dedicación al aprendizaje es admirable."
            )
        
        # Logro: Primer desafío generado
        challenge_count = conn.execute("""
            SELECT COUNT(*) FROM notifications 
            WHERE user_id = ? AND title LIKE '%Desafío Generado%'
        """, (user_id,)).fetchone()[0]
        
        if challenge_count == 1:
            notification_manager.create_achievement_notification(
                user_id=user_id,
                achievement_title="Primer Desafío",
                achievement_message="¡Genial! Has generado tu primer desafío personalizado. La práctica constante es clave del éxito."
            )
        
        # Logro: Explorador de funciones
        feature_notifications = conn.execute("""
            SELECT COUNT(DISTINCT title) FROM notifications 
            WHERE user_id = ? AND type = 'achievement' AND title LIKE '%Usaste:%'
        """, (user_id,)).fetchone()[0]
        
        if feature_notifications >= 3:
            existing_explorer = conn.execute("""
                SELECT id FROM notifications 
                WHERE user_id = ? AND title LIKE '%Explorador de Funciones%'
            """, (user_id,)).fetchone()
            
            if not existing_explorer:
                notification_manager.create_achievement_notification(
                    user_id=user_id,
                    achievement_title="Explorador de Funciones",
                    achievement_message="¡Increíble! Has explorado múltiples funciones de la plataforma. Eres un usuario avanzado."
                )
        
        return True
        
    except Exception as e:
        print(f"Error verificando logros: {e}")
        return False