from __future__ import annotations

import logging
import sys

import click

from bods_ftm.bods_to_ftm.converter import BODSToFTMConverter
from bods_ftm.config import PublisherConfig
from bods_ftm.ftm_to_bods.converter import FTMToBODSConverter


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors.")
def main(verbose: bool, quiet: bool) -> None:
    """Bidirectional converter between BODS v0.4 and FollowTheMoney."""
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(stream=sys.stderr, level=level, format="%(levelname)s: %(message)s")


@main.command("bods-to-ftm")
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    default="output.ftm.jsonl",
    show_default=True,
    help="Output file path (FTM JSONL).",
)
def bods_to_ftm(input_file: str, output: str) -> None:
    """Convert a BODS v0.4 JSON file to FollowTheMoney JSONL.

    INPUT_FILE should be a BODS v0.4 JSON array of statements.
    """
    converter = BODSToFTMConverter()
    count = converter.convert_file(input_file, output)
    logging.info("Wrote %d FTM entities to %s", count, output)


@main.command("ftm-to-bods")
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    default="output.bods.json",
    show_default=True,
    help="Output file path (BODS JSON array).",
)
@click.option("--publisher-name", default="bods-ftm converter", show_default=True)
@click.option("--publisher-uri", default=None)
@click.option(
    "--license-url",
    default="https://creativecommons.org/publicdomain/zero/1.0/",
    show_default=True,
)
def ftm_to_bods(
    input_file: str,
    output: str,
    publisher_name: str,
    publisher_uri: str | None,
    license_url: str,
) -> None:
    """Convert a FollowTheMoney JSONL file to BODS v0.4 JSON.

    INPUT_FILE should be a newline-delimited JSON file of FTM entities.
    """
    config = PublisherConfig(
        publisher_name=publisher_name,
        publisher_uri=publisher_uri,
        license_url=license_url,
    )
    converter = FTMToBODSConverter(config)
    count = converter.convert_file(input_file, output)
    logging.info("Wrote %d BODS statements to %s", count, output)


if __name__ == "__main__":
    main()
