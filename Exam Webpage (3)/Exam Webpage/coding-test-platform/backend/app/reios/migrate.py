"""
Additive schema upgrades for databases created before a column existed.
create_all() makes new tables but never alters existing ones, so new columns are added here.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# table -> [(column, SQL type and default)]
NEW_COLUMNS = {
    "reios_exams": [
        ("exam_type", "VARCHAR(16) NOT NULL DEFAULT 'mixed'"),
        ("show_leaderboard", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("auto_assign_sets", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ],
    "reios_exam_items": [("set_id", "INTEGER")],
    "reios_attempts": [("set_id", "INTEGER")],
    "reios_users": [("firebase_uid", "VARCHAR(128)")],
    "reios_colleges": [("max_exams", "INTEGER"), ("access_until", "TIMESTAMP"),
                       ("org_type", "VARCHAR(16) NOT NULL DEFAULT 'college'"), ("features", "JSON"),
                       ("logo", "TEXT"), ("brand_color", "VARCHAR(16)")],
}


def upgrade(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in NEW_COLUMNS.items():
            if table not in tables:
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))
