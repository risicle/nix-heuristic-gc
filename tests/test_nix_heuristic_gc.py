import logging
import os

import pytest

from nix_heuristic_gc import nix_heuristic_gc
from nix_heuristic_gc.quantity import Quantity, QuantityUnit


@pytest.mark.parametrize("dry_run", (False, True))
@pytest.mark.parametrize("unit", (QuantityUnit.BYTES, QuantityUnit.INODES))
def test_empty_local_store(caplog, dry_run, unit):
    caplog.set_level(logging.DEBUG)

    nix_heuristic_gc(
        Quantity(1e6, unit),
        penalize_substitutable=None,  # avoid network requests
        dry_run=dry_run,
        threads=0,
    )

    assert "requesting deletion of 0 store paths, total nar_size 0 bytes, 0 inodes" in caplog.text
    assert ("(not) requesting deletion" in caplog.text) is dry_run
    assert "ran out of zero-reference paths to remove" in caplog.text
