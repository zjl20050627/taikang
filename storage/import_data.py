import json
import os
import sys
import time

# Add parent directory to path to import neo4j_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.neo4j_config import db

def load_json(filepath):
    """Load JSON data from a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found at {filepath}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {filepath}")
        return None

def clear_database():
    """Clear all data from Neo4j database."""
    print("Clearing database...")
    query = "MATCH (n) DETACH DELETE n"
    db.execute_write(query)
    print("Database cleared.")

def create_indexes():
    """Create indexes for faster lookup."""
    print("Creating indexes...")
    # Use explicit queries for each index
    queries = [
        "CREATE INDEX entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id)",
        "CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name)",
        "CREATE INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON (d.name)"
    ]
    
    for q in queries:
        print(f"Executing: {q}")
        db.execute_write(q)
    print("Indexes created.")

def import_nodes(data):
    """Import entities as nodes."""
    print("Importing nodes...")
    
    # Import Diseases
    if 'diseases' in data and data['diseases']:
        print(f"Importing {len(data['diseases'])} diseases...")
        query = """
        UNWIND $batch as row
        MERGE (d:Disease:Entity {id: row.id})
        SET d.code = row.code,
            d.name = row.name,
            d.normalized_name = row.normalized_name,
            d.aligned_name = row.aligned_name,
            d.category_code = row.category,
            d.chapter = row.chapter
        """
        batch_size = 1000
        total = len(data['diseases'])
        for i in range(0, total, batch_size):
            batch = data['diseases'][i:i+batch_size]
            db.execute_write(query, {'batch': batch})
            print(f"  Processed {min(i + batch_size, total)}/{total} diseases")
            
    # Import Drugs
    if 'drugs' in data and data['drugs']:
        print(f"Importing {len(data['drugs'])} drugs...")
        query = """
        UNWIND $batch as row
        MERGE (d:Drug:Entity {id: row.id})
        SET d.code = row.code,
            d.name = row.name,
            d.normalized_name = row.normalized_name,
            d.brand_name = row.brand_name,
            d.indication = row.indication,
            d.manufacturer = row.manufacturer
        """
        batch_size = 1000
        total = len(data['drugs'])
        for i in range(0, total, batch_size):
            batch = data['drugs'][i:i+batch_size]
            db.execute_write(query, {'batch': batch})
            print(f"  Processed {min(i + batch_size, total)}/{total} drugs")

    # Import Categories
    if 'categories' in data and data['categories']:
        print(f"Importing {len(data['categories'])} categories...")
        query = """
        UNWIND $batch as row
        MERGE (c:Category:Entity {id: row.id})
        SET c.code = row.code,
            c.name = row.name,
            c.level = row.level,
            c.chapter = row.chapter
        """
        batch_size = 1000
        total = len(data['categories'])
        for i in range(0, total, batch_size):
            batch = data['categories'][i:i+batch_size]
            db.execute_write(query, {'batch': batch})
            print(f"  Processed {min(i + batch_size, total)}/{total} categories")

    print("Nodes imported.")

def import_relationships(triples):
    """Import relationships from triples."""
    if not triples:
        print("No triples to import.")
        return

    print(f"Importing {len(triples)} relationships...")
    
    from collections import defaultdict
    triples_by_pred = defaultdict(list)
    
    for t in triples:
        if 'predicate' in t and 'subject' in t and 'object' in t:
            triples_by_pred[t['predicate']].append(t)
        
    for pred, batch in triples_by_pred.items():
        print(f"Importing {len(batch)} relationships of type {pred}...")
        
        # Use simple string formatting since pred is trusted (from our own generation script)
        # Using Entity label for optimized lookup via index
        query = f"""
        UNWIND $batch as row
        MATCH (s:Entity {{id: row.subject}})
        MATCH (o:Entity {{id: row.object}})
        MERGE (s)-[r:{pred}]->(o)
        SET r += row.properties
        """
        
        batch_size = 1000
        total = len(batch)
        for i in range(0, total, batch_size):
            sub_batch = batch[i:i+batch_size]
            db.execute_write(query, {'batch': sub_batch})
            print(f"  Processed {min(i + batch_size, total)}/{total} relationships ({pred})")
            
    print("Relationships imported.")

def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_path, 'data', 'processed', 'medical')
    
    entities_file = os.path.join(data_path, 'aligned_entities.json')
    triples_file = os.path.join(data_path, 'triples.json')
    
    print(f"Loading entities from {entities_file}...")
    entities = load_json(entities_file)
    
    print(f"Loading triples from {triples_file}...")
    triples = load_json(triples_file)
    
    if entities or triples:
        try:
            db.connect()
            # clear_database() 
            create_indexes()
            
            if entities:
                import_nodes(entities)
            
            if triples:
                import_relationships(triples)
                
            print("Import completed successfully!")
        except Exception as e:
            print(f"An error occurred during import: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()
    else:
        print("Failed to load data files.")

if __name__ == "__main__":
    main()
