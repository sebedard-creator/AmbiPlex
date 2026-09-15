import io
import json
import os
import lz4.frame
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from rover_batch import (DEFAULTS, VideoFile, conflicting_outputs, discover_videos,
                         encode_batch, load_settings, track_path)


class RoverBatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_scan_recursive_extensions_tracks_and_order(self):
        (self.root / "sub").mkdir()
        for name in ["B.MKV", "a.mp4", "note.txt", "B.wledsub.lz4", "sub/c.avi"]:
            (self.root / name).touch()
        errors = []
        rows = list(discover_videos(self.root, threading.Event(), errors.append))
        self.assertEqual([Path(row.path).name for row in rows], ["a.mp4", "B.MKV", "c.avi"])
        self.assertEqual([row.has_track for row in rows], [False, True, False])
        self.assertEqual(errors, [])

    def test_scan_cancellation_and_missing_folder(self):
        (self.root / "a.mkv").touch()
        stop = threading.Event()
        stop.set()
        self.assertEqual(list(discover_videos(self.root, stop, self.fail)), [])
        errors = []
        self.assertEqual(list(discover_videos(self.root / "missing", threading.Event(), errors.append)), [])
        self.assertEqual(len(errors), 1)

    def test_settings_only_encoding_fields_no_mutation(self):
        path = self.root / "config.json"
        content = json.dumps({**DEFAULTS, "plex_token": "synthetic-test-token", "leds_top": 200})
        path.write_text(content, encoding="utf-8")
        settings = load_settings(path)
        self.assertEqual(set(settings), set(DEFAULTS))
        self.assertEqual(settings["leds_top"], 200)
        self.assertEqual(path.read_text(encoding="utf-8"), content)
        self.assertEqual(load_settings(self.root / "missing.json"), DEFAULTS)

    def test_invalid_config_is_not_silently_used(self):
        path = self.root / "config.json"
        for value in ["broken", "[]", '{"leds_top": -1}', '{"leds_top": 0, "leds_side": 0}', '{"led_depth": 0}']:
            path.write_text(value, encoding="utf-8")
            with self.assertRaises(ValueError):
                load_settings(path)

    def test_output_collisions(self):
        files = [str(self.root / name) for name in ["movie.mkv", "movie.mp4", "other.avi"]]
        self.assertEqual(conflicting_outputs(files), [files[1]])
        self.assertEqual(conflicting_outputs([files[0], str(self.root / "sub/movie.mp4")]), [])

    def process(self, code=0, lines="Progression: 42.50% (50/100)\n"):
        process = Mock()
        process.stdout = io.StringIO(lines)
        process.wait.return_value = code
        context = Mock()
        context.__enter__ = Mock(return_value=process)
        context.__exit__ = Mock(return_value=False)
        return context

    def test_batch_success_preserves_bake_parameters_and_progress(self):
        path = str(self.root / "movie.mkv")
        track_path(path).touch()
        events = []
        settings = {**DEFAULTS, "ffmpeg_threads": 3}
        with patch("rover_batch.subprocess.Popen", return_value=self.process()) as popen:
            encode_batch([path], settings, threading.Event(), lambda *event: events.append(event))
        command = popen.call_args.args[0]
        self.assertEqual(command[3:], [path, "--leds-x", "64", "--leds-y", "36", "--depth", "8", "--threads", "3"])
        self.assertEqual(command[1], "-u")
        progress = next(payload for kind, payload in events if kind == "progress")
        self.assertEqual(progress[3], 42.5)
        self.assertEqual(events[-1], ("batch_done", (1, 0, 0)))

    def test_failure_is_counted_and_next_file_runs(self):
        paths = [str(self.root / name) for name in ["a.mkv", "b.mkv"]]
        for path in paths:
            track_path(path).write_bytes(b"existing")
        events = []
        with patch("rover_batch.subprocess.Popen", side_effect=[self.process(1), self.process(0)]):
            encode_batch(paths, DEFAULTS, threading.Event(), lambda *event: events.append(event))
        self.assertEqual(events[-1], ("batch_done", (1, 1, 0)))
        self.assertEqual(track_path(paths[0]).read_bytes(), b"existing")

    def test_missing_output_and_spawn_failure(self):
        for process in [self.process(0), OSError("synthetic spawn failure")]:
            events = []
            kwargs = {"side_effect": process} if isinstance(process, OSError) else {"return_value": process}
            with patch("rover_batch.subprocess.Popen", **kwargs):
                encode_batch([str(self.root / "missing.mkv")], DEFAULTS, threading.Event(), lambda *event: events.append(event))
            self.assertEqual(events[-1], ("batch_done", (0, 1, 0)))

    def test_stop_finishes_current_file_without_starting_next(self):
        paths = [str(self.root / name) for name in ["a.mkv", "b.mkv"]]
        track_path(paths[0]).touch()
        stop, events = threading.Event(), []

        def emit(kind, payload):
            events.append((kind, payload))
            if kind == "progress":
                stop.set()

        with patch("rover_batch.subprocess.Popen", return_value=self.process()) as popen:
            encode_batch(paths, DEFAULTS, stop, emit)
        self.assertEqual(popen.call_count, 1)
        self.assertEqual(events[-1], ("batch_done", (1, 0, 1)))

    def test_stop_before_start_and_progress_clamp(self):
        stop, events = threading.Event(), []
        stop.set()
        with patch("rover_batch.subprocess.Popen") as popen:
            encode_batch(["unused.mkv"], DEFAULTS, stop, lambda *event: events.append(event))
        popen.assert_not_called()
        self.assertEqual(events[-1], ("batch_done", (0, 0, 1)))
        stop.clear()
        path = str(self.root / "a.mkv")
        track_path(path).touch()
        with patch("rover_batch.subprocess.Popen", return_value=self.process(lines="Progression: 102.30%\n")):
            encode_batch([path], DEFAULTS, stop, lambda *event: events.append(event))
        self.assertEqual(next(data[3] for kind, data in events if kind == "progress"), 100)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is not installed")
    def test_real_bake_output_identical_to_direct_command(self):
        path = self.root / "sample.mp4"
        subprocess.run([shutil.which("ffmpeg"), "-v", "error", "-f", "lavfi", "-i",
                        "testsrc2=size=320x180:rate=24", "-t", "1", "-c:v", "mpeg4", str(path)],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        bake = Path(__file__).resolve().parents[1] / "bake.py"
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run([sys.executable, str(bake), str(path), "--leds-x", "64",
                        "--leds-y", "36", "--depth", "8", "--threads", "0"],
                       env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        before = lz4.frame.decompress(track_path(path).read_bytes())
        events = []
        encode_batch([str(path)], DEFAULTS, threading.Event(), lambda *event: events.append(event))
        self.assertEqual(events[-1], ("batch_done", (1, 0, 0)))
        self.assertEqual(lz4.frame.decompress(track_path(path).read_bytes()), before)
        self.assertEqual(len(before), 32 + 24 * 400)


class RoverInterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from rover import AmbiPlexRover
        with patch("rover.load_settings", return_value=DEFAULTS.copy()):
            cls.app = AmbiPlexRover()
        cls.app.withdraw()
        cls.callback_errors = []
        cls.app.report_callback_exception = lambda *args: cls.callback_errors.append(args)

    @classmethod
    def tearDownClass(cls):
        cls.app.on_close()

    def setUp(self):
        self.callback_errors.clear()
        self.app.is_encoding = self.app.is_scanning = False
        self.app.stop_batch.clear()
        self.app.close_when_done = False
        self.app.filter_generation += 1
        self.app.filtering = False
        self.app.records.clear()
        self.app.states.clear()
        self.app.table.delete(*self.app.table.get_children())
        self.app.search.configure(state="normal")
        self.app.search.delete(0, "end")
        self.app.view_var.set("Tous")
        self.app.set_controls()
        self.app.handle_event("scan_rows", [VideoFile("a.mkv", "Alpha.mkv", False), VideoFile("b.mp4", "Beta.mp4", True)])

    def tearDown(self):
        self.assertEqual(self.callback_errors, [])

    def pump(self, predicate):
        deadline = time.monotonic() + 5
        while not predicate() and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_selection_filters_and_empty_state(self):
        self.app.select_files("missing")
        self.assertEqual(self.app.table.selection(), ("a.mkv",))
        self.app.select_files("all")
        self.assertEqual(len(self.app.table.selection()), 2)
        self.app.view_var.set("Avec piste")
        self.app.apply_filter()
        self.assertEqual(self.app.table.selection(), ("b.mp4",))
        self.app.search.insert(0, "no match")
        self.app.apply_filter()
        self.assertEqual(self.app.table.get_children(), ())
        self.assertEqual(self.app.btn_start.cget("state"), "disabled")

    def test_progress_errors_and_stop_summary(self):
        self.app.is_encoding = True
        self.app.states["b.mp4"] = "En attente"
        self.app.handle_event("started", ("a.mkv", 0, 2))
        self.app.handle_event("progress", ("a.mkv", 0, 2, 50.0, "Progression: 50%"))
        self.assertAlmostEqual(self.app.progress_bar.get(), 0.25)
        self.app.request_stop()
        self.assertTrue(self.app.stop_batch.is_set())
        self.app.handle_event("file_done", ("a.mkv", False, "test error", 1, 2))
        self.app.handle_event("batch_done", (0, 1, 1))
        self.assertEqual(self.app.states, {"a.mkv": "Erreur", "b.mp4": "Non traité"})
        self.app.view_var.set("En erreur")
        self.app.apply_filter()
        self.assertEqual(self.app.table.get_children(), ("a.mkv",))

    def test_completed_track_and_bounded_log(self):
        self.app.handle_event("file_done", ("a.mkv", True, "", 1, 1))
        self.assertTrue(self.app.records["a.mkv"].has_track)
        for i in range(250):
            self.app.append_log(f"test line {i}")
        self.assertLessEqual(int(self.app.log.index("end-1c").split(".")[0]), 201)
        self.assertIn("test line 249", self.app.log.get("1.0", "end"))

    def test_large_scan_and_filter_are_chunked(self):
        records = [VideoFile(f"file{i}.mkv", f"File {i}.mkv", False) for i in range(3000)]
        for start in range(0, len(records), 200):
            self.app.handle_event("scan_rows", records[start:start + 200])
        self.app.apply_filter()
        self.assertTrue(self.app.filtering)
        self.assertLessEqual(len(self.app.table.get_children()), 200)
        self.pump(lambda: not self.app.filtering)
        self.assertEqual(len(self.app.table.get_children()), 3002)

    def test_worker_queue_and_scan_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "test.mkv").touch()
            self.app.current_folder = folder
            self.app.scan_folder()
            self.pump(lambda: not self.app.is_scanning)
            self.assertEqual(len(self.app.records), 1)
            self.assertEqual(self.app.btn_refresh.cget("state"), "normal")

    def test_batch_snapshots_threads_on_ui_thread(self):
        self.app.select_files("missing")
        self.app.threads_var.set(3)
        with patch("rover.load_settings", return_value=DEFAULTS.copy()), patch("rover.threading.Thread") as worker:
            self.app.start_batch_thread()
        self.assertEqual(worker.call_args.kwargs["args"][1]["ffmpeg_threads"], 3)
        self.assertEqual(self.app.threads_slider.cget("state"), "disabled")
        self.app.is_encoding = False

    def test_close_during_batch_waits_and_can_be_declined(self):
        self.app.is_encoding = True
        with patch("rover.messagebox.askyesno", return_value=False):
            self.app.on_close()
        self.assertFalse(self.app.close_when_done)
        self.assertFalse(self.app.stop_batch.is_set())
        with patch("rover.messagebox.askyesno", return_value=True):
            self.app.on_close()
        self.assertTrue(self.app.close_when_done)
        self.assertTrue(self.app.stop_batch.is_set())
        self.assertFalse(self.app.closing)
        self.app.is_encoding = False

    def test_duplicate_output_and_overwrite_confirmation(self):
        self.app.handle_event("scan_rows", [VideoFile("a.mp4", "a.mp4", False)])
        self.app.table.selection_set(["a.mkv", "a.mp4"])
        with patch("rover.messagebox.showerror") as error, patch("rover.threading.Thread") as worker:
            self.app.start_batch_thread()
        error.assert_called_once()
        worker.assert_not_called()
        self.app.table.selection_set(["b.mp4"])
        with patch("rover.track_path") as output, patch("rover.messagebox.askyesno", return_value=False) as question, patch("rover.threading.Thread") as worker:
            output.return_value.exists.return_value = True
            self.app.start_batch_thread()
        question.assert_called_once()
        worker.assert_not_called()

    def test_native_layout_controls_fit_both_window_sizes(self):
        self.app.deiconify()
        try:
            for size in ["1120x820", "880x720"]:
                self.app.geometry(size)
                self.app.update()
                self.app.status_label.configure(text="[1/2] " + "Long video filename " * 12 + " · Progression: 50.00%")
                self.app.update()
                for widget in [self.app.btn_start, self.app.btn_stop, self.app.threads_slider,
                               self.app.count_label, self.app.search, self.app.folder_entry,
                               self.app.log, self.app.table, *self.app.select_buttons]:
                    parent = widget.master
                    self.assertGreater(widget.winfo_width(), 0)
                    self.assertGreaterEqual(widget.winfo_x(), 0)
                    self.assertGreaterEqual(widget.winfo_y(), 0)
                    self.assertLessEqual(widget.winfo_x() + widget.winfo_width(), parent.winfo_width() + 2, (size, str(widget)))
                    self.assertLessEqual(widget.winfo_y() + widget.winfo_height(), parent.winfo_height() + 2, (size, str(widget)))
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.app.winfo_rooty() + self.app.winfo_height() + 2)
        finally:
            self.app.withdraw()


if __name__ == "__main__":
    unittest.main()
