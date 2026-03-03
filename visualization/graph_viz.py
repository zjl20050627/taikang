import networkx as nx
from pyvis.network import Network
import streamlit.components.v1 as components
import os
import random
import string

def visualize_graph(data, height="600px", width="100%"):
    """
    Visualize a graph using PyVis and Streamlit.
    """
    if not data or not data.get('nodes'):
        return None

    # Create networkx graph
    try:
        G = nx.DiGraph()
        
        # Add nodes
        for node in data['nodes']:
            # Determine label and title
            label = node.get('name', node.get('id', 'Unknown'))
            title = "<br>".join([f"{k}: {v}" for k, v in node.items() if k != 'id'])
            
            # Determine color/shape based on type if available
            # Note: We don't have explicit type in node dict unless we fetch labels separately.
            # But we can infer from properties or ID prefix.
            color = "#97C2FC" # Default blue
            if node.get('id', '').startswith('disease'):
                color = "#FB7E81" # Red
            elif node.get('id', '').startswith('drug'):
                color = "#7BE141" # Green
            elif node.get('id', '').startswith('category'):
                color = "#FFC0CB" # Pink
                
            G.add_node(node['id'], label=label, title=title, color=color)

        # Add edges
        for edge in data['edges']:
            G.add_edge(edge['source'], edge['target'], title=edge.get('type', ''), label=edge.get('type', ''))

        # Pyvis network
        net = Network(height=height, width=width, bgcolor="#222222", font_color="white", notebook=False)
        net.from_nx(G)
        
        # Physics options
        net.repulsion(node_distance=150, spring_length=200)
        
        # Save to temporary file
        # Use random suffix to avoid collisions in strict environments (though unnecessary for single user)
        # Using a fixed temp name is safer for cleanup
        path = "tmp_graph_viz.html"
        net.save_graph(path)
        
        # Read file content
        with open(path, 'r', encoding='utf-8') as f:
            source_code = f.read()
            
        # Clean up
        try:
            os.remove(path)
        except:
            pass
            
        return source_code
        
    except Exception as e:
        print(f"Error generating graph visualization: {e}")
        return None

def render_graph(source_code, height=600):
    if source_code:
        components.html(source_code, height=height)
