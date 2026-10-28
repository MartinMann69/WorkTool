"""Real process exclusion, crash recovery, and duplicate-launch handoff."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QSignalSpy

from tslibrary_ui.app import create_app, main
from tslibrary_ui.single_instance import SingleInstance
from tslibrary_ui.storage import StorageError


ROOT = Path(__file__).resolve().parents[1]
WORKER = """
import sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTimer
from tslibrary_ui.single_instance import SingleInstance
app = QCoreApplication([])
name, barrier, stop = sys.argv[1:]
if barrier != '-':
    import time
    while not Path(barrier).exists():
        time.sleep(.01)
guard = SingleInstance(name=name)
primary = guard.start()
print('primary' if primary else 'secondary', flush=True)
if primary:
    timer = QTimer()
    timer.timeout.connect(lambda: app.quit() if Path(stop).exists() else None)
    timer.start(30)
    QTimer.singleShot(15000, app.quit)
    app.exec()
guard.close()
"""


class SingleInstanceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.name = "TSLibrary.Test." + uuid4().hex
        self.instances = []
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        for instance in self.instances:
            instance.close()
            instance.deleteLater()
        self.app.processEvents()

    def instance(self):
        instance = SingleInstance(name=self.name)
        self.instances.append(instance)
        return instance

    def worker(self, barrier="-", stop="-"):
        process = subprocess.Popen(
            [sys.executable, "-c", WORKER, self.name, str(barrier), str(stop)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(process)
        return process

    def test_duplicate_process_exits_and_notifies_original(self):
        first = self.instance()
        self.assertTrue(first.start())
        spy = QSignalSpy(first.activation_requested)
        second = self.worker()
        stdout, stderr = second.communicate(timeout=10)
        self.assertEqual(second.returncode, 0, stderr)
        self.assertEqual(stdout.strip(), "secondary")
        self.app.processEvents()
        self.assertEqual(spy.count(), 1)

    def test_simultaneous_startups_have_exactly_one_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            barrier = Path(directory) / "start"
            stop = Path(directory) / "stop"
            workers = [self.worker(barrier, stop) for _ in range(4)]
            barrier.touch()
            results = [worker.stdout.readline().strip() for worker in workers]
            stop.touch()
            for worker in workers:
                _, stderr = worker.communicate(timeout=10)
                self.assertEqual(worker.returncode, 0, stderr)
            self.assertEqual(results.count("primary"), 1, results)
            self.assertEqual(results.count("secondary"), 3, results)

    def test_new_instance_can_start_after_owner_crashes(self):
        first = self.worker()
        self.assertEqual(first.stdout.readline().strip(), "primary")
        first.kill()
        first.communicate(timeout=5)
        self.assertTrue(self.instance().start())

    def test_normal_shutdown_releases_the_instance(self):
        first = self.instance()
        self.assertTrue(first.start())
        first.close()
        first.close()  # Both aboutToQuit and the startup finally block call this.
        self.assertTrue(self.instance().start())

    def test_duplicate_startup_never_loads_data_or_constructs_windows(self):
        with patch("tslibrary_ui.app.SingleInstance") as guard_type, \
             patch("tslibrary_ui.app.create_repository") as repository, \
             patch("tslibrary_ui.app.PreviewController") as controller:
            guard_type.return_value.start.return_value = False
            guard_type.return_value.notified = True
            self.assertEqual(main(), 0)
            repository.assert_not_called()
            controller.assert_not_called()

    def test_failed_startup_releases_the_instance(self):
        first = self.instance()
        with patch("tslibrary_ui.app.SingleInstance", return_value=first), \
             patch("tslibrary_ui.app.create_repository"), \
             patch("tslibrary_ui.app.PreviewController", side_effect=StorageError("fixture")), \
             patch("tslibrary_ui.app.QMessageBox.exec"), \
             patch("tslibrary_ui.app.QMessageBox.clickedButton", return_value=None):
            self.assertEqual(main(), 1)
        self.assertTrue(self.instance().start())


if __name__ == "__main__":
    unittest.main()
