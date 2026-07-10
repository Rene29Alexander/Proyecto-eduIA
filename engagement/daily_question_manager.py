"""Gestor de Preguntas Diarias para mantener la racha"""
from database import db_manager
from datetime import date, datetime
import json
import google.generativeai as genai

class DailyQuestionManager:
    
    # Preguntas de respaldo en caso de que la IA falle
    FALLBACK_QUESTIONS = [
        {
            "question": "¿Cuál es la complejidad temporal de buscar un elemento en un árbol binario de búsqueda balanceado?",
            "option_a": "O(1)",
            "option_b": "O(log n)",
            "option_c": "O(n)",
            "option_d": "O(n²)",
            "correct_answer": "B",
            "explanation": "En un árbol binario de búsqueda balanceado, cada comparación elimina aproximadamente la mitad de los elementos restantes, resultando en O(log n).",
            "topic": "Estructuras de Datos"
        },
        {
            "question": "¿Qué estructura de datos sigue el principio LIFO (Last In, First Out)?",
            "option_a": "Cola (Queue)",
            "option_b": "Lista enlazada",
            "option_c": "Pila (Stack)",
            "option_d": "Árbol",
            "correct_answer": "C",
            "explanation": "Una pila (Stack) sigue el principio LIFO donde el último elemento agregado es el primero en ser removido.",
            "topic": "Estructuras de Datos"
        },
        {
            "question": "¿Cuál es el propósito principal de la recursión en programación?",
            "option_a": "Hacer el código más rápido",
            "option_b": "Resolver problemas dividiéndolos en subproblemas más pequeños",
            "option_c": "Usar menos memoria",
            "option_d": "Evitar bucles",
            "correct_answer": "B",
            "explanation": "La recursión permite resolver problemas complejos dividiéndolos en subproblemas más pequeños y manejables del mismo tipo.",
            "topic": "Algoritmos"
        },
        {
            "question": "¿Qué algoritmo de ordenamiento tiene la mejor complejidad temporal en el caso promedio?",
            "option_a": "Bubble Sort - O(n²)",
            "option_b": "Quick Sort - O(n log n)",
            "option_c": "Selection Sort - O(n²)",
            "option_d": "Insertion Sort - O(n²)",
            "correct_answer": "B",
            "explanation": "Quick Sort tiene una complejidad promedio de O(n log n), siendo uno de los algoritmos de ordenamiento más eficientes.",
            "topic": "Algoritmos"
        },
        {
            "question": "¿Qué es la programación orientada a objetos (POO)?",
            "option_a": "Un lenguaje de programación",
            "option_b": "Un paradigma que organiza código en objetos con datos y métodos",
            "option_c": "Una base de datos",
            "option_d": "Un tipo de variable",
            "correct_answer": "B",
            "explanation": "POO es un paradigma de programación que organiza el código en objetos que contienen tanto datos (atributos) como comportamientos (métodos).",
            "topic": "Paradigmas"
        },
        {
            "question": "¿Cuál es la diferencia entre una lista y una tupla en Python?",
            "option_a": "No hay diferencia",
            "option_b": "Las listas son inmutables, las tuplas son mutables",
            "option_c": "Las listas son mutables, las tuplas son inmutables",
            "option_d": "Las tuplas son más lentas",
            "correct_answer": "C",
            "explanation": "Las listas en Python son mutables (se pueden modificar), mientras que las tuplas son inmutables (no se pueden cambiar después de crearse).",
            "topic": "Python"
        },
        {
            "question": "¿Qué es un deadlock en programación concurrente?",
            "option_a": "Un error de sintaxis",
            "option_b": "Una situación donde dos o más procesos esperan indefinidamente por recursos",
            "option_c": "Un tipo de variable",
            "option_d": "Un algoritmo de ordenamiento",
            "correct_answer": "B",
            "explanation": "Un deadlock ocurre cuando dos o más procesos están esperando recursos que están siendo retenidos por otros procesos, creando un ciclo de espera infinito.",
            "topic": "Concurrencia"
        }
    ]
    
    @staticmethod
    def _ensure_table():
        """Asegura que existe la tabla de preguntas diarias"""
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_date DATE NOT NULL UNIQUE,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                explanation TEXT,
                difficulty TEXT DEFAULT 'medium',
                topic TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_question_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                question_id INTEGER NOT NULL,
                user_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username),
                FOREIGN KEY (question_id) REFERENCES daily_questions(id),
                UNIQUE(user_id, question_id)
            )
        ''')
        
        conn.commit()
    
    @staticmethod
    def generate_daily_question():
        """Genera una pregunta diaria usando IA"""
        try:
            # Configurar Gemini
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY", "")
            if not api_key:
                print("No hay API key configurada")
                return None
            
            genai.configure(api_key=api_key)
            # Usar Gemini 3.1 Flash Lite Preview (actualizado marzo 2026)
            model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
            
            prompt = """Genera una pregunta de opción múltiple sobre programación.
            
            La pregunta debe ser:
            - Sobre conceptos de programación (algoritmos, estructuras de datos, paradigmas, etc.)
            - De dificultad media
            - Con 4 opciones (A, B, C, D)
            - Solo una respuesta correcta
            - Incluir una explicación breve de por qué es correcta
            
            Responde SOLO con un JSON válido en este formato exacto:
            {
                "question": "texto de la pregunta",
                "option_a": "opción A",
                "option_b": "opción B",
                "option_c": "opción C",
                "option_d": "opción D",
                "correct_answer": "A",
                "explanation": "explicación de por qué es correcta",
                "topic": "tema de la pregunta"
            }
            
            NO incluyas markdown, NO incluyas ```json, solo el JSON puro."""
            
            response = model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Limpiar respuesta si tiene markdown
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group()
            
            question_data = json.loads(response_text)
            
            # Validar que tenga todos los campos
            required_fields = ['question', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'explanation', 'topic']
            for field in required_fields:
                if field not in question_data:
                    print(f"Campo faltante: {field}")
                    return None
            
            return question_data
            
        except Exception as e:
            print(f"Error generando pregunta: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def get_or_create_today_question():
        """Obtiene la pregunta del día o la crea si no existe"""
        DailyQuestionManager._ensure_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        today = date.today()
        
        # Buscar pregunta de hoy
        question = c.execute('''
            SELECT * FROM daily_questions WHERE question_date = ?
        ''', (today.isoformat(),)).fetchone()
        
        if question:
            return {
                'id': question[0],
                'question_date': question[1],
                'question_text': question[2],
                'option_a': question[3],
                'option_b': question[4],
                'option_c': question[5],
                'option_d': question[6],
                'correct_answer': question[7],
                'explanation': question[8],
                'difficulty': question[9],
                'topic': question[10]
            }
        
        # Intentar generar nueva pregunta con IA
        question_data = DailyQuestionManager.generate_daily_question()
        
        # Si la IA falla, usar pregunta de respaldo
        if not question_data:
            print("IA falló, usando pregunta de respaldo")
            # Usar el día del año para seleccionar una pregunta diferente cada día
            day_of_year = today.timetuple().tm_yday
            fallback_index = day_of_year % len(DailyQuestionManager.FALLBACK_QUESTIONS)
            question_data = DailyQuestionManager.FALLBACK_QUESTIONS[fallback_index].copy()
        
        # Guardar en BD
        try:
            c.execute('''
                INSERT INTO daily_questions 
                (question_date, question_text, option_a, option_b, option_c, option_d, 
                 correct_answer, explanation, topic)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today.isoformat(),
                question_data['question'],
                question_data['option_a'],
                question_data['option_b'],
                question_data['option_c'],
                question_data['option_d'],
                question_data['correct_answer'],
                question_data['explanation'],
                question_data.get('topic', 'Programación')
            ))
            
            conn.commit()
            
            question_id = c.lastrowid
            
            return {
                'id': question_id,
                'question_date': today.isoformat(),
                'question_text': question_data['question'],
                'option_a': question_data['option_a'],
                'option_b': question_data['option_b'],
                'option_c': question_data['option_c'],
                'option_d': question_data['option_d'],
                'correct_answer': question_data['correct_answer'],
                'explanation': question_data['explanation'],
                'difficulty': 'medium',
                'topic': question_data.get('topic', 'Programación')
            }
        except Exception as e:
            print(f"Error guardando pregunta: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def has_answered_today(user_id):
        """Verifica si el usuario ya respondió la pregunta de hoy"""
        DailyQuestionManager._ensure_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        today = date.today()
        
        # Obtener ID de pregunta de hoy
        question = c.execute('''
            SELECT id FROM daily_questions WHERE question_date = ?
        ''', (today.isoformat(),)).fetchone()
        
        if not question:
            return False
        
        # Verificar si respondió
        answer = c.execute('''
            SELECT id FROM daily_question_answers 
            WHERE user_id = ? AND question_id = ?
        ''', (user_id, question[0])).fetchone()
        
        return answer is not None
    
    @staticmethod
    def submit_answer(user_id, question_id, user_answer):
        """Registra la respuesta del usuario"""
        DailyQuestionManager._ensure_table()
        
        conn = db_manager.get_connection()
        c = conn.cursor()
        
        # Obtener respuesta correcta
        question = c.execute('''
            SELECT correct_answer FROM daily_questions WHERE id = ?
        ''', (question_id,)).fetchone()
        
        if not question:
            return False, "Pregunta no encontrada"
        
        correct_answer = question[0]
        is_correct = user_answer.upper() == correct_answer.upper()
        
        # Guardar respuesta
        try:
            c.execute('''
                INSERT INTO daily_question_answers (user_id, question_id, user_answer, is_correct)
                VALUES (?, ?, ?, ?)
            ''', (user_id, question_id, user_answer, 1 if is_correct else 0))
            conn.commit()
        except:
            return False, "Ya respondiste esta pregunta"
        
        # Si es correcta, actualizar racha
        if is_correct:
            from .streak_manager import StreakManager
            from .points_manager import PointsManager
            
            StreakManager.update_streak(user_id)
            PointsManager.add_points(user_id, 50, 'daily_question', 'Pregunta diaria respondida correctamente')
            
            return True, "¡Correcto! +50 puntos y racha mantenida"
        else:
            return False, f"Incorrecto. La respuesta correcta era: {correct_answer}"
    
    @staticmethod
    def get_user_streak_status(user_id):
        """Obtiene el estado de la racha del usuario respecto a la pregunta diaria"""
        from .streak_manager import StreakManager
        
        streak_info = StreakManager.get_streak_info(user_id)
        has_answered = DailyQuestionManager.has_answered_today(user_id)
        
        return {
            'current_streak': streak_info['current_streak'],
            'has_answered_today': has_answered,
            'freeze_count': streak_info['freeze_count'],
            'is_at_risk': not has_answered and streak_info['current_streak'] > 0
        }
