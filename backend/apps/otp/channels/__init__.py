from apps.otp.channels.base import NotificationChannel
from apps.otp.channels.email import SmtpEmailChannel
from apps.otp.channels.registry import ChannelRegistry, get_channel

ChannelRegistry.register(SmtpEmailChannel)

__all__ = [
    "ChannelRegistry",
    "NotificationChannel",
    "SmtpEmailChannel",
    "get_channel",
]
