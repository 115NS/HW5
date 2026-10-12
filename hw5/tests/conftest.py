import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
HW5 = TESTS.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(HW5))
sys.path.insert(0, str(HW5 / "mcp_server"))

ORIGINAL_DB = HW5 / "data" / "campus_customs.db"
WORKING_DB = HW5 / "data" / "campus_customs_new.db"
ORIGINAL_SHA256 = "23686a90d698f7fa6f901a3f0a9774db9cbb31e13151c9e5717275f3321f360a"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# Tests never depend on the real working DB's current state (Problem 9 left real outcomes in it).
# Every test runs against a fresh temp copy of the ORIGINAL database, named by CAMPUS_CUSTOMS_DB,
# which the MCP server, the agents' stdio MCP subprocess, and the ledger all honour.
TEST_DB = Path(tempfile.mkdtemp(prefix="hw5-tests-")) / "campus_customs_test.db"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    shutil.copyfile(ORIGINAL_DB, TEST_DB)
    previous = os.environ.get("CAMPUS_CUSTOMS_DB")
    os.environ["CAMPUS_CUSTOMS_DB"] = str(TEST_DB)
    yield TEST_DB
    if previous is None:
        os.environ.pop("CAMPUS_CUSTOMS_DB", None)
    else:
        os.environ["CAMPUS_CUSTOMS_DB"] = previous


@pytest.fixture(autouse=True)
def fresh_test_database(test_database):
    """Each test starts from the original values."""
    shutil.copyfile(ORIGINAL_DB, test_database)


@pytest.fixture
def db():
    """Read-only connection to the test copy of the original DB, for checking tool output."""
    conn = sqlite3.connect(f"file:{TEST_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def databases_unchanged():
    """Every test must leave both database files byte-for-byte unchanged."""
    before = sha256(ORIGINAL_DB), sha256(WORKING_DB)
    yield
    assert sha256(ORIGINAL_DB) == ORIGINAL_SHA256, "original database changed"
    assert (sha256(ORIGINAL_DB), sha256(WORKING_DB)) == before, "a database file changed during the test"
