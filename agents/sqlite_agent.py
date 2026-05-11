# Built-in Python library for reading/writing SQLite databases (no install needed)
import sqlite3

# Built-in Python library to convert Python dicts/lists → JSON string for the response
import json

# Anthropic SDK — used to call the Claude LLM
import anthropic

# BaseAgent is the abstract base class all agents must inherit from.
# It enforces that every agent has a run(question) method.
from .base_agent import BaseAgent

# SUBAGENT_MODEL — the Claude model used by sub-agents (claude-haiku, cheaper/faster)
# DB_PATH        — the file path to the SQLite database on disk
from config import SUBAGENT_MODEL, DB_PATH

# The instruction we give Claude when asking it to generate SQL.
# We tell it to return ONLY raw SQL so we can execute it directly
# without having to strip out markdown code blocks or explanations.
_SYSTEM_PROMPT = """You are a SQL expert. Given a SQLite schema and a user question, write a
single SELECT query that answers the question. Return ONLY the raw SQL — no markdown, no explanation."""


class SQLiteAgent(BaseAgent):
    """Translates natural-language questions into SQL, runs them, and returns results."""

    def __init__(self):
        # Create the Anthropic client. This is the object we use to call Claude.
        # It automatically reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic()

    def _get_schema(self) -> str:
        # Connect to the SQLite database file at DB_PATH.
        # `with` ensures the connection is closed automatically when done.
        with sqlite3.connect(DB_PATH) as conn:

            # Query SQLite's internal metadata table to get all table names.
            # sqlite_master is a special built-in table that stores the DB structure.
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")

            # fetchall() returns a list of tuples e.g. [("profile",), ("skills",), ...]
            # row[0] extracts just the table name from each tuple.
            tables = [row[0] for row in cursor.fetchall()]

            parts = []
            for table in tables:
                # PRAGMA table_info(table) is a SQLite command that returns
                # column metadata: id, name, type, notnull, default, primary key.
                cursor = conn.execute(f"PRAGMA table_info({table})")

                # row[1] is the column name. We collect all column names for this table.
                cols = [row[1] for row in cursor.fetchall()]

                # Build a compact schema string like: "skills(name, level, years)"
                parts.append(f"{table}({', '.join(cols)})")

            # Join all table schemas with newlines into one string, e.g.:
            # "profile(key, value)\nskills(name, level, years)\nexperience(company, role, ...)"
            return "\n".join(parts)

    def _to_sql(self, question: str, schema: str) -> str:
        # Call Claude (the sub-agent LLM) and ask it to write a SQL query.
        # We pass the schema so Claude knows what tables and columns exist.
        response = self.client.messages.create(
            model=SUBAGENT_MODEL,
            max_tokens=512,               # SQL queries are short, 512 tokens is plenty
            system=_SYSTEM_PROMPT,        # Tell Claude it's a SQL expert
            messages=[{"role": "user", "content": f"Schema:\n{schema}\n\nQuestion: {question}"}],
        )

        # Strip markdown code fences if the model wraps the SQL (e.g. ```sql ... ```)
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]  # drop opening fence line
            text = text.rsplit("```", 1)[0]  # drop closing fence
        return text.strip().rstrip(";")

    def run(self, question: str) -> str:
        # This is the main entry point called by the Orchestrator.
        # It orchestrates the full flow: schema → SQL → execute → return results.
        try:
            # Step 1: Read the database schema so Claude knows what to query
            schema = self._get_schema()
            print(f"\n + SQLITE SCHEMA {schema}")

            # Step 2: Ask Claude to convert the natural-language question into SQL
            sql = self._to_sql(question, schema)
            print(f"\n + SQLITE SQL {sql}")

            # Step 3: Execute the generated SQL against the real database
            with sqlite3.connect(DB_PATH) as conn:

                # Row factory makes each row behave like a dict instead of a plain tuple,
                # so we can access columns by name: row["name"] instead of row[0]
                conn.row_factory = sqlite3.Row

                # Execute the SQL and convert each row to a regular Python dict
                rows = [dict(r) for r in conn.execute(sql).fetchall()]

            print(f"\n + SQLITE ROWS {rows}")
            # If the query ran but found no matching data, return a friendly message
            if not rows:
                return "No matching records found in the personal database."

            # Convert the list of dicts to a formatted JSON string so the
            # Orchestrator LLM can easily read and summarise the results.
            # default=str handles any non-serialisable types (e.g. dates)
            return json.dumps(rows, indent=2, default=str)

        except Exception as e:
            # If anything goes wrong (bad SQL, DB error, API error),
            # return an error string instead of crashing the whole application.
            return f"[SQLiteAgent error] {e}"
