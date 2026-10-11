#!/usr/bin/env python3
"""CLI tool to ingest OpenHarmony official developer reference docs into SQLite + FTS5 RAG database."""

import argparse
import os
import sys
import time
from doc_rag.indexer import DocIndexer


def main():
    parser = argparse.ArgumentParser(description="Ingest OpenHarmony official docs into RAG database.")
    parser.add_argument(
        "--doc-dir",
        type=str,
        default=None,
        help="Path to unzipped docs directory (e.g. official/docs-OpenHarmony-v6.0.0.1-Release-.../zh-cn/application-dev/reference)",
    )
    parser.add_argument(
        "--zip",
        type=str,
        default=None,
        help="Path to doc zip archive (e.g. official/docs-OpenHarmony-v6.1-LTS-zh-cn-application-dev-reference.zip)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="v6.0.0.1-Release",
        help="Version tag for the ingested documents (e.g. v6.0.0.1-Release, v6.1-LTS)",
    )
    parser.add_argument(
        "--kit",
        type=str,
        default="apis-network-kit",
        help="Comma-separated kit filters (e.g. 'apis-network-kit' or 'all' to ingest all kits)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/official_doc_rag.db",
        help="SQLite database path",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing version data in DB before ingesting",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Print database statistics and exit",
    )

    args = parser.parse_args()

    indexer = DocIndexer(db_path=args.db_path)

    if args.stats:
        stats = indexer.get_stats()
        print("=== Official Doc RAG Database Stats ===")
        print(f"Database: {args.db_path}")
        print(f"Total Chunks: {stats['total_chunks']}")
        print(f"Total FTS Chunks: {stats.get('total_fts', 'N/A')}")
        print(f"Distinct APIs: {stats['distinct_apis']}")
        print(f"Versions: {stats['by_version']}")
        print(f"Categories: {stats['by_category']}")
        print(f"Top Kits: {stats['top_kits']}")
        return

    if not args.doc_dir and not args.zip:
        # Default behavior: try local extracted v6.0.0.1-Release directory
        default_dir = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference"
        if os.path.exists(default_dir):
            args.doc_dir = default_dir
            print(f"Using default extracted doc directory: {default_dir}")
        else:
            parser.print_help()
            sys.exit(1)

    kit_filter = None if args.kit.lower() == "all" else [k.strip() for k in args.kit.split(",") if k.strip()]

    if args.clear:
        cleared = indexer.clear_version(args.version)
        print(f"Cleared {cleared} existing chunks for version '{args.version}'.")

    start_time = time.time()
    total_ingested = 0

    if args.doc_dir:
        print(f"Ingesting directory '{args.doc_dir}' (version: {args.version}, kits: {kit_filter or 'all'})...")
        total_ingested = indexer.ingest_directory(
            doc_dir=args.doc_dir,
            version=args.version,
            kit_filter=kit_filter,
        )
    elif args.zip:
        print(f"Ingesting zip archive '{args.zip}' (version: {args.version}, kits: {kit_filter or 'all'})...")
        total_ingested = indexer.ingest_zip(
            zip_path=args.zip,
            version=args.version,
            kit_filter=kit_filter,
        )

    elapsed = time.time() - start_time
    print(f"Successfully ingested {total_ingested} chunks in {elapsed:.2f}s.")

    stats = indexer.get_stats()
    print("\nUpdated Database Stats:")
    print(f"  Total Chunks: {stats['total_chunks']}")
    print(f"  Total FTS Chunks: {stats.get('total_fts', 'N/A')}")
    print(f"  Distinct APIs: {stats['distinct_apis']}")
    print(f"  By Version: {stats['by_version']}")
    print(f"  By Category: {stats['by_category']}")


if __name__ == "__main__":
    main()
