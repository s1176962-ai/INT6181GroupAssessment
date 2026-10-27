"""Window preferences and small-screen boundaries."""

import tempfile
import unittest
from pathlib import Path

from learning_platform.display import DisplaySettings, window_size
from learning_platform.storage import DataError


class DisplayTests(unittest.TestCase):
    def test_preferences_persist_and_do_not_change_language(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            language = path / "settings.json"
            language.write_text('{"language":"en"}', encoding="utf-8")
            settings = DisplaySettings(path)
            self.assertEqual(settings.load(), {"size": "auto", "compact": True})
            settings.save("960x640", False)
            self.assertEqual(DisplaySettings(path).load(), {"size": "960x640", "compact": False})
            self.assertEqual(language.read_text(encoding="utf-8"), '{"language":"en"}')

    def test_corrupt_preferences_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = DisplaySettings(Path(folder))
            settings.store.write({"size": "invalid", "compact": True})
            before = settings.store.path.read_bytes()
            with self.assertRaises(DataError):
                settings.save("auto", True)
            self.assertEqual(settings.store.path.read_bytes(), before)

    def test_presets_fit_laptop_screen(self):
        self.assertEqual(window_size("auto", 1366, 768), (1040, 648))
        self.assertEqual(window_size("1280x800", 1024, 768), (944, 648))
        self.assertEqual(window_size("960x640", 1920, 1080), (960, 640))
