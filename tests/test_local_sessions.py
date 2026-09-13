import types
import unittest
from unittest.mock import Mock, patch

from sync import PlexSynchronizer


def session(key=1, client='tv', title='Sony Bravia', local=True,
            location='lan', relayed=False, address='192.168.1.50', state='playing'):
    player = types.SimpleNamespace(machineIdentifier=client, title=title, local=local,
                                   relayed=relayed, address=address, state=state)
    return types.SimpleNamespace(type='movie', sessionKey=key, player=player,
                                 session=types.SimpleNamespace(location=location))


def notification(key=1, client='tv', state='playing', rating='123', offset=1000):
    return dict(sessionKey=key, clientIdentifier=client, state=state,
                ratingKey=rating, viewOffset=offset)


class LocalSessionTests(unittest.TestCase):
    def setUp(self):
        self.sync = PlexSynchronizer('http://127.0.0.1:32400', '', 'Sony_Bravia')
        self.sync._log = Mock()
        self.sync.server = Mock()
        self.sync.server.sessions.return_value = []
        media = types.SimpleNamespace(parts=[types.SimpleNamespace(file='local_movie.mkv')],
                                      videoResolution='1080', videoCodec='h264', videoFrameRate='24')
        self.sync.server.fetchItem.return_value = types.SimpleNamespace(type='movie', title='Test', media=[media])

    def emit(self, *notifications):
        self.sync._on_plex_message(dict(type='playing', PlaySessionStateNotification=list(notifications)))

    def refresh(self, sessions):
        self.sync.server.sessions.return_value = sessions
        self.sync._sessions_checked_at = float('-inf')

    def test_remote_private_ip_cannot_override_plex(self):
        for address in ['192.168.1.5', '10.0.0.4', '127.0.0.1', '172.16.1.3', '::1']:
            with self.subTest(address=address):
                self.refresh([session(local=False, location='wan', address=address)])
                self.emit(notification())
                self.assertFalse(self.sync.is_playing)
                self.assertIsNone(self.sync.current_media_path)
        self.sync.server.fetchItem.assert_not_called()

    def test_remote_relayed_unknown_and_conflicting_flags_rejected(self):
        for kwargs in [dict(local=True, location='wan'), dict(local=True, location='cellular'),
                       dict(local=True, relayed=True), dict(local=None), dict(local='0'),
                       dict(local=False, location='lan')]:
            with self.subTest(kwargs=kwargs):
                self.refresh([session(**kwargs)])
                self.emit(notification())
                self.assertFalse(self.sync.is_playing)
        self.sync.server.fetchItem.assert_not_called()

    def test_named_local_tv_starts_and_updates_play_pause_seek(self):
        self.refresh([session(title='SONY   BRAVIA')])
        self.emit(notification())
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.current_media_path, 'local_movie.mkv')
        self.assertEqual(self.sync.master_session_key, '1')
        self.emit(notification(state='paused', offset=2000))
        self.assertFalse(self.sync.is_playing)
        self.assertEqual(self.sync.current_view_offset, 2000)
        self.assertEqual(self.sync.current_media_path, 'local_movie.mkv')
        self.emit(notification(offset=9000))
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.last_ping_offset, 9000)
        self.sync.server.fetchItem.assert_called_once_with(123)

    def test_local_without_bandwidth_session_is_accepted(self):
        local = session(address='fe80::1234')
        local.session = None
        self.refresh([local])
        self.emit(notification())
        self.assertTrue(self.sync.is_playing)

    def test_no_fallback_when_configured_tv_is_absent(self):
        for name in ['Firefox', 'Other Sony Bravia', 'Sony Bravia Remote']:
            self.refresh([session(title=name)])
            self.emit(notification())
            self.assertFalse(self.sync.is_playing)
        self.sync.server.fetchItem.assert_not_called()

    def test_blank_target_still_allows_automatic_local_selection(self):
        self.sync.master_client = ''
        self.refresh([session(local=False, location='wan'), session(2, 'browser', title='Firefox')])
        self.emit(notification(), notification(2, 'browser'))
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.master_client_id, 'browser')

    def test_remote_with_same_client_id_cannot_hijack_local_session(self):
        self.refresh([session(), session(2, local=False, location='wan')])
        self.emit(notification())
        self.emit(notification(2, rating='999', offset=70000))
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.master_session_key, '1')
        self.assertEqual(self.sync.current_rating_key, '123')
        self.assertEqual(self.sync.last_ping_offset, 1000)
        self.sync.server.fetchItem.assert_called_once_with(123)

    def test_remote_stop_does_not_stop_local_and_missing_keys_rejected(self):
        self.refresh([session()])
        self.emit(notification())
        self.emit(notification(2, state='stopped'))
        self.emit(notification(None, rating='999'))
        self.emit(notification(1, client=None, rating='999'))
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.current_rating_key, '123')

    def test_local_stop_releases_client_and_next_session_can_start(self):
        self.refresh([session()])
        self.emit(notification())
        self.emit(notification(state='stopped'))
        self.assertFalse(self.sync.is_playing)
        self.assertIsNone(self.sync.master_client_id)
        self.assertIsNone(self.sync.current_media_path)
        self.refresh([session(3, 'new-tv')])
        self.emit(notification(3, 'new-tv'))
        self.assertTrue(self.sync.is_playing)
        self.assertEqual(self.sync.master_client_id, 'new-tv')

    def test_disappeared_or_remote_session_releases_master(self):
        self.refresh([session()])
        self.emit(notification())
        self.refresh([session(local=False, location='wan')])
        self.emit(notification())
        self.assertFalse(self.sync.is_playing)
        self.assertIsNone(self.sync.current_media_path)
        self.refresh([])
        self.emit(notification())
        self.assertFalse(self.sync.is_playing)

    def test_two_local_tabs_prioritize_playing_session(self):
        self.refresh([session(1, state='paused'), session(2)])
        self.emit(notification(1, state='paused'), notification(2))
        self.assertEqual(self.sync.master_session_key, '2')

    def test_unknown_session_is_not_trusted_and_queries_are_rate_limited(self):
        with patch('sync.time.monotonic', return_value=10):
            self.refresh([session()])
            for _ in range(100):
                self.emit(notification(999, rating='999'))
            self.sync.server.sessions.assert_called_once()
            self.sync.server.fetchItem.assert_not_called()
            self.emit(notification())
            self.assertTrue(self.sync.is_playing)
        with patch('sync.time.monotonic', return_value=11.1):
            self.emit(notification())
        self.assertEqual(self.sync.server.sessions.call_count, 2)

    def test_session_lookup_failure_does_not_reuse_old_authorization(self):
        self.refresh([session()])
        self.emit(notification())
        self.sync._sessions_checked_at = float('-inf')
        self.sync.server.sessions.side_effect = RuntimeError('offline')
        self.emit(notification(2, rating='999'))
        self.assertFalse(self.sync.is_playing)
        self.assertIsNone(self.sync.master_client_id)
        self.assertEqual(self.sync._sessions_cache, [])


if __name__ == '__main__':
    unittest.main()
