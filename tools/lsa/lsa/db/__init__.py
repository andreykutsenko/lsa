"""Database module for LSA."""

from .connection import (
    get_connection,
    init_db,
    insert_message_code,
    get_message_code,
    get_message_codes_batch,
    count_message_codes,
    insert_case_card,
    upsert_case_card,
    upsert_incident,
    get_incidents,
    get_incident_by_log_path,
    count_incidents,
    count_case_cards,
)
from .schema import SCHEMA

__all__ = [
    "get_connection",
    "init_db",
    "SCHEMA",
    "insert_message_code",
    "get_message_code",
    "get_message_codes_batch",
    "count_message_codes",
    "insert_case_card",
    "upsert_case_card",
    "upsert_incident",
    "get_incidents",
    "get_incident_by_log_path",
    "count_incidents",
    "count_case_cards",
]
