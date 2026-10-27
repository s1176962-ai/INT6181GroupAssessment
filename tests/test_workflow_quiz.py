"""Quiz workflow tests using temporary question banks and progress files."""

import tempfile
import unittest
from pathlib import Path

from workflow_support import create_workspace

from learning_platform.repositories import ProgressRepository
from learning_platform.services import QuizEngine, select_questions


class QuizWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.bank, self.progress = create_workspace(self.folder)

    def test_tc01_configure_complete_and_reopen_results(self):
        """TC01 - A filtered quiz saves an accurate result after restart."""
        questions = select_questions(self.bank.all(), "Mathematics", "Arithmetic", "easy", 5)
        self.assertEqual({q.id for q in questions}, {"T001", "T002"})
        quiz = QuizEngine(questions, self.progress)
        quiz.submit(quiz.current.answer)
        quiz.next_question()
        quiz.submit(
            next(option for option in quiz.current.options if option != quiz.current.answer)
        )
        saved = ProgressRepository(self.folder / "progress.json").load()
        self.assertEqual(len(saved["history"]), 1)
        result = saved["history"][0]
        self.assertEqual((result["total"], result["correct"], result["incorrect"]), (2, 1, 1))
        self.assertEqual(result["accuracy"], 50.0)
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["subject"], "Mathematics")

    def test_tc02_review_removes_only_the_corrected_question(self):
        """TC02 - Reviewing one mistake leaves other mistakes available."""
        questions = self.bank.all()[:2]
        quiz = QuizEngine(questions, self.progress)
        quiz.submit("4")
        quiz.next_question()
        quiz.submit("6")
        QuizEngine([questions[0]], self.progress, review=True).submit("5")
        restored = ProgressRepository(self.folder / "progress.json").load()
        self.assertEqual(set(restored["wrong"]), {"T002"})
        self.assertEqual(len(restored["history"]), 2)
        self.assertEqual(restored["history"][-1]["mode"], "review")

    def test_tc03_rejected_answers_do_not_change_saved_progress(self):
        """TC03 - Blank and repeated submissions cannot alter stored results."""
        quiz = QuizEngine(self.bank.all()[:1], self.progress)
        with self.assertRaises(ValueError):
            quiz.submit("")
        self.assertFalse(self.progress.store.path.exists())
        quiz.submit("5")
        snapshot = self.progress.store.path.read_bytes()
        with self.assertRaises(ValueError):
            quiz.submit("4")
        self.assertEqual(self.progress.store.path.read_bytes(), snapshot)
        self.assertEqual(quiz.result()["correct"], 1)

    def test_tc04_incomplete_quiz_keeps_mistakes_without_final_score(self):
        """TC04 - Leaving an unfinished quiz keeps mistakes but no final result."""
        QuizEngine(self.bank.all(), self.progress).submit("4")
        restored = ProgressRepository(self.folder / "progress.json").load()
        self.assertEqual(set(restored["wrong"]), {"T001"})
        self.assertEqual(restored["history"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
