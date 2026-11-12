"""Unit tests for the media player backends behind the HA facade."""

from unittest.mock import MagicMock

from linux_voice_assistant.peripheral_api import ExternalPlayerEvent
from linux_voice_assistant.player_backend import ExternalPlayerBackend, LocalPlayerBackend


class TestLocalPlayerBackend:
    def test_set_volume_normalized_converts_to_mpv_percent(self):
        music = MagicMock()
        backend = LocalPlayerBackend(music, MagicMock())

        backend.set_volume_normalized(0.4)

        music.set_volume.assert_called_once_with(40)

    def test_transport_commands_delegate(self):
        music = MagicMock()
        backend = LocalPlayerBackend(music, MagicMock())

        backend.pause()
        backend.resume()
        backend.stop()

        music.pause.assert_called_once()
        music.resume.assert_called_once()
        music.stop.assert_called_once()

    def test_play_delegates_with_callback(self):
        music = MagicMock()
        backend = LocalPlayerBackend(music, MagicMock())

        def _done():
            pass

        backend.play("http://example.com/track.flac", announcement=False, done_callback=_done)

        music.play.assert_called_once_with("http://example.com/track.flac", done_callback=_done)

    def test_announcement_play_uses_announce_player(self):
        music = MagicMock()
        announce = MagicMock()
        backend = LocalPlayerBackend(music, announce)

        backend.play("http://example.com/chime.flac", announcement=True)

        announce.play.assert_called_once()
        music.play.assert_not_called()

    def test_is_playing_and_is_paused_delegates(self):
        music = MagicMock()
        music.is_playing = True
        music.is_paused = False
        backend = LocalPlayerBackend(music, MagicMock())

        assert backend.is_playing is True
        assert backend.is_paused is False


class TestExternalPlayerBackend:
    def test_play_forwards_instruction(self):
        api = MagicMock()
        backend = ExternalPlayerBackend(api)

        backend.play("http://example.com/track.flac", announcement=True)

        api.send_external_player_sync.assert_called_once_with(
            ExternalPlayerEvent.PLAY,
            {"media_url": "http://example.com/track.flac", "announcement": True},
        )

    def test_transport_commands_forward_instructions(self):
        api = MagicMock()
        backend = ExternalPlayerBackend(api)

        backend.pause()
        backend.resume()
        backend.stop()

        assert api.send_external_player_sync.call_args_list[0][0] == (ExternalPlayerEvent.PAUSE, None)
        assert api.send_external_player_sync.call_args_list[1][0] == (ExternalPlayerEvent.RESUME, None)
        assert api.send_external_player_sync.call_args_list[2][0] == (ExternalPlayerEvent.STOP, None)

    def test_set_volume_forwards_normalized(self):
        api = MagicMock()
        backend = ExternalPlayerBackend(api)

        backend.set_volume_normalized(0.5)

        api.send_external_player_sync.assert_called_once_with(ExternalPlayerEvent.SET_VOLUME, {"volume": 0.5})

    def test_noop_without_api(self):
        backend = ExternalPlayerBackend(None)

        backend.pause()
        backend.play("http://example.com/x")
        backend.set_volume_normalized(0.5)
