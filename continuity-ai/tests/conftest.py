import pytest
from app.database.connection import connect, init_db
from scripts.seed import seed


@pytest.fixture
def db_and_case(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_db(conn)
    yield conn, seed(conn)
    conn.close()


@pytest.fixture
def db(db_and_case):
    return db_and_case[0]


@pytest.fixture
def case_id(db_and_case):
    return db_and_case[1]
