import sqlite3
import random
import string
import bcrypt
import json
from datetime import datetime, timedelta
import os
from pathlib import Path

class DatabaseManager:
    """Gestor mejorado de base de datos con conexión persistente y seguridad"""
    
    _instance = None
    _conn = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._conn is None:
            self._init_connection()
    
    def _init_connection(self):
        """Inicializa la conexión con índices y optimizaciones"""
        self._conn = sqlite3.connect('learning_platform.db', check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")
        self._conn.execute("PRAGMA cache_size = -2000")
        
        # Crear índices para mejorar performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Crea índices para optimizar queries frecuentes"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_courses_teacher ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS idx_courses_code ON courses(code)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_course ON tasks(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_task_student ON submissions(task_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_student ON enrollments(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_enrollments_course ON enrollments(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_exam_attempts_exam_student ON exam_attempts(exam_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_exam_attempts_score ON exam_attempts(score)",
            "CREATE INDEX IF NOT EXISTS idx_materials_course_module ON course_materials(course_id, module_id)",
            "CREATE INDEX IF NOT EXISTS idx_forum_course_date ON forum_posts(course_id, date)",
            # Índices para Academia Personal IA
            "CREATE INDEX IF NOT EXISTS idx_ai_courses_student ON ai_courses(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_courses_language ON ai_courses(language)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_topics_course ON ai_course_topics(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_topics_number ON ai_course_topics(topic_number)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_materials_course ON ai_course_materials(ai_course_id)",
            # "CREATE INDEX IF NOT EXISTS idx_ai_course_materials_topic ON ai_course_materials(topic_id)",  # Comentado: columna no existe
            # "CREATE INDEX IF NOT EXISTS idx_ai_topic_exercises_topic ON ai_topic_exercises(topic_id)",  # Comentado: columna no existe
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_exercises_course ON ai_topic_exercises(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_exercise_attempts_exercise ON ai_exercise_attempts(exercise_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_exercise_attempts_student ON ai_exercise_attempts(student_id)",
            # "CREATE INDEX IF NOT EXISTS idx_ai_topic_evaluations_topic ON ai_topic_evaluations(topic_id)",  # Comentado: columna no existe
            "CREATE INDEX IF NOT EXISTS idx_ai_topic_evaluations_student ON ai_topic_evaluations(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_course_chat_course ON ai_course_chat(ai_course_id)",
            # "CREATE INDEX IF NOT EXISTS idx_ai_course_chat_topic ON ai_course_chat(topic_id)",  # Comentado: columna no existe
            "CREATE INDEX IF NOT EXISTS idx_ai_final_exams_course ON ai_course_final_exams(ai_course_id)",
            "CREATE INDEX IF NOT EXISTS idx_language_assessments_student_lang ON language_assessments(student_id, language)",
            "CREATE INDEX IF NOT EXISTS idx_personal_exercises_student_lang ON personal_exercises(student_id, language)",
            "CREATE INDEX IF NOT EXISTS idx_personal_exercises_level ON personal_exercises(level)",
            "CREATE INDEX IF NOT EXISTS idx_exercise_attempts_exercise ON personal_exercise_attempts(exercise_id)",
            "CREATE INDEX IF NOT EXISTS idx_learning_progress_student ON learning_progress(student_id)",
            "CREATE INDEX IF NOT EXISTS idx_learning_resources_student_lang ON learning_resources(student_id, language)",
            "CREATE INDEX IF NOT EXISTS idx_achievements_student ON student_achievements(student_id)",
            # Índices para Chat IA Semanal
            "CREATE INDEX IF NOT EXISTS idx_chat_content_module ON module_ai_chat_content(module_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_questions_module ON module_ai_chat_suggested_questions(module_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_conversations_module_student ON module_ai_chat_conversations(module_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_chat_conversations_created ON module_ai_chat_conversations(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_group_chat_module ON module_ai_group_chat(module_id, created_at DESC)",
            # Índices para Chat Privado entre Usuarios
            "CREATE INDEX IF NOT EXISTS idx_conversations_user1 ON conversations(user1_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_user2 ON conversations(user2_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_course ON conversations(course_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_last_message ON conversations(last_message_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON private_messages(conversation_id, sent_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread ON private_messages(recipient_id, is_read)",
            "CREATE INDEX IF NOT EXISTS idx_messages_sender ON private_messages(sender_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachments_message ON message_attachments(message_id)",
        ]
        
        for index_sql in indexes:
            try:
                self._conn.execute(index_sql)
            except Exception as e:
                print(f"Error creando índice: {e}")
                continue
        
        self._conn.commit()
    
    def get_connection(self):
        """Retorna la conexión a la base de datos"""
        if self._conn is None:
            self._init_connection()
        return self._conn
    
    def init_db(self):
        """Inicializa todas las tablas con estructura mejorada"""
        c = self._conn.cursor()
        
        # Tabla de usuarios
        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student', 'teacher', 'admin')),
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            user_code TEXT UNIQUE,
            bio TEXT DEFAULT '',
            title TEXT DEFAULT '',
            subjects TEXT DEFAULT '',
            social_links TEXT DEFAULT '',
            avatar BLOB,
            theme TEXT DEFAULT 'dark',
            force_reset INTEGER DEFAULT 0,
            join_date DATE DEFAULT CURRENT_DATE,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            email TEXT,
            account_type TEXT DEFAULT 'full',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Migraciones: agregar columnas si no existen en DBs antiguas
        for migration in [
            "ALTER TABLE users ADD COLUMN account_type TEXT DEFAULT 'full'",
            "ALTER TABLE users ADD COLUMN email TEXT",
        ]:
            try:
                c.execute(migration)
                self._conn.commit()
            except:
                pass  # Ya existe
        
        # Tabla de cursos
        c.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            teacher_id TEXT,
            description TEXT,
            cover_image BLOB,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'archived', 'draft')),
            credits INTEGER DEFAULT 3,
            semester TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES users(username) ON DELETE SET NULL
        )
        ''')
        
        # Tabla de módulos
        c.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            order_index INTEGER DEFAULT 0,
            start_date DATE,
            end_date DATE,
            is_published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de tareas
        c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            module_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            criteria TEXT,
            language TEXT DEFAULT 'python',
            submission_type TEXT DEFAULT 'code' CHECK(submission_type IN ('code', 'file', 'text')),
            points INTEGER DEFAULT 10,
            created_by TEXT NOT NULL,
            due_date DATE NOT NULL,
            max_attempts INTEGER DEFAULT 1,
            allow_late INTEGER DEFAULT 0,
            late_penalty REAL DEFAULT 0.0,
            is_published INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL,
            FOREIGN KEY (created_by) REFERENCES users(username)
        )
        ''')
        
        # Tabla de entregas
        c.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            code TEXT,
            file_blob BLOB,
            file_name TEXT,
            file_size INTEGER,
            file_type TEXT,
            ai_feedback TEXT,
            ai_grade REAL,
            final_grade REAL,
            teacher_feedback TEXT,
            status TEXT DEFAULT 'submitted' CHECK(status IN ('submitted', 'graded', 'returned', 'late')),
            attempt_number INTEGER DEFAULT 1,
            submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            graded_date TIMESTAMP,
            graded_by TEXT,
            is_late INTEGER DEFAULT 0,
            late_days INTEGER DEFAULT 0,
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (graded_by) REFERENCES users(username)
        )
        ''')
        
        # Tabla de matrículas
        c.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            student_id TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            enrollment_date DATE DEFAULT CURRENT_DATE,
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'dropped', 'completed')),
            final_grade REAL,
            PRIMARY KEY (student_id, course_id),
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de materiales
        c.execute('''
        CREATE TABLE IF NOT EXISTS course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            module_id INTEGER,
            title TEXT NOT NULL,
            type TEXT DEFAULT 'pdf' CHECK(type IN ('pdf', 'video', 'text', 'link', 'quiz')),
            content_text TEXT,
            content_blob BLOB,
            file_name TEXT,
            file_size INTEGER,
            url TEXT,
            order_index INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 1,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
        )
        ''')
        
        # Tabla de foro
        c.execute('''
        CREATE TABLE IF NOT EXISTS forum_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            parent_id INTEGER,
            message TEXT NOT NULL,
            is_question INTEGER DEFAULT 0,
            is_resolved INTEGER DEFAULT 0,
            upvotes INTEGER DEFAULT 0,
            attachments TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            edited_at TIMESTAMP,
            is_edited INTEGER DEFAULT 0,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (parent_id) REFERENCES forum_posts(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de exámenes
        c.execute('''
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            module_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            duration_minutes INTEGER DEFAULT 60,
            passing_score REAL DEFAULT 60.0,
            max_attempts INTEGER DEFAULT 1,
            shuffle_questions INTEGER DEFAULT 1,
            show_results INTEGER DEFAULT 1,
            is_published INTEGER DEFAULT 1,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE SET NULL
        )
        ''')
        
        # Tabla de preguntas
        c.execute('''
        CREATE TABLE IF NOT EXISTS exam_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            question_type TEXT DEFAULT 'multiple_choice' CHECK(question_type IN ('multiple_choice', 'true_false', 'short_answer', 'essay', 'open_text')),
            options_json TEXT,
            correct_index INTEGER,
            correct_answer TEXT,
            points INTEGER DEFAULT 1,
            explanation TEXT,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de intentos de examen
        c.execute('''
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exam_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            score REAL,
            max_score REAL,
            percentage REAL,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            duration_seconds INTEGER,
            status TEXT DEFAULT 'in_progress' CHECK(status IN ('in_progress', 'completed', 'graded', 'expired')),
            details_json TEXT,
            graded_by TEXT,
            graded_at TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (graded_by) REFERENCES users(username)
        )
        ''')
        
        # Tabla de respuestas de examen
        c.execute('''
        CREATE TABLE IF NOT EXISTS exam_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            student_answer TEXT,
            selected_index INTEGER,
            points_earned REAL DEFAULT 0,
            feedback TEXT,
            is_correct INTEGER DEFAULT 0,
            FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES exam_questions(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de notificaciones
        c.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'info' CHECK(type IN ('info', 'warning', 'success', 'error', 'assignment', 'exam')),
            is_read INTEGER DEFAULT 0,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de logs de actividad
        c.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE SET NULL
        )
        ''')
        
        # Tabla de configuración
        c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # ========== NUEVAS TABLAS PARA ACADEMIA PERSONAL IA ==========
        
        # Tabla de cursos IA (se integran con cursos normales)
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            level TEXT NOT NULL CHECK(level IN ('principiante', 'intermedio', 'avanzado')),
            difficulty_setting TEXT DEFAULT 'normal' CHECK(difficulty_setting IN ('facil', 'normal', 'dificil')),
            status TEXT DEFAULT 'active' CHECK(status IN ('active', 'completed', 'paused')),
            progress_percentage REAL DEFAULT 0,
            assessment_score REAL,
            assessment_data TEXT,
            total_topics INTEGER DEFAULT 0,
            completed_topics INTEGER DEFAULT 0,
            sections_count INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            UNIQUE(student_id, language)
        )
        ''')
        
        # Tabla de temas/secciones del curso IA
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_course_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_course_id INTEGER NOT NULL,
            topic_number INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            objectives TEXT,
            estimated_hours INTEGER DEFAULT 2,
            order_index INTEGER DEFAULT 0,
            is_unlocked INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            completion_percentage REAL DEFAULT 0,
            completed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
            UNIQUE(ai_course_id, topic_number)
        )
        ''')
        
        # Tabla de materiales de cursos IA (ahora por tema)
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_course_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_course_id INTEGER NOT NULL,
            topic_id INTEGER,
            type TEXT NOT NULL CHECK(type IN ('video', 'website', 'tutorial', 'documentation', 'exercise')),
            title TEXT NOT NULL,
            description TEXT,
            url TEXT,
            content TEXT,
            order_index INTEGER DEFAULT 0,
            is_completed INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            difficulty_level INTEGER DEFAULT 1,
            estimated_minutes INTEGER DEFAULT 30,
            language_content TEXT DEFAULT 'es',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
            FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de materiales por tema (contenido generado por IA)
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_topic_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            content_type TEXT DEFAULT 'lesson' CHECK(content_type IN ('lesson', 'example', 'reference', 'video', 'quiz')),
            content TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de ejercicios por tema
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_topic_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            ai_course_id INTEGER,
            exercise_number INTEGER DEFAULT 1,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            exercise_type TEXT DEFAULT 'coding' CHECK(exercise_type IN ('coding', 'multiple_choice', 'fill_blank', 'debug')),
            difficulty TEXT DEFAULT 'medium' CHECK(difficulty IN ('easy', 'medium', 'hard')),
            difficulty_level INTEGER DEFAULT 1 CHECK(difficulty_level BETWEEN 1 AND 5),
            initial_code TEXT,
            solution_code TEXT,
            test_cases TEXT,
            hints TEXT,
            points INTEGER DEFAULT 10,
            order_index INTEGER DEFAULT 0,
            is_required INTEGER DEFAULT 1,
            question TEXT,
            options TEXT,
            correct_index INTEGER,
            explanation TEXT,
            topic_area TEXT,
            code_example TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de intentos de ejercicios por tema
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_exercise_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            submitted_code TEXT,
            submitted_answer TEXT,
            score REAL DEFAULT 0,
            max_score REAL DEFAULT 10,
            is_correct INTEGER DEFAULT 0,
            feedback TEXT,
            ai_evaluation TEXT,
            attempt_number INTEGER DEFAULT 1,
            time_spent_seconds INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES ai_topic_exercises(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de evaluaciones por tema
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_topic_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            ai_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            questions_data TEXT NOT NULL,
            responses_data TEXT,
            score REAL DEFAULT 0,
            max_score REAL DEFAULT 100,
            percentage REAL DEFAULT 0,
            passed INTEGER DEFAULT 0,
            passing_score REAL DEFAULT 70,
            attempt_number INTEGER DEFAULT 1,
            time_spent_seconds INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE CASCADE,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de chat con IA por curso
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_course_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            topic_id INTEGER,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            context_material_id INTEGER,
            context_exercise_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (topic_id) REFERENCES ai_course_topics(id) ON DELETE SET NULL,
            FOREIGN KEY (context_material_id) REFERENCES ai_course_materials(id) ON DELETE SET NULL,
            FOREIGN KEY (context_exercise_id) REFERENCES ai_topic_exercises(id) ON DELETE SET NULL
        )
        ''')
        
        # Tabla de evaluaciones finales de cursos IA
        c.execute('''
        CREATE TABLE IF NOT EXISTS ai_course_final_exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ai_course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            questions_data TEXT NOT NULL,
            responses_data TEXT,
            score REAL,
            max_score REAL,
            percentage REAL,
            passed INTEGER DEFAULT 0,
            passing_score REAL DEFAULT 70,
            attempt_number INTEGER DEFAULT 1,
            time_spent_seconds INTEGER DEFAULT 0,
            can_retake INTEGER DEFAULT 1,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (ai_course_id) REFERENCES ai_courses(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Mantener tablas existentes para compatibilidad
        # Tabla de evaluaciones de nivel por lenguaje
        c.execute('''
        CREATE TABLE IF NOT EXISTS language_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            level TEXT NOT NULL CHECK(level IN ('principiante', 'intermedio', 'avanzado')),
            score REAL NOT NULL,
            max_score REAL NOT NULL,
            percentage REAL NOT NULL,
            assessment_data TEXT,
            recommendations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de ejercicios personalizados
        c.execute('''
        CREATE TABLE IF NOT EXISTS personal_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            level TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            exercise_code TEXT,
            solution_code TEXT,
            difficulty INTEGER DEFAULT 1 CHECK(difficulty BETWEEN 1 AND 10),
            topics TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            is_completed INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de intentos de ejercicios personalizados
        c.execute('''
        CREATE TABLE IF NOT EXISTS personal_exercise_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            submitted_code TEXT NOT NULL,
            score REAL,
            feedback TEXT,
            ai_evaluation TEXT,
            attempt_number INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES personal_exercises(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de progreso de aprendizaje
        c.execute('''
        CREATE TABLE IF NOT EXISTS learning_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            current_level TEXT NOT NULL,
            experience_points INTEGER DEFAULT 0,
            exercises_completed INTEGER DEFAULT 0,
            exercises_total INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 0,
            last_activity_date DATE,
            achievements TEXT,
            study_plan TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE,
            UNIQUE(student_id, language)
        )
        ''')
        
        # Tabla de recursos recomendados
        c.execute('''
        CREATE TABLE IF NOT EXISTS learning_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            level TEXT NOT NULL,
            resource_type TEXT NOT NULL CHECK(resource_type IN ('video', 'website', 'tutorial', 'documentation', 'course')),
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            description TEXT,
            provider TEXT,
            duration_minutes INTEGER,
            rating REAL,
            is_completed INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla de logros y badges
        c.execute('''
        CREATE TABLE IF NOT EXISTS student_achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            language TEXT NOT NULL,
            achievement_type TEXT NOT NULL,
            achievement_name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            points INTEGER DEFAULT 0,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # ========== FIN NUEVAS TABLAS ==========
        
        # Insertar configuración por defecto
        default_settings = [
            ('site_name', 'Plataforma Educativa IA', 'Nombre del sitio'),
            ('site_description', 'Plataforma educativa con inteligencia artificial integrada', 'Descripción del sitio'),
            ('allow_registrations', '0', 'Permitir registros de nuevos usuarios'),
            ('default_theme', 'dark', 'Tema por defecto'),
            ('max_file_size', '10485760', 'Tamaño máximo de archivo en bytes (10MB)'),
            ('ai_enabled', '1', 'Habilitar funcionalidades de IA'),
            ('backup_enabled', '1', 'Habilitar backups automáticos'),
        ]
        
        for key, value, description in default_settings:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO settings (key, value, description) VALUES (?, ?, ?)",
                    (key, value, description)
                )
            except:
                pass
        
        # Crear admin por defecto (contraseña: admin123)
        try:
            admin_password = self.hash_password('admin123')
            if not c.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
                c.execute('''
                    INSERT INTO users (
                        username, password_hash, role, first_name, last_name, full_name, 
                        user_code, email, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    'admin', admin_password, 'admin', 'Super', 'Admin', 'Super Admin',
                    'ADMI000000', 'admin@learningplatform.com', 1
                ))
                self._conn.commit()
        except Exception as e:
            print(f"Error creando admin: {e}")
        
        # ========== TABLAS PARA CHAT IA SEMANAL ==========
        
        # Tabla para almacenar el contenido de contexto del chat por módulo
        c.execute('''
        CREATE TABLE IF NOT EXISTS module_ai_chat_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            content_type TEXT NOT NULL CHECK(content_type IN ('pdf', 'text')),
            content_text TEXT NOT NULL,
            file_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
            UNIQUE(module_id)
        )
        ''')
        
        # Tabla para almacenar preguntas sugeridas por módulo
        c.execute('''
        CREATE TABLE IF NOT EXISTS module_ai_chat_suggested_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
        )
        ''')
        
        # Tabla para almacenar conversaciones de estudiantes
        c.execute('''
        CREATE TABLE IF NOT EXISTS module_ai_chat_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla para chat grupal IA (todos los alumnos y profesores ven los mensajes)
        c.execute('''
        CREATE TABLE IF NOT EXISTS module_ai_group_chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL,
            user_id TEXT NOT NULL,
            user_role TEXT NOT NULL DEFAULT 'student',
            message TEXT NOT NULL,
            response TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')

        # ========== TABLAS PARA CHAT PRIVADO ENTRE USUARIOS ==========
        
        # Tabla para almacenar conversaciones entre dos usuarios
        c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id TEXT NOT NULL,
            user2_id TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user1_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (user2_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
            UNIQUE(user1_id, user2_id, course_id)
        )
        ''')
        
        # Tabla para almacenar mensajes privados
        c.execute('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            sender_id TEXT NOT NULL,
            recipient_id TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            has_attachment INTEGER DEFAULT 0,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE,
            FOREIGN KEY (recipient_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')
        
        # Tabla para almacenar archivos adjuntos a mensajes
        c.execute('''
        CREATE TABLE IF NOT EXISTS message_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_content BLOB NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES private_messages(id) ON DELETE CASCADE
        )
        ''')

        # Tabla para chat exclusivo entre administradores
        c.execute('''
        CREATE TABLE IF NOT EXISTS admin_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT NOT NULL,
            message_text TEXT NOT NULL,
            is_read_by TEXT DEFAULT '[]',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sender_id) REFERENCES users(username) ON DELETE CASCADE
        )
        ''')

        self._conn.commit()
        return self._conn
    
    @staticmethod
    def hash_password(password):
        """Hash de contraseña con bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password, hashed):
        """Verifica contraseña con bcrypt"""
        if not hashed:
            return False
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except:
            return False
    
    def generate_user_code(self, role):
        """Genera código único de usuario"""
        prefix = {
            'student': 'STU',
            'teacher': 'TCH', 
            'admin': 'ADM'
        }.get(role, 'USR')
        
        while True:
            number = ''.join(random.choices(string.digits, k=6))
            code = f"{prefix}{number}"
            
            # Verificar que no exista
            existing = self._conn.execute(
                "SELECT 1 FROM users WHERE user_code = ?", 
                (code,)
            ).fetchone()
            
            if not existing:
                return code
    
    def create_backup(self):
        """Crea backup de la base de datos con compresión"""
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"learning_platform_backup_{timestamp}.db"
        
        try:
            # Copiar archivo de base de datos
            import shutil
            shutil.copy2('learning_platform.db', backup_file)
            
            # Comprimir backup si es muy grande
            if backup_file.stat().st_size > 50 * 1024 * 1024:  # 50MB
                import gzip
                compressed_file = backup_dir / f"learning_platform_backup_{timestamp}.db.gz"
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file.unlink()  # Eliminar archivo sin comprimir
                backup_file = compressed_file
            
            # Limpiar backups antiguos (mantener solo últimos 10)
            backups = sorted(backup_dir.glob("learning_platform_backup_*.db*"))
            if len(backups) > 10:
                for old_backup in backups[:-10]:
                    old_backup.unlink()
            
            return backup_file
        except Exception as e:
            print(f"Error creando backup: {e}")
            return None
    
    def log_activity(self, user_id, action, entity_type=None, entity_id=None, details=None, ip=None, user_agent=None):
        """Registra actividad en el sistema"""
        try:
            self._conn.execute('''
                INSERT INTO activity_logs 
                (user_id, action, entity_type, entity_id, details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, action, entity_type, entity_id, json.dumps(details) if details else None, ip, user_agent))
            self._conn.commit()
        except sqlite3.Error as e:
            print(f"Error registrando actividad en BD: {e}")
        except Exception as e:
            print(f"Error inesperado registrando actividad: {e}")
    
    def close(self):
        """Cierra la conexión a la base de datos"""
        if self._conn:
            self._conn.close()
            self._conn = None
            DatabaseManager._instance = None

# Instancia global para usar en toda la aplicación
db_manager = DatabaseManager()

# Funciones de conveniencia para compatibilidad
def get_db_connection():
    return db_manager.get_connection()

def init_db():
    return db_manager.init_db()

def hash_password(password):
    return db_manager.hash_password(password)

def verify_password(password, hashed):
    return db_manager.verify_password(password, hashed)

def generate_user_code(role):
    return db_manager.generate_user_code(role)