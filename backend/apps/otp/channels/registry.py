from __future__ import annotations

from typing import ClassVar

from apps.otp.channels.base import NotificationChannel
from apps.otp.exceptions import OtpChannelUnsupportedError


class ChannelRegistry:
    _channels: ClassVar[dict[str, type]] = {}

    @classmethod
    def register(cls, channel_cls: type) -> type:
        name = getattr(channel_cls, "name", None)
        if not name:
            raise ValueError("El canal debe definir `name`.")
        cls._channels[name] = channel_cls
        return channel_cls

    @classmethod
    def get(cls, name: str) -> NotificationChannel:
        channel_cls = cls._channels.get(name)
        if channel_cls is None:
            raise OtpChannelUnsupportedError(
                "Canal de mensajería no disponible.",
                field="channel",
            )
        return channel_cls()


def get_channel(name: str) -> NotificationChannel:
    return ChannelRegistry.get(name)
