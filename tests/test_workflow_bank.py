"""Question maintenance workflows checked through quiz and storage services."""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from workflow_support import create_workspace

from learning_platform.maintenance import QuestionEditor
from learning_platform.models import Question
from learning_platform.services import QuizEngine, select_questions
from learning_platform.storage import JsonStore


class BankWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.bank, self.progress = create_workspace(self.folder)
        self.editor = QuestionEditor(self.folder / "questions")

    def test_tc09_new_subject_is_available_without_code_changes(self):
        """TC09 - A saved question makes its new subject available to quizzes."""
        question = replace(self.bank.all()[0], id="NEW001", subject="New Subject")
        self.editor.save(question)
        selected = select_questions(self.bank.all(), subject="New Subject", count=1)
        self.assertEqual([q.id for q in selected], ["NEW001"])
        quiz = QuizEngine(selected, self.progress)
        self.assertTrue(quiz.submit("5"))
        self.assertEqual(self.progress.load()["history"][0]["subject"], "New Subject")

    def test_tc10_edit_updates_answer_and_preserves_original_backup(self):
        """TC10 - Editing changes the next quiz and retains the previous bank."""
        original = self.bank.all()[0]
        changed = replace(
            original, question="2 + 2 = ?", answer="4", explanation="Two plus two is four."
        )
        self.editor.save(changed, original)
        reloaded = next(q for q in self.bank.all() if q.id == original.id)
        self.assertTrue(QuizEngine([reloaded], self.progress).submit("4"))
        backups = list((self.folder / "backups").glob("*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(Question.from_dict(JsonStore(backups[0], []).read()[0]), original)

    def test_tc11_delete_keeps_existing_notebook_and_history(self):
        """TC11 - Deleting a question does not erase past learning records."""
        question = self.bank.all()[0]
        QuizEngine([question], self.progress).submit("4")
        before = self.progress.load()
        self.editor.delete(question)
        self.assertNotIn(question.id, {q.id for q in self.bank.all()})
        self.assertEqual(self.progress.load(), before)

    def test_tc12_duplicate_id_is_rejected_without_changing_bank(self):
        """TC12 - Duplicate IDs leave the existing question bank intact."""
        question = self.bank.all()[0]
        path = self.folder / "questions/sample.json"
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            self.editor.save(replace(question, subject="Duplicate"))
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.bank.all()), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
