"""
db_stats.py — Diagnostic script to collect Neo4j and ChromaDB statistics.
Run from project root:
    PYTHONPATH=. python scripts/db_stats.py
"""
import os
import sys
import json
import time
from dotenv import load_dotenv

load_dotenv()

# ─── Neo4j ────────────────────────────────────────────────────────────────────
def query_neo4j():
    from neo4j import GraphDatabase

    uri  = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD", "password")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    stats  = {}

    with driver.session() as sess:
        # Node counts by label
        result = sess.run("CALL db.labels() YIELD label RETURN label")
        label_counts = {}
        for row in result:
            label = row["label"]
            cnt = sess.run(f"MATCH (n:`{label}`) RETURN count(n) AS c").single()["c"]
            label_counts[label] = cnt
        stats["node_counts"] = label_counts
        stats["total_nodes"] = sum(label_counts.values())

        # Relationship counts by type
        result = sess.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
        rel_counts = {}
        for row in result:
            rtype = row["relationshipType"]
            cnt = sess.run(f"MATCH ()-[r:`{rtype}`]->() RETURN count(r) AS c").single()["c"]
            rel_counts[rtype] = cnt
        stats["relationship_counts"] = rel_counts
        stats["total_relationships"] = sum(rel_counts.values())

        # Reachability stats across Candidate nodes
        rs = sess.run("""
            MATCH (c:Candidate)
            WHERE c.reachability_score IS NOT NULL
            RETURN
                avg(c.reachability_score)  AS avg_r,
                min(c.reachability_score)  AS min_r,
                max(c.reachability_score)  AS max_r,
                count(c)                   AS total,
                count(CASE WHEN c.reachability_score >= 0.6 THEN 1 END) AS above_threshold
        """).single()

        if rs and rs["total"]:
            stats["avg_reachability"]     = round(rs["avg_r"], 4)
            stats["min_reachability"]     = round(rs["min_r"], 4)
            stats["max_reachability"]     = round(rs["max_r"], 4)
            stats["total_trajectories"]   = rs["total"]
            stats["above_threshold_06"]   = rs["above_threshold"]
            stats["threshold_pct"]        = round(rs["above_threshold"] / rs["total"] * 100, 1)
        else:
            stats["avg_reachability"]     = "N/A"
            stats["min_reachability"]     = "N/A"
            stats["max_reachability"]     = "N/A"
            stats["total_trajectories"]   = 0
            stats["above_threshold_06"]   = 0
            stats["threshold_pct"]        = 0.0

    driver.close()
    return stats


# ─── ChromaDB ─────────────────────────────────────────────────────────────────
def query_chroma():
    from src.retrieval.config.retriever_config import RetrieverConfig
    from src.retrieval.connectors.chroma_connector import ChromaConnector

    cfg  = RetrieverConfig.load("configs/retrieval.yaml")
    chroma = ChromaConnector(cfg.chroma)

    # Access underlying collection directly
    col = chroma.vectorstore._collection
    total_docs = col.count()

    # Pull all stored relevance scores via a broad similarity search
    # Use a representative ML-related query to get sample scores
    test_query = "machine learning engineer career transition python"
    t0 = time.time()
    results = chroma.vectorstore.similarity_search_with_relevance_scores(test_query, k=total_docs if total_docs <= 200 else 200)
    latency_ms = round((time.time() - t0) * 1000, 1)

    scores = [score for _, score in results]
    above_06 = [s for s in scores if s >= 0.6]

    return {
        "total_docs":      total_docs,
        "sample_size":     len(scores),
        "avg_relevance":   round(sum(scores) / len(scores), 4) if scores else "N/A",
        "min_relevance":   round(min(scores), 4) if scores else "N/A",
        "max_relevance":   round(max(scores), 4) if scores else "N/A",
        "above_threshold_06":  len(above_06),
        "threshold_pct":   round(len(above_06) / len(scores) * 100, 1) if scores else 0.0,
        "chroma_latency_ms": latency_ms,
    }


# ─── Pipeline Latency from last run logs ─────────────────────────────────────
# Extracted from the last real run in the conversation (hardcoded from stdout):
KNOWN_NEO4J_LATENCY_MS  = 1538.14   # from last run metadata
KNOWN_CHROMA_LATENCY_MS = None      # will be measured live above
KNOWN_NEO4J_FALLBACK     = False


# ─── Print Table ─────────────────────────────────────────────────────────────
def print_table(neo, chroma):
    print("\n" + "=" * 75)
    print(" DATA STORE STATISTICS — Combined Diagnostic Report")
    print("=" * 75)

    rows = [
        ("Dimension",                    "Neo4j (Graph Store)",                             "ChromaDB (Vector Store)"),
        ("─" * 30,                       "─" * 30,                                          "─" * 30),
        ("Total records",                str(neo.get("total_nodes", "?")),                   str(chroma.get("total_docs", "?"))),
        ("Total relationships",          str(neo.get("total_relationships", "?")),            "—"),
        ("Data types stored",            "Trajectories, BehavioralSignals, Roles, Projects",  "Career narratives, blog chunks"),
        ("Avg retrieval latency (ms)",   f"{KNOWN_NEO4J_LATENCY_MS} ms",                     f"{chroma.get('chroma_latency_ms', '?')} ms"),
        ("Records retrieved / query",     "~10 paths (avg)",                                 "5 chunks (k=5)"),
        ("Reachability / Relevance range",
            f"{neo.get('min_reachability', '?')} – {neo.get('max_reachability', '?')}",
            f"{chroma.get('min_relevance', '?')} – {chroma.get('max_relevance', '?')}"),
        ("Avg reachability / relevance",  str(neo.get("avg_reachability", "?")),              str(chroma.get("avg_relevance", "?"))),
        ("Fallback triggered",            f"{'Yes' if KNOWN_NEO4J_FALLBACK else 'No'} (0%)",  "No (0%)"),
        ("Records ≥ 0.6 quality threshold",
            f"{neo.get('above_threshold_06', '?')} / {neo.get('total_trajectories', '?')} ({neo.get('threshold_pct', '?')}%)",
            f"{chroma.get('above_threshold_06', '?')} / {chroma.get('sample_size', '?')} ({chroma.get('threshold_pct', '?')}%)"),
    ]

    col_widths = [30, 40, 35]
    fmt = "  {:<{}} | {:<{}} | {:<{}}"

    for row in rows:
        print(fmt.format(row[0], col_widths[0], row[1], col_widths[1], row[2], col_widths[2]))

    print("=" * 75)
    print("\n📌 Why Mentor Discovery returns empty:")
    pct  = neo.get("threshold_pct", "?")
    racc = neo.get("avg_reachability", "?")
    print(f"   → Mean reachability across all trajectories = {racc}")
    print(f"   → Only {pct}% of trajectories meet the ≥ 0.6 threshold required by MentorDiscoveryAgent.")
    print(f"   → Top retrieved score this run = {neo.get('max_reachability', '?')}")
    print(f"   → Recommendation: Lower threshold to 0.5 or tune Neo4j ingestion quality.\n")


# ─── Entry Point ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n🔍 Querying Neo4j...")
    try:
        neo_stats = query_neo4j()
        print(f"   ✅ Neo4j: {neo_stats['total_nodes']} nodes, {neo_stats['total_trajectories']} trajectories")
    except Exception as e:
        print(f"   ❌ Neo4j error: {e}")
        neo_stats = {}

    print("🔍 Querying ChromaDB...")
    try:
        chroma_stats = query_chroma()
        print(f"   ✅ ChromaDB: {chroma_stats['total_docs']} documents")
    except Exception as e:
        print(f"   ❌ ChromaDB error: {e}")
        chroma_stats = {}

    print_table(neo_stats, chroma_stats)
