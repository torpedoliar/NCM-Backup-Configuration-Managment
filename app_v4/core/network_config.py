from __future__ import annotations

from dataclasses import dataclass, field

from app_v4.core.config import Settings


@dataclass(frozen=True)
class NetworkConfig:
    max_retries: int
    retry_delay: int
    backoff_multiplier: int
    connect_timeout: int
    command_timeout: int
    read_timeout: int
    prompts: list[str] = field(default_factory=lambda: ["#", ">"])
    paging_disable_commands: list[str] = field(
        default_factory=lambda: ["terminal length 0", "terminal pager 0", "no page"]
    )
    paging_indicators: list[str] = field(default_factory=lambda: ["--More--", "More:", "Press any key"])


def load_network_config(settings: Settings) -> NetworkConfig:
    return NetworkConfig(
        max_retries=settings.network_max_retries,
        retry_delay=settings.network_retry_delay,
        backoff_multiplier=settings.network_backoff_multiplier,
        connect_timeout=settings.network_connect_timeout,
        command_timeout=settings.network_command_timeout,
        read_timeout=settings.network_read_timeout,
    )
