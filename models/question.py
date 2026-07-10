# -*- coding: utf-8 -*-
"""
Data models for the question bank system
"""

from dataclasses import dataclass
from typing import List
import random


@dataclass
class Question:
    """Represents a single evaluation question."""
    id: str
    question_text: str
    options: List[str]
    correct_answer_index: int
    explanation: str
    example_code: str
    
    def validate(self) -> tuple[bool, str]:
        """Validate question structure and content."""
        if len(self.options) != 4:
            return False, "Must have exactly 4 options"
        if not 0 <= self.correct_answer_index <= 3:
            return False, "Correct answer index must be 0-3"
        if not self.question_text or not self.explanation:
            return False, "Question text and explanation required"
        if "```" not in self.question_text:
            return False, "Question must contain code block"
        if not self.example_code:
            return False, "Example code is required"
        return True, ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "question_text": self.question_text,
            "options": self.options,
            "correct_answer_index": self.correct_answer_index,
            "explanation": self.explanation,
            "example_code": self.example_code
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        """Create Question from dictionary."""
        return cls(
            id=data["id"],
            question_text=data["question_text"],
            options=data["options"],
            correct_answer_index=data["correct_answer_index"],
            explanation=data["explanation"],
            example_code=data["example_code"]
        )


@dataclass
class QuestionPool:
    """Represents a pool of 40 questions for a specific combination."""
    language: str
    section: int
    section_title: str
    difficulty: str
    questions: List[Question]
    
    def validate(self) -> tuple[bool, str]:
        """Validate pool has exactly 40 valid questions."""
        if len(self.questions) != 40:
            return False, f"Pool must have 40 questions, has {len(self.questions)}"
        
        for i, q in enumerate(self.questions):
            is_valid, error = q.validate()
            if not is_valid:
                return False, f"Question {i}: {error}"
        
        return True, ""
    
    def select_random(self, count: int = 15) -> List[Question]:
        """Randomly select questions without replacement."""
        return random.sample(self.questions, min(count, len(self.questions)))


@dataclass
class EvaluationResult:
    """Represents the result of an evaluation."""
    score: int
    total: int
    percentage: float
    passed: bool
    correct_answers: List[int]
    incorrect_answers: List[int]
    feedback: str
    
    @classmethod
    def from_responses(
        cls,
        questions: List[Question],
        responses: List[int],
        passing_score: int = 6
    ) -> 'EvaluationResult':
        """Calculate evaluation result from responses."""
        correct = []
        incorrect = []
        
        for i, (question, response) in enumerate(zip(questions, responses)):
            if response == question.correct_answer_index:
                correct.append(i)
            else:
                incorrect.append(i)
        
        score = len(correct)
        total = len(questions)
        percentage = (score / total) * 100 if total > 0 else 0
        passed = score >= passing_score
        
        if passed:
            feedback = f"¡Excelente trabajo! Has aprobado con {score}/{total} respuestas correctas."
        else:
            feedback = f"Has obtenido {score}/{total} respuestas correctas. Necesitas al menos {passing_score} para aprobar. ¡Sigue practicando!"
        
        return cls(
            score=score,
            total=total,
            percentage=percentage,
            passed=passed,
            correct_answers=correct,
            incorrect_answers=incorrect,
            feedback=feedback
        )
