"""Small isolated datasets used by the workflow test modules."""

from pathlib import Path

from learning_platform.auth import AuthService
from learning_platform.repositories import ProgressRepository, QuestionRepository
from learning_platform.storage import JsonStore


def create_workspace(folder: Path):
    records = [
        {
            "id": "T001",
            "subject": "Mathematics",
            "topic": "Arithmetic",
            "difficulty": "easy",
            "type": "single_choice",
            "question": "2 + 3 = ?",
            "options": ["4", "5", "6"],
            "answer": "5",
            "explanation": "Adding two and three gives five.",
        },
        {
            "id": "T002",
            "subject": "Mathematics",
            "topic": "Arithmetic",
            "difficulty": "easy",
            "type": "single_choice",
            "question": "3 + 4 = ?",
            "options": ["6", "7", "8"],
            "answer": "7",
            "explanation": "Adding three and four gives seven.",
        },
        {
            "id": "T003",
            "subject": "Science",
            "topic": "Matter",
            "difficulty": "medium",
            "type": "single_choice",
            "question": "Which is solid water?",
            "options": ["Ice", "Steam"],
            "answer": "Ice",
            "explanation": "Ice is water in its solid state.",
        },
    ]
    JsonStore(folder / "questions" / "sample.json", []).write(records)
    return QuestionRepository(folder / "questions"), ProgressRepository(folder / "progress.json")


def create_accounts(folder: Path):
    auth = AuthService(folder)
    admin = auth.register("Manager", "Secret1", "Secret1")
    records = auth.store.read()
    records["manager"]["role"] = "admin"
    auth.store.write(records)
    return auth, auth.require_admin(admin)
