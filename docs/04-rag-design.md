# RAG Context Service Design

The knowledge corpus has four required classes: schema, certified metrics, business terms, and verified NL–SQL examples. Each document carries an ID, type, title, text, tags, and optional SQL. Retrieval normalizes Chinese/English terms, calculates token overlap, calculates cosine similarity over deterministic hashed character features, then merges scores. The API returns the top documents and both component scores as retrieval evidence.

Day 1 persists the corpus as JSON for transparent inspection. The next step stores chunks and production embeddings in pgvector, adds metadata filters and reranking, and evaluates recall@k/MRR by knowledge type. Retrieval trace must remain stable across implementations.

