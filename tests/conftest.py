"""pytest setup for DSiRPC's tests (see tests/README.md)."""

import os
import sys

import pytest

# The repo root, for core/ and tools/ (tests/ itself is on the path already,
# for helpers/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from helpers import cbuild  # noqa: E402

# CI sets this, so a missing compiler or rcheevos library fails the run
# instead of quietly skipping the tests that need it
REQUIRE_ALL = os.environ.get("DSIRPC_TESTS_REQUIRE_ALL") == "1"


def need(ok, why):
    """Skips the test (fails it in CI) when `ok` is false."""
    if not ok:
        if REQUIRE_ALL:
            pytest.fail(why, pytrace=False)
        pytest.skip(why)


@pytest.fixture(scope="session")
def cc():
    """gcc, for the C harnesses (Linux only: they map memory at the DS's addresses)."""
    need(cbuild.gcc() and sys.platform.startswith("linux"), "the C harnesses need gcc on Linux")
    return cbuild.gcc()


@pytest.fixture(scope="session")
def rcheevos():
    """core.rcheevos, with the library and DSiRPC's offline addition loaded
    (third_party/rcheevos/README.md says how to build it)."""
    from core import rcheevos as rc
    try:
        lib = rc.library()
    except rc.RcheevosMissing as e:
        need(False, str(e))
    need(hasattr(lib, "dsirpc_offline_compile"), "the rcheevos library was built without dsirpc_offline.c")
    return rc
