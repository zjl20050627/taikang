import os
import sys

# Add parent directory to path to import neo4j_config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.neo4j_config import db

def get_node_by_id(node_id):
    """
    Get a node by its ID.
    """
    query = """
    MATCH (n:Entity {id: $id})
    RETURN n
    LIMIT 1
    """
    results = db.query(query, {'id': node_id})
    return results[0]['n'] if results else None

def search_nodes(search_term, limit=10):
    """
    Search for nodes by name (case-insensitive).
    """
    query = """
    MATCH (n:Entity)
    WHERE toLower(n.name) CONTAINS toLower($term)
    RETURN n, labels(n) as labels
    LIMIT $limit
    """
    results = db.query(query, {'term': search_term, 'limit': limit})
    return results

def get_subgraph(node_id, limit=50):
    """
    Get the subgraph centered around a node (direct neighbors).
    """
    query = """
    MATCH (n:Entity {id: $id})-[r]-(m:Entity)
    RETURN n, r, m
    LIMIT $limit
    """
    results = db.query(query, {'id': node_id, 'limit': limit})
    
    nodes = []
    edges = []
    
    if not results:
        # Return just the center node if no relationships
        center = get_node_by_id(node_id)
        if center:
            nodes.append(center)
        return {'nodes': nodes, 'edges': edges}
        
    seen_nodes = set()
    
    for row in results:
        # Process source node
        n = row['n']
        if n['id'] not in seen_nodes:
            nodes.append(n)
            seen_nodes.add(n['id'])
            
        # Process target node
        m = row['m']
        if m['id'] not in seen_nodes:
            nodes.append(m)
            seen_nodes.add(m['id'])
            
        # Process relationship
        r = row['r']
        # Neo4j driver returns relationship objects with start/end node ids usually, 
        # but here we get raw properties + type. We need to reconstruct.
        # However, the python driver's `data()` method returns a dict structure.
        # But `row['r']` in `record.data()` might be just properties + id + type.
        # Wait, `db.query` calls `record.data()`.
        # `record.data()` returns a dictionary where keys are return variables.
        # For a relationship `r`, it returns properties. It DOES NOT return start/end/type easily in the dict unless explicitly returned.
        
        edges.append({
            'source': n['id'],
            'target': m['id'],
            'type': r[1], # Wait, record.data() for relationship is tricky.
            'properties': dict(r)
        })
        
    return {'nodes': nodes, 'edges': edges}

def get_subgraph_viz_format(node_id, limit=50):
    """
    Get subgraph in a format suitable for visualization (explicit logic for relationships).
    """
    query = """
    MATCH (n:Entity {id: $id})-[r]-(m:Entity)
    RETURN n, type(r) as rel_type, properties(r) as rel_props, startNode(r) as start, endNode(r) as end, m
    LIMIT $limit
    """
    results = db.query(query, {'id': node_id, 'limit': limit})

    nodes = {}
    edges = []
    
    if not results:
        center = get_node_by_id(node_id)
        if center:
             nodes[center['id']] = center
        return {'nodes': list(nodes.values()), 'edges': edges}

    for row in results:
        n = row['n']
        m = row['m']
        
        nodes[n['id']] = n
        nodes[m['id']] = m
        
        # Determine direction
        start_id = row['start']['id']
        end_id = row['end']['id']
        
        edges.append({
            'source': start_id,
            'target': end_id,
            'type': row['rel_type'],
            'properties': row['rel_props']
        })
        
    return {'nodes': list(nodes.values()), 'edges': edges}

if __name__ == "__main__":
    # Test
    print("Searching for '霍乱'...")
    res = search_nodes("霍乱")
    print(res)
