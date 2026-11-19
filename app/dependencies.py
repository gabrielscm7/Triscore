from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from app.database import connect


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    connection = connect(request.app.state.db_path)
    try:
        yield connection
    finally:
        connection.close()
