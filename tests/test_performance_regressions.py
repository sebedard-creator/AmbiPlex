import asyncio
import logging
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

import lz4.frame
import numpy as np

from bake import process_frame
from color_sampling import sample_segments
from led_engine import LedEngine
from monitoring import MonitorMailbox
from player import SlavePlayer
from wled_reader import WledSubtitleReader


ROOT = Path(__file__).resolve().parents[1]
BASELINE = '81db0f00bcdf3cc94db47fc597fb028205fa72ab'


def original_module(filename):
    source = subprocess.check_output(
        ['git', 'show', f'{BASELINE}:{filename}'], cwd=ROOT).decode('utf-8')
    module = types.ModuleType('baseline_' + filename[:-3])
    module.__file__ = str(ROOT / filename)
    exec(compile(source, module.__file__, 'exec'), module.__dict__)
    return module


OLD_LED = original_module('led_engine.py').LedEngine
OLD_BAKE = original_module('bake.py').process_frame


def config(**changes):
    result = dict(leds_top=64, leds_side=36, led_depth=8, led_smoothing=0)
    result.update(changes)
    return result


def crop_state():
    return dict(top=0, bottom=90, frames_top=0, frames_bottom=0)


class ColorEquivalence(unittest.TestCase):
    def test_segment_means_exact(self):
        rng = np.random.default_rng(81)
        for shape in [(90, 160, 3), (0, 160, 3), (90, 0, 3), (3, 7, 3)]:
            for dtype in [np.uint8, np.float32]:
                zone = rng.integers(0, 256, shape, dtype=np.uint8).astype(dtype)
                for axis in [0, 1]:
                    length = zone.shape[1-axis]
                    for count in [1, 36, 64, 200]:
                        for gap in [-3, 0, 5, 100]:
                            step = max(1, length - 2*gap) / count
                            expected = []
                            for i in range(count):
                                a, b = gap+int(i*step), gap+int((i+1)*step)
                                segment = zone[:, a:b] if axis == 0 else zone[a:b, :]
                                expected.append(np.mean(segment, axis=(0, 1))
                                                if segment.size else np.zeros(3))
                            np.testing.assert_array_equal(expected, sample_segments(zone, count, axis, gap))

    def test_sequences_exact_including_smoothing_and_crop(self):
        rng = np.random.default_rng(213)
        frames = rng.integers(0, 256, (160, 90, 160, 3), dtype=np.uint8)
        frames[10:75, :12] = 0
        frames[10:75, 78:] = 0
        frames[75:125, :20] = 0
        frames[75:125, 70:] = 0
        frames[125:130] = 0
        frames[130:140] %= 9
        for start in ['top_left', 'top_right', 'bottom_right', 'bottom_left']:
            for direction in ['clockwise', 'counter_clockwise']:
                a, b = OLD_LED(), LedEngine()
                try:
                    for i, frame in enumerate(frames):
                        cfg = config(led_start_pos=start, led_direction=direction,
                                     led_smoothing=[0, 30, 67, 100][i//40],
                                     offset_top=3, offset_right=-2, offset_bottom=-100,
                                     led_brightness_top=63, led_brightness_left=0)
                        self.assertEqual(a.calculate_colors(frame, cfg), b.calculate_colors(frame, cfg))
                        np.testing.assert_array_equal(a.last_colors, b.last_colors)
                        self.assertEqual((a.crop_top, a.crop_bottom, a.frames_with_new_crop),
                                         (b.crop_top, b.crop_bottom, b.frames_with_new_crop))
                finally:
                    a.close(); b.close()
        for x, y in [(64, 36), (66, 38), (53, 31), (200, 100), (0, 36), (64, 0)]:
            for gap in [0, 7, 50]:
                a, b = OLD_LED(), LedEngine()
                try:
                    for frame in frames[:8]:
                        cfg = config(leds_top=x, leds_side=y, led_corner_gap=gap, disable_autocrop=True)
                        self.assertEqual(a.calculate_colors(frame, cfg), b.calculate_colors(frame, cfg))
                finally:
                    a.close(); b.close()
        for x, y in [(64, 36), (66, 38), (53, 31), (200, 100)]:
            for depth in [1, 8, 25]:
                a, b = crop_state(), crop_state()
                for frame in frames:
                    self.assertEqual(OLD_BAKE(frame, a, x, y, depth), process_frame(frame, b, x, y, depth))
                    self.assertEqual(a, b)

    def test_prebaked_and_ddp_exact(self):
        a, b = OLD_LED(), LedEngine()
        a.close(); b.close()
        a.sock, b.sock = Mock(), Mock()
        rng = np.random.default_rng(8)
        for smoothing in [0, 50, 100]:
            for _ in range(20):
                raw = rng.integers(0, 65536, 200, dtype=np.uint16)
                cfg = config(led_smoothing=smoothing, led_brightness_bottom=29, offset_left=-5)
                ac, bc = a.process_prebaked_colors(raw, cfg), b.process_prebaked_colors(raw, cfg)
                self.assertEqual(ac, bc)
                a.send_ddp('127.0.0.1', ac); b.send_ddp('127.0.0.1', bc)
                self.assertEqual(a.sock.sendto.call_args, b.sock.sendto.call_args)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg is needed for calibration videos')
    def test_real_calibration_videos(self):
        paths = sorted(ROOT.glob('calibration*.mp4'))
        if not paths:
            self.skipTest('Local calibration videos are not included in Git')
        for path in paths:
            cmd = ['ffmpeg', '-v', 'error', '-i', str(path), '-vf',
                   'scale=160:90:force_original_aspect_ratio=decrease,pad=160:90:(ow-iw)/2:(oh-ih)/2',
                   '-frames:v', '90', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
            raw = subprocess.check_output(cmd, timeout=60)
            frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 90, 160, 3)
            self.assertGreater(len(frames), 0)
            a, b = OLD_LED(), LedEngine()
            ca, cb = crop_state(), crop_state()
            try:
                for frame in frames:
                    self.assertEqual(a.calculate_colors(frame, config(led_smoothing=30)),
                                     b.calculate_colors(frame, config(led_smoothing=30)), path.name)
                    self.assertEqual(OLD_BAKE(frame, ca, 64, 36, 8), process_frame(frame, cb, 64, 36, 8))
            finally:
                a.close(); b.close()


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reader = WledSubtitleReader(self.temp.name)
        self.addCleanup(self.reader.close)
        self.video = str(Path(self.temp.name) / 'film.mkv')
        self.path = Path(self.video).with_suffix('.wledsub.lz4')

    def write_movie(self, x=64, y=36, value=123, frames=100):
        raw = np.full((frames, 2*(x+y)), value, dtype=np.uint16)
        with lz4.frame.open(self.path, 'wb') as f:
            f.write(struct.pack('<4s4sfIHH12x', b'WLED', b'0003', 24., 120, x, y))
            f.write(raw.tobytes())
        return raw

    def test_missing_appearing_replaced_and_removed(self):
        r = self.reader
        self.assertFalse(r.load_if_compatible(self.video, 64, 36))
        self.write_movie()
        self.assertFalse(r.load_if_compatible(self.video, 64, 36))
        r._next_check = 0
        self.assertTrue(r.load_if_compatible(self.video, 64, 36))
        held_frame = r.get_colors_at_time(0)
        raw_path = r._raw_path
        self.assertEqual(r.total_frames, 100)
        np.testing.assert_array_equal(r.get_colors_at_time(-1), held_frame)
        np.testing.assert_array_equal(r.get_colors_at_time(999999), held_frame)
        self.write_movie(value=456)
        r._next_check = 0
        self.assertTrue(r.load_if_compatible(self.video, 64, 36))
        self.assertTrue(np.all(r.get_colors_at_time(0) == 456))
        self.assertTrue(np.all(held_frame == 123))
        self.path.unlink()
        r._next_check = 0
        self.assertFalse(r.load_if_compatible(self.video, 64, 36))
        self.assertFalse(r.is_active())
        self.assertFalse(os.path.exists(raw_path))

    def test_cached_hits_misses_and_dimension_changes(self):
        self.write_movie()
        r = self.reader
        self.assertTrue(r.load_if_compatible(self.video, 64, 36))
        with patch('wled_reader.os.stat', side_effect=AssertionError('unexpected stat')):
            for _ in range(100):
                self.assertTrue(r.load_if_compatible(self.video, 64, 36))
        with self.assertLogs('WledReader', level=logging.WARNING):
            self.assertFalse(r.load_if_compatible(self.video, 66, 38))
        r._next_check = 0
        with patch('wled_reader.lz4.frame.open', side_effect=AssertionError('reopened incompatible file')):
            self.assertFalse(r.load_if_compatible(self.video, 66, 38))
        self.assertTrue(r.load_if_compatible(self.video, 64, 36))
        r.close()
        with patch('wled_reader.os.remove', side_effect=AssertionError('repeated delete')):
            r.close()

    def test_decompression_reads_bounded_chunks(self):
        expected = self.write_movie(frames=4000)
        real_open = lz4.frame.open
        sizes = []
        def tracked_open(*args, **kwargs):
            f = real_open(*args, **kwargs)
            read = f.read
            def tracked_read(size=-1):
                sizes.append(size)
                return read(size)
            f.read = tracked_read
            return f
        with patch('wled_reader.lz4.frame.open', side_effect=tracked_open):
            self.assertTrue(self.reader.load_if_compatible(self.video, 64, 36))
        self.assertTrue(all(0 < n <= 1024*1024 for n in sizes))
        self.assertGreaterEqual(len(sizes), 4)
        np.testing.assert_array_equal(self.reader.memmap_array, expected)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_shutdown_releases_resources_after_loop_cancellation(self):
        import web
        task = asyncio.create_task(asyncio.Event().wait())
        reader, player, engine, sync = Mock(), Mock(), Mock(), Mock()
        with patch.object(web, 'sync_task', task), \
                patch.object(web, 'wled_reader_instance', reader), \
                patch.object(web, 'player_instance', player), \
                patch.object(web, 'led_engine_instance', engine), \
                patch.object(web, 'sync_instance', sync):
            await web.shutdown_event()
        self.assertTrue(task.cancelled())
        reader.close.assert_called_once()
        player.quit.assert_called_once()
        engine.close.assert_called_once()
        sync.notifier.stop.assert_called_once()

    async def test_movie_changed_during_load_does_not_emit_stale_colors(self):
        import web
        sync = types.SimpleNamespace(is_playing=True, current_media_path='A.mkv',
                                     current_view_offset=1000, connect=Mock(), start_websocket_listener=Mock())
        reader = Mock()
        reader.is_active.return_value = False
        reader.needs_check.return_value = True
        visited = []
        async def ensure(path, x, y):
            visited.append(path)
            if path == 'A.mkv':
                sync.current_media_path = 'B.mkv'
            return True
        reader.ensure_compatible = ensure
        engine = Mock()
        engine.process_prebaked_colors.return_value = [[10, 20, 30]]
        received = []
        async def broadcast(data):
            if data['type'] == 'monitoring':
                received.append(data)
                raise asyncio.CancelledError()
        async def no_delay(seconds):
            return None
        with patch.object(web, 'load_config', return_value=config(wled_ip='127.0.0.1')), \
                patch.object(web, 'PlexSynchronizer', return_value=sync), \
                patch.object(web, 'WledSubtitleReader', return_value=reader), \
                patch.object(web, 'LedEngine', return_value=engine), \
                patch.object(web, 'SlavePlayer') as player, \
                patch.object(web, 'broadcast', side_effect=broadcast), \
                patch.object(web.asyncio, 'sleep', side_effect=no_delay):
            with self.assertRaises(asyncio.CancelledError):
                await web.background_sync_loop()
        self.assertEqual(visited, ['A.mkv', 'B.mkv'])
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]['colors'], [[10, 20, 30]])
        engine.send_ddp.assert_called_once()
        player.assert_not_called()
        reader.close.assert_called_once()

    async def test_slow_monitor_keeps_latest_frame_and_all_events(self):
        q = MonitorMailbox()
        await q.put({'type': 'info', 'message': 'first'})
        for i in range(10000):
            await q.put({'type': 'monitoring', 'offset': i})
        await q.put({'type': 'preset_changed', 'combo': 'second'})
        self.assertEqual((await q.get())['message'], 'first')
        self.assertEqual((await q.get())['combo'], 'second')
        self.assertEqual((await q.get())['offset'], 9999)
        waiting = asyncio.create_task(q.get())
        await asyncio.sleep(0)
        self.assertFalse(waiting.done())
        await q.put({'type': 'monitoring', 'offset': 10000})
        self.assertEqual((await waiting)['offset'], 10000)

    async def test_reader_worker_does_not_block_and_cancellation_cleans_up(self):
        with tempfile.TemporaryDirectory() as temp:
            r = WledSubtitleReader(temp)
            entered, release = threading.Event(), threading.Event()
            def slow_load(*args):
                entered.set()
                release.wait(3)
                return False
            with patch.object(r, 'load_if_compatible', side_effect=slow_load), patch.object(r, 'close') as close:
                task = asyncio.create_task(r.ensure_compatible('test.mkv', 64, 36))
                try:
                    self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                    self.assertFalse(task.done())
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(task.done())
                finally:
                    release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                close.assert_called_once()


class PlayerTests(unittest.TestCase):
    def test_control_deduplication_observation_and_position(self):
        with patch('player._create_hidden_window', return_value=None), patch('player.mpv.MPV') as mpv:
            player = SlavePlayer()
        backend = types.SimpleNamespace(time_pos=1.25)
        player.player = backend
        player.play(); player.set_speed(1.0)
        del backend.pause; del backend.speed
        player.play(); player.set_speed(1.0)
        self.assertFalse(hasattr(backend, 'pause'))
        self.assertFalse(hasattr(backend, 'speed'))
        player._control_changed('pause', True)
        player._control_changed('speed', 0.95)
        player.play(); player.set_speed(1.0)
        self.assertFalse(backend.pause)
        self.assertEqual(backend.speed, 1.0)
        self.assertEqual(player.get_offset_ms(), 1250)
        player.pause()
        self.assertTrue(backend.pause)
        player._cache_controls = False
        del backend.pause
        player.pause()
        self.assertTrue(backend.pause)


class RoverTests(unittest.TestCase):
    def test_slider_does_not_create_widgets(self):
        import rover
        instance = types.SimpleNamespace(threads_label=Mock())
        with patch.object(rover.ctk, 'CTkScrollableFrame') as scroll, \
                patch.object(rover.ctk, 'CTkFrame') as frame:
            for value in range(17):
                rover.AmbiPlexRover.update_threads_label(instance, value)
        scroll.assert_not_called()
        frame.assert_not_called()
        instance.threads_label.configure.assert_called_with(text='Threads : 16')


if __name__ == '__main__':
    unittest.main()
