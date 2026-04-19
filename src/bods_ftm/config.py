from __future__ import annotations

from dataclasses import dataclass, field

from bods_ftm.utils.dates import today_iso


@dataclass
class PublisherConfig:
    """Configuration for BODS publication metadata, used in FTM→BODS conversion."""

    publisher_name: str = "bods-ftm converter"
    publisher_uri: str | None = None
    license_url: str = "https://creativecommons.org/publicdomain/zero/1.0/"
    bods_version: str = "0.4"
    publication_date: str = field(default_factory=today_iso)
