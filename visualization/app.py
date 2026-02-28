import streamlit as st
import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.query import search_nodes, get_subgraph_viz_format
from visualization.graph_viz import visualize_graph, render_graph

st.set_page_config(layout="wide", page_title="Medical KG Visualization")

st.title("Medical Knowledge Graph Explorer")

# Sidebar for search
st.sidebar.header("Search")
search_term = st.sidebar.text_input("Enter entity name (e.g., 霍乱, 阿司匹林)")

selected_node_id = None
selected_node_name = None

if search_term:
    results = search_nodes(search_term, limit=20)
    if results:
        # Create mapping from display text to node ID
        options_map = {}
        display_options = []
        
        for r in results:
            # Safely access node properties
            node = r.get('n', {})
            labels = r.get('labels', [])
            
            # Determine primary label
            priority_label = "Entity"
            for label in labels:
                if label in ['Disease', 'Drug', 'Category']:
                    priority_label = label
                    break
            
            name = node.get('name', node.get('id', 'Unknown'))
            entity_id = node.get('id')
            
            if entity_id:
                display_text = f"{name} ({priority_label})"
                options_map[display_text] = {'id': entity_id, 'name': name}
                display_options.append(display_text)
                
        if display_options:
            selected_label = st.sidebar.selectbox("Select Entity", display_options)
            selected_node = options_map[selected_label]
            selected_node_id = selected_node['id']
            selected_node_name = selected_node['name']
        else:
            st.sidebar.warning("No valid entities found.")
    else:
        st.sidebar.warning("No results found.")

if selected_node_id:
    st.header(f"Exploring: {selected_node_name or selected_node_id}")
    
    # Create layout
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.info("Graph Information")
        st.markdown(f"**Selected Entity ID:** `{selected_node_id}`")
        if selected_node_name:
            st.markdown(f"**Name:** {selected_node_name}")
            
    # Fetch data
    with st.spinner("Loading graph..."):
        graph_data = get_subgraph_viz_format(selected_node_id, limit=50)
        
        if not graph_data or not graph_data.get('nodes'):
            st.warning("No data found for this entity.")
        else:
            with col1:
                st.metric("Nodes", len(graph_data['nodes']))
                st.metric("Edges", len(graph_data['edges']))
            
            # Visualize Graph
            source_code = visualize_graph(graph_data, height="600px", width="100%")
            if source_code:
                st.components.v1.html(source_code, height=600, scrolling=True)
            else:
                st.error("Failed to generate graph visualization.")
                
            # Node Details Table
            st.subheader("Selected Entity Details")
            center_node = next((n for n in graph_data['nodes'] if n.get('id') == selected_node_id), None)
            
            if center_node:
                # remove internal id if present? No, keep everything
                data_items = [{"Property": k, "Value": str(v)} for k, v in center_node.items()]
                df = pd.DataFrame(data_items)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
else:
    st.info("Please search for an entity in the sidebar to explore the Knowledge Graph.")
    
    st.markdown("""
    ### How to use
    1. Enter a search term in the sidebar (e.g., "霍乱").
    2. Select an entity from the results.
    3. Explore the graph visualization and entity details.
    
    ### Requirements
    - Ensure Neo4j is running and configured correctly in `storage/neo4j_config.py`.
    - Run this app using `streamlit run visualization/app.py`.
    """)
