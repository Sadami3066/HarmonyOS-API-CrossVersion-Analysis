#!/usr/bin/env python3
"""CLI tool to query OpenHarmony official doc RAG database and perform cross-version comparison."""

import argparse
import json
import sys
from doc_rag.retriever import DocRetriever


def format_chunk_card(result, idx=1) -> str:
    c = result.chunk
    lines = [
        f"--- [{idx}] [{c.category.upper()}] {c.full_name} (Score: {result.score:.2f}, Match: {result.match_type}) ---",
        f"Version: {c.version} | Kit: {c.kit} | Module: {c.module}",
        f"File: {c.file_path}",
    ]
    if c.signature:
        lines.append(f"Signature: {c.signature}")
    if c.since:
        lines.append(f"Since: {c.since}")
    if c.deprecated:
        lines.append("Deprecated: YES")
    if c.permission:
        lines.append(f"Permission: {c.permission}")
    if c.syscap:
        lines.append(f"SysCap: {c.syscap}")
    if c.atomic_service:
        lines.append(f"Atomic Service: {c.atomic_service}")
    if c.description:
        desc_preview = c.description[:180] + ("..." if len(c.description) > 180 else "")
        lines.append(f"Description: {desc_preview}")
    if c.parameters_summary:
        lines.append(f"Parameters:\n{c.parameters_summary[:200]}")
    if c.return_summary:
        lines.append(f"Return: {c.return_summary[:120]}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query OpenHarmony official doc RAG database.")
    parser.add_argument("--db-path", type=str, default="data/official_doc_rag.db", help="Path to SQLite DB")
    parser.add_argument("--name", type=str, default=None, help="Search by API name (exact/prefix)")
    parser.add_argument("--keyword", type=str, default=None, help="Search by keyword (BM25 full text)")
    parser.add_argument("--query", type=str, default=None, help="Hybrid search (name + keyword)")
    parser.add_argument("--compare", type=str, default=None, help="Compare API across versions")
    parser.add_argument("--version", type=str, default=None, help="Filter by version")
    parser.add_argument("--versions", type=str, default=None, help="Comma-separated versions for comparison")
    parser.add_argument("--kit", type=str, default=None, help="Filter by kit")
    parser.add_argument("--module", type=str, default=None, help="Filter by module")
    parser.add_argument("--permission", type=str, default=None, help="Filter by permission")
    parser.add_argument("--syscap", type=str, default=None, help="Filter by system capability")
    parser.add_argument("--category", type=str, default=None, help="Filter by category (method, property, enum, etc.)")
    parser.add_argument("--deprecated", action="store_true", help="Filter deprecated APIs")
    parser.add_argument("--limit", type=int, default=10, help="Max results")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")

    args = parser.parse_args()

    retriever = DocRetriever(db_path=args.db_path)

    if args.stats:
        stats = retriever.indexer.get_stats()
        if args.json:
            print(json.dumps(stats, ensure_ascii=False, indent=2))
        else:
            print("=== Doc RAG Database Stats ===")
            print(f"Total Chunks: {stats['total_chunks']}")
            print(f"Total FTS Chunks: {stats.get('total_fts', 'N/A')}")
            print(f"Distinct APIs: {stats['distinct_apis']}")
            print(f"Versions: {stats['by_version']}")
            print(f"Categories: {stats['by_category']}")
            print(f"Top Kits: {stats['top_kits']}")
        return

    # Cross-version comparison
    if args.compare:
        target_versions = [v.strip() for v in args.versions.split(",")] if args.versions else None
        comp_res = retriever.compare_api_across_versions(api_name=args.compare, target_versions=target_versions)
        if args.json:
            print(json.dumps(comp_res.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(comp_res.summary_markdown)
        return

    # Name search
    if args.name:
        results = retriever.search_by_name(
            name=args.name,
            version=args.version,
            kit=args.kit,
            limit=args.limit,
        )
    # Keyword search
    elif args.keyword:
        results = retriever.search_by_keyword(
            query=args.keyword,
            version=args.version,
            kit=args.kit,
            limit=args.limit,
        )
    # Hybrid search
    elif args.query:
        results = retriever.search(
            query=args.query,
            version=args.version,
            kit=args.kit,
            module=args.module,
            category=args.category,
            permission=args.permission,
            syscap=args.syscap,
            deprecated=True if args.deprecated else None,
            limit=args.limit,
        )
    # Condition search
    elif any([args.permission, args.syscap, args.category, args.deprecated, args.module]):
        results = retriever.search_by_condition(
            version=args.version,
            kit=args.kit,
            module=args.module,
            category=args.category,
            permission=args.permission,
            syscap=args.syscap,
            deprecated=True if args.deprecated else None,
            limit=args.limit,
        )
    else:
        parser.print_help()
        sys.exit(1)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        print(f"\nFound {len(results)} matching chunks:\n")
        for idx, r in enumerate(results, 1):
            print(format_chunk_card(r, idx))
            print()


if __name__ == "__main__":
    main()
