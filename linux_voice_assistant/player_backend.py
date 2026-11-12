"""Playback backends behind the HA media player facade.

``MediaPlayerEntity`` (entity.py) is the single point Home Assistant drives.
Two interchangeable backends sit behind it:

  LocalPlayerBackend     the local mpv stack (music_player + announce_player),
                         used when no peripheral registered as the player.
  ExternalPlayerBackend  fire-and-forget instruction events to the peripheral
                         that registered via register_media_player; the real
                         outcome comes back as media_player_state /
                         volume_changed reports, applied to the facade via
                         MediaPlayerEntity.apply_reported_state() and
                         apply_reported_volume().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Union

from .peripheral_api import ExternalPlayerEvent

if TYPE_CHECKING:
    from .peripheral_api import PeripheralAPIBridge


class LocalPlayerBackend:
    """Drives the local mpv stack directly."""

    def __init__(self, music_player, announce_player) -> None:
        self.music_player = music_player
        self.announce_player = announce_player

    @property
    def is_playing(self) -> bool:
        return bool(self.music_player.is_playing)

    @property
    def is_paused(self) -> bool:
        return bool(self.music_player.is_paused)

    def play(
        self,
        url: Union[str, List[str]],
        announcement: bool = False,
        done_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Simple playback. The local announce-over-music choreography lives
        in MediaPlayerEntity.play — it broadcasts HA state transitions."""
        if announcement:
            self.announce_player.play(url, done_callback=done_callback)
        else:
            self.music_player.play(url, done_callback=done_callback)

    def pause(self) -> None:
        self.music_player.pause()

    def resume(self) -> None:
        self.music_player.resume()

    def stop(self) -> None:
        self.music_player.stop()

    def set_volume_normalized(self, volume: float) -> None:
        """Apply volume; mpv wants 1–100 percent."""
        self.music_player.set_volume(int(round(volume * 100)))


class ExternalPlayerBackend:
    """Forwards playback instructions to the registered peripheral player."""

    def __init__(self, api: Optional["PeripheralAPIBridge"]) -> None:
        self._api = api

    def play(
        self,
        url: Union[str, List[str]],
        announcement: bool = False,
        done_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Forward the URL. ``done_callback`` is accepted but unused: the
        external player reports completion via media_player_state."""
        self._send(ExternalPlayerEvent.PLAY, {"media_url": url, "announcement": announcement})

    def pause(self) -> None:
        self._send(ExternalPlayerEvent.PAUSE)

    def resume(self) -> None:
        self._send(ExternalPlayerEvent.RESUME)

    def stop(self) -> None:
        self._send(ExternalPlayerEvent.STOP)

    def set_volume_normalized(self, volume: float) -> None:
        """Forward the normalized volume; the player applies it physically
        and reports the result back via volume_changed."""
        self._send(ExternalPlayerEvent.SET_VOLUME, {"volume": volume})

    def _send(self, event: ExternalPlayerEvent, data: Optional[dict] = None) -> None:
        if self._api is None:
            return
        self._api.send_external_player_sync(event, data)
