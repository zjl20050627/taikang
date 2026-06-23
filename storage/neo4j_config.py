import os
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from storage.neo4j_settings import get_neo4j_settings


class Neo4jConnection:
    def __init__(self, uri=None, user=None, password=None, database=None):
        settings = get_neo4j_settings()

        self.uri = uri or settings["uri"]
        self.user = user or settings["user"]
        self.password = password or settings["password"]
        self.database = database or settings["database"]
        self.driver = None

    def connect(self):
        if not self.driver:
            try:
                self.driver = GraphDatabase.driver(
                    self.uri, auth=(self.user, self.password)
                )
                self.driver.verify_connectivity()
                with self.driver.session(database=self.database) as session:
                    session.run("RETURN 1")
                print(f"Connected to Neo4j at {self.uri} (db={self.database})")
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

        database = db or self.database
        try:
            with self.driver.session(database=database) as session:
                result = session.run(query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query failed: {e}")
            return None

    def execute_write(self, query, parameters=None, db=None):
        self.connect()
        if not self.driver:
            return None

        database = db or self.database
        try:
            with self.driver.session(database=database) as session:
                result = session.run(query, parameters)
                return result.consume()
        except Exception as e:
            print(f"Write failed: {e}")
            return None


# Singleton instance for easy import
db = Neo4jConnection()
