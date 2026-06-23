import json
import os
import sys
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.neo4j_config import db


def load_json(filepath):
    """Load JSON data from a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
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
    db.execute_write("MATCH (n) DETACH DELETE n")
    print("Database cleared.")


def create_indexes():
    """Create indexes for faster lookup."""
    print("Creating indexes...")
    queries = [
        "CREATE INDEX entity_id IF NOT EXISTS FOR (n:Entity) ON (n.id)",
        "CREATE INDEX disease_name IF NOT EXISTS FOR (d:Disease) ON (d.name)",
        "CREATE INDEX disease_aligned IF NOT EXISTS FOR (d:Disease) ON (d.aligned_name)",
        "CREATE INDEX drug_name IF NOT EXISTS FOR (d:Drug) ON (d.name)",
        "CREATE INDEX insurance_name IF NOT EXISTS FOR (p:InsuranceProduct) ON (p.name)",
        "CREATE INDEX insurance_short IF NOT EXISTS FOR (p:InsuranceProduct) ON (p.short_name)",
        "CREATE INDEX institution_name IF NOT EXISTS FOR (i:Institution) ON (i.name)",
    ]
    for q in queries:
        print(f"  Executing: {q}")
        db.execute_write(q)
    print("Indexes created.")


def _batch_import(query: str, rows: list, label: str, batch_size: int = 1000):
    """Generic batch import helper."""
    if not rows:
        return
    total = len(rows)
    print(f"Importing {total} {label}...")
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        db.execute_write(query, {"batch": batch})
        print(f"  Processed {min(i + batch_size, total)}/{total} {label}")


def import_nodes(data):
    """Import all entity types as Neo4j nodes."""
    print("Importing nodes...")

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (d:Disease:Entity {id: row.id})
        SET d.code = row.code,
            d.name = row.name,
            d.normalized_name = row.normalized_name,
            d.aligned_name = row.aligned_name,
            d.category_code = row.category,
            d.chapter = row.chapter
        """,
        data.get("diseases", []),
        "diseases",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (d:Drug:Entity {id: row.id})
        SET d.code = row.code,
            d.name = row.name,
            d.normalized_name = row.normalized_name,
            d.brand_name = row.brand_name,
            d.indication = row.indication,
            d.manufacturer = row.manufacturer
        """,
        data.get("drugs", []),
        "drugs",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (c:Category:Entity {id: row.id})
        SET c.code = row.code,
            c.name = row.name,
            c.level = row.level,
            c.chapter = row.chapter
        """,
        data.get("categories", []),
        "categories",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (p:InsuranceProduct:Entity {id: row.id})
        SET p.code = row.code,
            p.name = row.name,
            p.short_name = row.short_name,
            p.type = row.type,
            p.company = row.company,
            p.description = row.description,
            p.source = row.source,
            p.annual_premium = row.annual_premium,
            p.coverage_amount = row.coverage_amount,
            p.waiting_period = row.waiting_period
        """,
        data.get("insurance_products", []),
        "insurance products",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (i:Institution:Entity {id: row.id})
        SET i.name = row.name,
            i.type = row.type,
            i.city = row.city,
            i.district = row.district,
            i.address = row.address,
            i.phone = row.phone,
            i.monthly_fee = row.monthly_fee,
            i.admission_requirements = row.admission_requirements,
            i.bed_count = row.bed_count,
            i.rating = row.rating,
            i.source = row.source
        """,
        data.get("institutions", []),
        "institutions",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (a:AgeLimit:Entity {id: row.id})
        SET a.min_age = row.min_age,
            a.max_age = row.max_age,
            a.label = row.label
        """,
        data.get("age_limits", []),
        "age limits",
    )

    _batch_import(
        """
        UNWIND $batch as row
        MERGE (m:MedicalService:Entity {id: row.id})
        SET m.name = row.name,
            m.description = row.description
        """,
        data.get("medical_services", []),
        "medical services",
    )

    # Value nodes: Price, Coverage, AdmissionRequirement
    value_nodes = data.get("value_nodes", [])
    if value_nodes:
        by_type = defaultdict(list)
        for node in value_nodes:
            by_type[node.get("type", "Value")].append(node)

        label_map = {
            "Price": "Price",
            "Coverage": "Coverage",
            "AdmissionRequirement": "AdmissionRequirement",
        }
        for vtype, nodes in by_type.items():
            neo4j_label = label_map.get(vtype, "Value")
            _batch_import(
                f"""
                UNWIND $batch as row
                MERGE (v:{neo4j_label}:Entity {{id: row.id}})
                SET v.value = row.value,
                    v.label = row.label,
                    v.node_type = row.type
                """,
                nodes,
                f"{neo4j_label} nodes",
            )

    print("Nodes imported.")


def import_relationships(triples):
    """Import relationships from triples."""
    if not triples:
        print("No triples to import.")
        return

    print(f"Importing {len(triples)} relationships...")
    triples_by_pred = defaultdict(list)

    for t in triples:
        if "predicate" in t and "subject" in t and "object" in t:
            triples_by_pred[t["predicate"]].append(t)

    for pred, batch in triples_by_pred.items():
        print(f"Importing {len(batch)} relationships of type {pred}...")
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
            sub_batch = batch[i : i + batch_size]
            db.execute_write(query, {"batch": sub_batch})
            print(f"  Processed {min(i + batch_size, total)}/{total} ({pred})")

    print("Relationships imported.")


def main():
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_path, "data", "processed", "medical")

    entities_file = os.path.join(data_path, "aligned_entities.json")
    triples_file = os.path.join(data_path, "triples.json")

    print(f"Loading entities from {entities_file}...")
    entities = load_json(entities_file)

    print(f"Loading triples from {triples_file}...")
    triples = load_json(triples_file)

    if entities or triples:
        try:
            db.connect()
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
