import os
from pathlib import Path
from typing import Any

import yaml
from neo4j import GraphDatabase


def _load_root_config() -> dict[str, Any]:
    """
    Load root `config.yaml` if present.
    Priority for this module:
      explicit args > config.yaml > env vars > defaults
    """
    root_dir = Path(__file__).resolve().parents[1]
    config_path = root_dir / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        with config_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[WARN] Failed to load config.yaml: {e}")
        return {}

class Neo4jConnection:
    def __init__(self, uri=None, user=None, password=None):
        cfg = _load_root_config().get("neo4j", {}) if uri is None or user is None or password is None else {}

        self.uri = (
            uri
            or cfg.get("uri")
            or os.getenv("NEO4J_URI")
            or "bolt://localhost:7687"
        )
        self.user = (
            user
            or cfg.get("user")
            or os.getenv("NEO4J_USER")
            or "neo4j"
        )
        self.password = (
            password
            or cfg.get("password")
            or os.getenv("NEO4J_PASSWORD")
            or "password"
        )
        self.driver = None

    def connect(self):
        if not self.driver:
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                # Verify connection
                self.driver.verify_connectivity()
                print(f"Connected to Neo4j at {self.uri}")
            except Exception as e:
                print(f"Failed to connect to Neo4j: {e}")
                self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def query(self, query, parameters=None, db=None):
        self.connect()
        if not self.driver:
            return None
            
        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query failed: {e}")
            return None

    def execute_write(self, query, parameters=None, db=None):
        self.connect()
        if not self.driver:
            return None
            
        try:
            with self.driver.session(database=db) as session:
                result = session.run(query, parameters)
                return result.consume()
        except Exception as e:
            print(f"Write failed: {e}")
            return None

# Singleton instance for easy import
db = Neo4jConnection()
