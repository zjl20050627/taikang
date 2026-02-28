import os
from neo4j import GraphDatabase

class Neo4jConnection:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password")
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
