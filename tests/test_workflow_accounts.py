"""Account-management workflows with independent local test accounts."""

import tempfile
import unittest
from pathlib import Path

from workflow_support import create_accounts, create_workspace

from learning_platform.repositories import ProgressRepository
from learning_platform.services import QuizEngine


class AccountWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.auth, self.admin = create_accounts(self.folder)
        self.student = self.auth.register("Learner", "Secret2", "Secret2")

    def test_tc05_login_routes_records_to_the_correct_account(self):
        """TC05 - Separate logins do not share learning history."""
        bank, _ = create_workspace(self.folder)
        student = self.auth.login("Learner", "Secret2")
        progress = ProgressRepository(self.auth.progress_path(student))
        QuizEngine(bank.all()[:1], progress).submit("5")
        self.assertEqual(len(self.auth.user_progress(self.admin, student["id"])["history"]), 1)
        self.assertEqual(self.auth.user_progress(self.admin, self.admin["id"])["history"], [])

    def test_tc06_disable_and_restore_login(self):
        """TC06 - Disabled accounts cannot log in until restored."""
        self.auth.update_user(self.admin, self.student["id"], "Learner", "student", False)
        with self.assertRaises(ValueError):
            self.auth.login("Learner", "Secret2")
        self.auth.update_user(self.admin, self.student["id"], "Learner", "student", True)
        self.assertEqual(self.auth.login("Learner", "Secret2")["id"], self.student["id"])

    def test_tc07_rename_and_reset_password_preserve_history(self):
        """TC07 - Renaming and password reset preserve the account's history."""
        bank, _ = create_workspace(self.folder)
        progress = ProgressRepository(self.auth.progress_path(self.student))
        QuizEngine(bank.all()[:1], progress).submit("5")
        self.auth.update_user(self.admin, self.student["id"], "Renamed", "student", True, "New123")
        with self.assertRaises(ValueError):
            self.auth.login("Learner", "Secret2")
        user = self.auth.login("Renamed", "New123")
        self.assertEqual(user["id"], self.student["id"])
        self.assertEqual(self.auth.user_progress(self.admin, user["id"])["history"][0]["score"], 1)

    def test_tc08_student_cannot_grant_administrator_access(self):
        """TC08 - Ordinary accounts cannot promote themselves or inspect others."""
        before = self.auth.store.path.read_bytes()
        with self.assertRaises(ValueError):
            self.auth.update_user(self.student, self.student["id"], "Learner", "admin", True)
        with self.assertRaises(ValueError):
            self.auth.user_progress(self.student, self.admin["id"])
        self.assertEqual(self.auth.store.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
