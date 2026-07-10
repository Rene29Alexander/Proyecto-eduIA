# -*- coding: utf-8 -*-
"""
Question Bank Loader and Manager
Manages loading, validation, and querying of the pre-generated question bank.
"""

import json
import os
from typing import List, Dict, Tuple, Optional
from models.question import Question, QuestionPool, EvaluationResult


class QuestionBank:
    """
    Manages loading, validation, and querying of the question bank.
    """
    
    def __init__(self, bank_path: str = "data/question_bank.json"):
        """Initialize the question bank loader."""
        self.bank_path = bank_path
        self.data = None
        self.is_loaded = False
    
    def load(self) -> bool:
        """
        Load the question bank from JSON file.
        Returns True if successful, False otherwise.
        Raises FileNotFoundError if bank file doesn't exist.
        Raises JSONDecodeError if bank file is malformed.
        """
        if not os.path.exists(self.bank_path):
            raise FileNotFoundError(
                f"Question bank file not found at {self.bank_path}. "
                "Please run the question generator script first."
            )
        
        try:
            with open(self.bank_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            self.is_loaded = True
            return True
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Question bank file is malformed. Error: {str(e)}",
                e.doc,
                e.pos
            )
        except Exception as e:
            raise Exception(f"Error loading question bank: {str(e)}")
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate the question bank structure and content.
        Returns (is_valid, list_of_warnings).
        """
        if not self.is_loaded:
            return False, ["Question bank not loaded"]
        
        warnings = []
        
        if "languages" not in self.data:
            return False, ["Missing 'languages' key in question bank"]
        
        languages = self.data["languages"]
        
        for lang_name, lang_data in languages.items():
            if "sections" not in lang_data:
                warnings.append(f"Language {lang_name}: missing 'sections' key")
                continue
            
            sections = lang_data["sections"]
            
            # Check for exactly 8 sections
            if len(sections) != 8:
                warnings.append(
                    f"Language {lang_name}: has {len(sections)} sections, expected 8"
                )
            
            for section_num, section_data in sections.items():
                if "difficulties" not in section_data:
                    warnings.append(
                        f"Language {lang_name}, Section {section_num}: missing 'difficulties' key"
                    )
                    continue
                
                difficulties = section_data["difficulties"]
                
                # Check for exactly 3 difficulty levels
                expected_difficulties = ["principiante", "intermedio", "avanzado"]
                for diff in expected_difficulties:
                    if diff not in difficulties:
                        warnings.append(
                            f"Language {lang_name}, Section {section_num}: "
                            f"missing difficulty '{diff}'"
                        )
                        continue
                    
                    if "questions" not in difficulties[diff]:
                        warnings.append(
                            f"Language {lang_name}, Section {section_num}, "
                            f"Difficulty {diff}: missing 'questions' key"
                        )
                        continue
                    
                    questions = difficulties[diff]["questions"]
                    
                    # Check for exactly 40 questions
                    if len(questions) != 40:
                        warnings.append(
                            f"Language {lang_name}, Section {section_num}, "
                            f"Difficulty {diff}: has {len(questions)} questions, expected 40"
                        )
        
        is_valid = len(warnings) == 0
        return is_valid, warnings
    
    def get_question_pool(
        self, 
        language: str, 
        section: int, 
        difficulty: str
    ) -> List[dict]:
        """
        Get all 40 questions for a specific combination.
        Returns empty list if combination doesn't exist.
        """
        if not self.is_loaded:
            return []
        
        try:
            questions = (
                self.data["languages"]
                [language]
                ["sections"]
                [str(section)]
                ["difficulties"]
                [difficulty]
                ["questions"]
            )
            return questions
        except KeyError:
            return []
    
    def select_random_questions(
        self, 
        language: str, 
        section: int, 
        difficulty: str, 
        count: int = 15
    ) -> List[dict]:
        """
        Randomly select questions from the pool without replacement.
        Returns list of question dictionaries.
        Filters out duplicate questions to ensure variety.
        """
        pool = self.get_question_pool(language, section, difficulty)
        
        if not pool:
            return []
        
        # Remove duplicate questions based on question_text
        seen_questions = set()
        unique_pool = []
        for q in pool:
            if q["question_text"] not in seen_questions:
                seen_questions.add(q["question_text"])
                unique_pool.append(q)
        
        # If we have fewer unique questions than requested, use all unique ones
        if len(unique_pool) < count:
            count = len(unique_pool)
        
        # Convert to Question objects for validation
        questions = [Question.from_dict(q) for q in unique_pool]
        
        # Create QuestionPool and select random
        question_pool = QuestionPool(
            language=language,
            section=section,
            section_title="",  # Not needed for selection
            difficulty=difficulty,
            questions=questions
        )
        
        selected = question_pool.select_random(count)
        
        # Convert back to dictionaries
        return [q.to_dict() for q in selected]
    
    def get_languages(self) -> List[str]:
        """Get list of all available languages."""
        if not self.is_loaded:
            return []
        
        return list(self.data.get("languages", {}).keys())
    
    def get_sections(self, language: str) -> List[dict]:
        """Get list of sections for a language with titles."""
        if not self.is_loaded:
            return []
        
        try:
            sections = self.data["languages"][language]["sections"]
            result = []
            for section_num, section_data in sections.items():
                result.append({
                    "number": int(section_num),
                    "title": section_data.get("title", f"Sección {section_num}")
                })
            return sorted(result, key=lambda x: x["number"])
        except KeyError:
            return []
    
    def get_difficulties(self) -> List[str]:
        """Get list of difficulty levels."""
        return ["principiante", "intermedio", "avanzado"]
    
    def get_stats(self) -> dict:
        """Get statistics about the question bank."""
        if not self.is_loaded:
            return {}
        
        stats = {
            "languages": [],
            "total_questions": 0,
            "questions_by_language": {}
        }
        
        languages = self.data.get("languages", {})
        stats["languages"] = list(languages.keys())
        
        for lang_name, lang_data in languages.items():
            lang_count = 0
            sections = lang_data.get("sections", {})
            
            for section_data in sections.values():
                difficulties = section_data.get("difficulties", {})
                
                for diff_data in difficulties.values():
                    questions = diff_data.get("questions", [])
                    lang_count += len(questions)
            
            stats["questions_by_language"][lang_name] = lang_count
            stats["total_questions"] += lang_count
        
        return stats


def generate_topic_evaluation_from_bank(
    language: str,
    section: int,
    difficulty: str,
    question_bank: QuestionBank
) -> dict:
    """
    Generate evaluation using pre-generated questions.
    
    Returns:
    {
        "questions": [
            {
                "question": "Question text with code",
                "options": ["A", "B", "C", "D"],
                "correct_answer": 1,
                "explanation": "Why this is correct",
                "example_code": "Code example"
            },
            // ... 14 more questions
        ],
        "metadata": {
            "language": "Python",
            "section": 1,
            "difficulty": "principiante",
            "total_questions": 15,
            "source": "question_bank"
        }
    }
    """
    selected_questions = question_bank.select_random_questions(
        language, section, difficulty, count=15
    )
    
    if not selected_questions:
        return {
            "questions": [],
            "metadata": {
                "language": language,
                "section": section,
                "difficulty": difficulty,
                "total_questions": 0,
                "source": "question_bank",
                "error": "No questions found for this combination"
            }
        }
    
    # Format questions for evaluation interface
    formatted_questions = []
    for q in selected_questions:
        formatted_questions.append({
            "question": q["question_text"],
            "options": q["options"],
            "correct_answer": q["correct_answer_index"],
            "explanation": q["explanation"],
            "example_code": q["example_code"]
        })
    
    return {
        "questions": formatted_questions,
        "metadata": {
            "language": language,
            "section": section,
            "difficulty": difficulty,
            "total_questions": len(formatted_questions),
            "source": "question_bank"
        }
    }


def evaluate_topic_assessment_from_bank(
    questions_data: List[dict],
    responses_data: List[int],
    passing_score: int = 6
) -> dict:
    """
    Evaluate student responses against correct answers.
    
    Returns:
    {
        "score": 12,
        "total": 15,
        "percentage": 80.0,
        "passed": True,
        "correct_answers": [0, 1, 2, 3, 5, 6, 7, 9, 10, 11, 12, 13, 14],
        "incorrect_answers": [4, 8],
        "feedback": "¡Excelente trabajo! Has aprobado con 12/15 respuestas correctas."
    }
    """
    if len(questions_data) != len(responses_data):
        raise ValueError(
            f"Response count ({len(responses_data)}) does not match "
            f"question count ({len(questions_data)})"
        )
    
    # Convert to Question objects
    questions = []
    for q_data in questions_data:
        questions.append(Question(
            id="",  # Not needed for evaluation
            question_text=q_data["question"],
            options=q_data["options"],
            correct_answer_index=q_data["correct_answer"],
            explanation=q_data["explanation"],
            example_code=q_data["example_code"]
        ))
    
    # Calculate result
    result = EvaluationResult.from_responses(questions, responses_data, passing_score)
    
    return {
        "score": result.score,
        "total": result.total,
        "percentage": result.percentage,
        "passed": result.passed,
        "correct_answers": result.correct_answers,
        "incorrect_answers": result.incorrect_answers,
        "feedback": result.feedback
    }



def generate_final_exam_from_bank(
    language: str,
    difficulty: str,
    question_bank: QuestionBank
) -> dict:
    """
    Generate final exam with 40 UNIQUE random questions from the question bank.
    Selects questions from all sections for a comprehensive exam.
    Ensures no duplicate questions based on question_text.
    
    Args:
        language: Programming language (e.g., "Python", "JavaScript")
        difficulty: Difficulty level ("principiante", "intermedio", "avanzado")
        question_bank: QuestionBank instance with loaded questions
    
    Returns:
        dict: {
            "questions": [
                {
                    "question": "Question text",
                    "options": ["A", "B", "C", "D"],
                    "correct_answer": 1,
                    "explanation": "Explanation",
                    "example_code": "Code example"
                },
                // ... 39 more questions
            ],
            "metadata": {
                "language": "Python",
                "difficulty": "principiante",
                "total_questions": 40,
                "source": "final_exam_bank"
            }
        }
    """
    import random
    
    # Collect all questions from all sections for this language and difficulty
    all_questions = []
    seen_questions = set()  # Track unique questions by text
    
    if language in question_bank.data.get("languages", {}):
        lang_data = question_bank.data["languages"][language]
        sections = lang_data.get("sections", {})
        
        for section_num, section_data in sections.items():
            difficulties = section_data.get("difficulties", {})
            if difficulty in difficulties:
                diff_data = difficulties[difficulty]
                questions = diff_data.get("questions", [])
                
                # Filter out duplicate questions
                for q in questions:
                    q_text = q.get("question_text", "")
                    if q_text and q_text not in seen_questions:
                        seen_questions.add(q_text)
                        all_questions.append(q)
    
    # Shuffle all unique questions
    random.shuffle(all_questions)
    
    # Select up to 40 unique questions
    if len(all_questions) < 40:
        selected = all_questions
    else:
        selected = all_questions[:40]
    
    # Format questions
    formatted_questions = []
    for q in selected:
        formatted_questions.append({
            "question": q.get("question_text", ""),
            "options": q.get("options", []),
            "correct_answer": q.get("correct_answer_index", 0),
            "explanation": q.get("explanation", ""),
            "example_code": q.get("example_code", "")
        })
    
    return {
        "questions": formatted_questions,
        "metadata": {
            "language": language,
            "difficulty": difficulty,
            "total_questions": len(formatted_questions),
            "source": "final_exam_bank",
            "unique_questions": len(all_questions)
        }
    }


def generate_level_assessment_from_bank(
    language: str,
    question_bank: QuestionBank
) -> list:
    """
    Generate level assessment with 10 random questions from the question bank.
    Selects 3-4 questions from each difficulty level (principiante, intermedio, avanzado)
    to determine student's level. Total: 10 questions.
    
    Args:
        language: Programming language (e.g., "Python", "JavaScript")
        question_bank: QuestionBank instance with loaded questions
    
    Returns:
        list: List of 10 questions with mixed difficulty levels
    """
    import random
    
    # Collect questions by difficulty level
    questions_by_level = {
        "principiante": [],
        "intermedio": [],
        "avanzado": []
    }
    
    if language in question_bank.data.get("languages", {}):
        lang_data = question_bank.data["languages"][language]
        sections = lang_data.get("sections", {})
        
        # Collect questions from each difficulty level
        for difficulty in ["principiante", "intermedio", "avanzado"]:
            seen_questions = set()
            
            for section_num, section_data in sections.items():
                difficulties = section_data.get("difficulties", {})
                if difficulty in difficulties:
                    diff_data = difficulties[difficulty]
                    questions = diff_data.get("questions", [])
                    
                    # Filter out duplicate questions
                    for q in questions:
                        q_text = q.get("question_text", "")
                        if q_text and q_text not in seen_questions:
                            seen_questions.add(q_text)
                            # Add difficulty level to question
                            q_copy = q.copy()
                            q_copy['level'] = difficulty
                            questions_by_level[difficulty].append(q_copy)
    
    # Select questions from each level
    # Distribution: 4 principiante, 3 intermedio, 3 avanzado = 10 total
    selected_questions = []
    
    # Shuffle questions in each level
    for level in questions_by_level:
        random.shuffle(questions_by_level[level])
    
    # Select 4 from principiante (or all available if less than 4)
    num_principiante = min(4, len(questions_by_level["principiante"]))
    selected_questions.extend(questions_by_level["principiante"][:num_principiante])
    
    # Select 3 from intermedio (or all available if less than 3)
    num_intermedio = min(3, len(questions_by_level["intermedio"]))
    selected_questions.extend(questions_by_level["intermedio"][:num_intermedio])
    
    # Select 3 from avanzado (or all available if less than 3)
    num_avanzado = min(3, len(questions_by_level["avanzado"]))
    selected_questions.extend(questions_by_level["avanzado"][:num_avanzado])
    
    # If we don't have 10 questions yet, try to fill from any level
    if len(selected_questions) < 10:
        remaining_needed = 10 - len(selected_questions)
        all_remaining = []
        
        # Collect remaining questions from all levels
        for level in ["principiante", "intermedio", "avanzado"]:
            if level == "principiante":
                all_remaining.extend(questions_by_level[level][num_principiante:])
            elif level == "intermedio":
                all_remaining.extend(questions_by_level[level][num_intermedio:])
            else:
                all_remaining.extend(questions_by_level[level][num_avanzado:])
        
        random.shuffle(all_remaining)
        selected_questions.extend(all_remaining[:remaining_needed])
    
    # Shuffle final selection to mix difficulty levels
    random.shuffle(selected_questions)
    
    # Ensure we have exactly 10 questions (or less if not enough available)
    selected_questions = selected_questions[:10]
    
    # Format questions to match expected format
    formatted_questions = []
    for q in selected_questions:
        formatted_questions.append({
            "question": q.get("question_text", ""),
            "options": q.get("options", []),
            "correct_index": q.get("correct_answer_index", 0),
            "level": q.get("level", "principiante"),
            "topic": "general",
            "explanation": q.get("explanation", ""),
            "points": 1,
            "code_example": q.get("example_code", "")
        })
    
    print(f"✅ Evaluación generada: {len(formatted_questions)} preguntas para {language}")
    print(f"   Distribución: {num_principiante} principiante, {num_intermedio} intermedio, {num_avanzado} avanzado")
    
    return formatted_questions
