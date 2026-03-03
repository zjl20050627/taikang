## GraphRAG Question Answering System

This repository implements a **GraphRAG** (knowledge-graph-based Retrieval-Augmented Generation) pipeline for the ��insurance + medical + elderly care�� domain.

### Directory overview
- `question_understanding/`: rule-based question parsing (entities, intent, age, constraints).
- `graph_retrieval/`: Neo4j-based subgraph retrieval (Cypher queries, entity alignment, fallbacks).
- `answer_generation/`: context building from triples, prompt templates, answer formatting.
- `llm_integration/`: LLM abstraction and factory (Mock LLM / ZhipuAI).
- `storage/`: knowledge graph storage utilities (Neo4j config, import scripts, query helpers).
- `extraction/` (from `kg` branch): raw data extraction and triple generation.
- `ontology/`: ontology and entity�Crelationship design docs.
- `visualization/`: Streamlit + PyVis graph explorer.

### End-to-end QA flow
1. **Question understanding**  
   `QuestionUnderstanding.parse()` extracts:
   - entities (Disease, Drug, InsuranceProduct, Institution, etc.)
   - intent (insurability, treatment, cost, coverage, eligibility, general)
   - age and simple constraints (gender, city).

2. **Graph retrieval (Neo4j)**  
   `Neo4jGraphRetrieval.retrieve()`:
   - builds an intent-aware Cypher query from the parsed question
   - executes it against Neo4j
   - parses records into `Triple` objects
   - if no result for insurance / institution labels, falls back to disease-centered subgraphs.

3. **Context construction**  
   `ContextBuilder.build_context()` groups triples by head entity and converts them into readable Chinese sentences, used as knowledge context.

4. **Prompt building & LLM call**  
   `PromptTemplateManager.build_prompt()` chooses a template by intent and builds `messages` for the LLM.  
   `create_llm()` returns either:
   - a Mock LLM (no API needed), or  
   - a real ZhipuAI client (when configured).

5. **Answer formatting & traceability**  
   The final answer includes:
   - natural-language response
   - referenced triples for traceability
   - a simple confidence score.

### How to run locally

1. **Install dependencies**

```bash
pip install -r requirements.txt
```

2. **Configure Neo4j**

Edit `config.yaml` at the repo root:

```yaml
neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "your_password"

system:
  max_hops: 2
  max_triples: 50
  enable_source: true
```

Start a local Neo4j DBMS in Neo4j Desktop with the same URI/user/password.

3. **Build and import the medical KG (from `kg` branch code)**

From the project root:

```bash
python extraction/extract_icd11.py
python extraction/extract_pdf.py
python extraction/generate_triples.py
python storage/import_data.py
```

This will create and import:
- `data/processed/medical/aligned_entities.json`
- `data/processed/medical/triples.json`
into your Neo4j instance.

4. **Run the GraphRAG QA pipeline**

```bash
python pipeline.py
```

`pipeline.py` runs several test questions end-to-end and prints:
- intermediate steps (parsing, retrieval, context, prompt, LLM call)
- final answer
- number of referenced triples.

5. **(Optional) Graph visualization**

```bash
python -m streamlit run visualization/app.py
```

Then open the local URL printed in the terminal to:
- search entities by name
- explore their 1-hop neighborhood
- inspect node properties and relationships.

### LLM configuration (ZhipuAI)

By default, the system uses a Mock LLM so that it works without any API keys.

To enable ZhipuAI:

1. Create `.env` in the repo root with:

```env
ZHIPUAI_API_KEY=your_zhipuai_api_key_here
```

2. In `config.yaml`, set:

```yaml
llm:
  provider: "zhipuai"
```

On the next run, `create_llm()` will attempt to use ZhipuAI; if the SDK or key is missing, it gracefully falls back to the Mock LLM.
