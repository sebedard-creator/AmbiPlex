import concurrent.futures
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chiaki_launcher import ChiakiLauncher, find_chiaki


class ChiakiFinderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.enterContext(patch.dict(os.environ, {}, clear=True))
        self.enterContext(patch('chiaki_launcher.Path.home', return_value=self.home))
        self.which = self.enterContext(patch('chiaki_launcher.shutil.which', return_value=None))

    def executable(self, relative):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_explicit_path(self):
        executable = self.executable('custom/chiaki.exe')
        os.environ['AMBIPLEX_CHIAKI_PATH'] = str(executable)
        self.assertEqual(find_chiaki(), executable)

    def test_invalid_explicit_path_never_falls_back(self):
        executable = self.executable('path/chiaki.exe')
        self.which.return_value = str(executable)
        wrong = self.executable('other.exe')
        for value in ['chiaki.exe', str(wrong), str(self.home / 'missing/chiaki.exe')]:
            with self.subTest(value=value):
                os.environ['AMBIPLEX_CHIAKI_PATH'] = value
                with self.assertRaises(FileNotFoundError):
                    find_chiaki()

    def test_path(self):
        executable = self.executable('path/chiaki-ng.exe')
        self.which.return_value = str(executable)
        self.assertEqual(find_chiaki(), executable)

    def test_program_files(self):
        executable = self.executable('installed/chiaki-ng/chiaki.exe')
        os.environ['ProgramFiles'] = str(self.home / 'installed')
        self.assertEqual(find_chiaki(), executable)

    def test_portable_installation(self):
        executable = self.executable('Downloads/AmbiPlex-PS4/chiaki-ng-1.10.0/app/chiaki-ng-Win/chiaki.exe')
        self.assertEqual(find_chiaki(), executable)


class ChiakiLaunchTests(unittest.TestCase):
    def setUp(self):
        self.launcher = ChiakiLauncher()
        self.enterContext(patch('chiaki_launcher.os.name', 'nt'))
        self.inventory = self.enterContext(patch('chiaki_launcher.subprocess.run',
            return_value=SimpleNamespace(stdout='"python.exe","100","Console","1","1024 K"\n')))
        self.find = self.enterContext(patch('chiaki_launcher.find_chiaki',
            return_value=Path('C:/Apps/Chiaki/chiaki.exe')))
        self.process = Mock()
        self.process.poll.return_value = None
        self.spawn = self.enterContext(patch('chiaki_launcher.subprocess.Popen', return_value=self.process))

    def test_launch_and_repeat_do_not_duplicate(self):
        self.assertEqual(self.launcher.start()['status'], 'started')
        self.assertEqual(self.launcher.start()['status'], 'already_running')
        self.inventory.assert_called_once()
        self.spawn.assert_called_once_with(
            [str(self.find.return_value)], cwd=str(self.find.return_value.parent), shell=False,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_manually_started_instance(self):
        self.inventory.return_value.stdout = '"chiaki.exe","101","Console","1","1024 K"\n'
        self.assertEqual(self.launcher.start()['status'], 'already_running')
        self.find.assert_not_called()
        self.spawn.assert_not_called()

    def test_concurrent_launches_spawn_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.launcher.start()['status'], range(4)))
        self.assertEqual(results.count('started'), 1)
        self.spawn.assert_called_once()

    def test_exited_process_can_be_launched_again(self):
        self.launcher.start()
        self.process.poll.return_value = 0
        self.assertEqual(self.launcher.start()['status'], 'started')
        self.assertEqual(self.spawn.call_count, 2)

    def test_inventory_failure_never_spawns(self):
        self.inventory.return_value.stdout = ''
        with self.assertRaises(OSError):
            self.launcher.start()
        self.inventory.side_effect = subprocess.TimeoutExpired('tasklist', 3)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.launcher.start()
        self.spawn.assert_not_called()

    def test_non_windows_never_spawns(self):
        with patch('chiaki_launcher.os.name', 'posix'):
            with self.assertRaises(NotImplementedError):
                self.launcher.start()
        self.inventory.assert_not_called()
        self.spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
