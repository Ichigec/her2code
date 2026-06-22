"""
Education graph initializer. Creates the `education` Neo4j database
and applies the schema from education_graph.cypher.

Usage:
  python -m graph_tool.python.graph.init_education
  python -m graph_tool.python.graph.init_education --drop-first
"""
from __future__ import annotations

import os
import pathlib
import sys

from neo4j import GraphDatabase, Driver


def get_driver() -> Driver:
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687"),
        auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "")),
    )


def load_schema() -> list[str]:
    schema_path = pathlib.Path(__file__).parent / "education_graph.cypher"
    raw = schema_path.read_text()
    statements = []
    for stmt in raw.split(";"):
        cleaned = "\n".join(
            line.split("//")[0] for line in stmt.split("\n")
        ).strip()
        if cleaned and not cleaned.startswith("//"):
            statements.append(cleaned)
    return statements


def init_education_db(drop_first: bool = False):
    driver = get_driver()
    database = os.getenv("EDUCATION_DATABASE", "education")

    if drop_first:
        with driver.session(database="system") as s:
            try:
                s.run(f"DROP DATABASE {database} IF EXISTS")
            except Exception as e:
                print(f"Warning: {e}")

        with driver.session(database="system") as s:
            s.run(f"CREATE DATABASE {database} IF NOT EXISTS")
            print(f"Created database '{database}'")
    else:
        with driver.session(database="system") as s:
            s.run(f"CREATE DATABASE {database} IF NOT EXISTS")

    # Wait for DB to be ready
    import time
    time.sleep(2)

    statements = load_schema()
    with driver.session(database=database) as session:
        for cypher in statements:
            try:
                session.run(cypher)
            except Exception as e:
                msg = str(e)
                if not any(kw in msg.lower() for kw in ("already exists", "equivalent")):
                    print(f"Warning: {msg}")

    print(f"Education graph schema applied to '{database}' ({len(statements)} constraints/indexes)")
    driver.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--drop-first", action="store_true")
    args = parser.parse_args()
    init_education_db(args.drop_first)
