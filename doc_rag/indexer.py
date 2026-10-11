"""SQLite + FTS5 Indexer for OpenHarmony Official Reference Documentation."""

import os
import re
import sqlite3
import zipfile
from typing import List, Dict, Any, Optional
from doc_rag.models import DocChunk
from doc_rag.parser import DocParser


def tokenize_for_search(text: str) -> str:
    """Tokenize English words, dot-separated identifiers, and CJK characters (unigram + bigram)."""
    tokens = []
    # English/alphanumeric words & identifiers
    for m in re.finditer(r"[a-zA-Z0-9_\.]+", text):
        word = m.group(0).lower()
        tokens.append(word)
        if "." in word:
            for sub in word.split("."):
                if sub:
                    tokens.append(sub)

    # CJK unigrams and bigrams
    for m in re.finditer(r"[\u4e00-\u9fff]+", text):
        s = m.group(0)
        for i in range(len(s)):
            tokens.append(s[i])
            if i + 1 < len(s):
                tokens.append(s[i : i + 2])

    return " ".join(tokens)


class DocIndexer:
    """Manages SQLite and FTS5 storage for official documentation RAG."""

    def __init__(self, db_path: str = "data/official_doc_rag.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema and FTS5 virtual table."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.cursor()

                # Main structured chunks table
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS doc_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        version TEXT NOT NULL,
                        kit TEXT,
                        subsystem TEXT,
                        module TEXT,
                        file_path TEXT,
                        file_title TEXT,
                        heading_level INTEGER,
                        heading_text TEXT,
                        parent_title TEXT,
                        heading_path TEXT,
                        category TEXT,
                        api_name TEXT,
                        full_name TEXT,
                        signature TEXT,
                        since TEXT,
                        deprecated INTEGER,
                        permission TEXT,
                        syscap TEXT,
                        atomic_service TEXT,
                        description TEXT,
                        parameters_summary TEXT,
                        return_summary TEXT,
                        error_codes_summary TEXT,
                        example TEXT,
                        raw_content TEXT,
                        created_at TEXT
                    );
                    """
                )

                # Indexes for structured filtering and fast lookups
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_version ON doc_chunks(version);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_api_name ON doc_chunks(api_name COLLATE NOCASE);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_full_name ON doc_chunks(full_name COLLATE NOCASE);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_parent_title ON doc_chunks(parent_title COLLATE NOCASE);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_kit ON doc_chunks(kit);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_module ON doc_chunks(module);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_category ON doc_chunks(category);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_permission ON doc_chunks(permission);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_syscap ON doc_chunks(syscap);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_since ON doc_chunks(since);",
                    "CREATE INDEX IF NOT EXISTS idx_doc_chunks_deprecated ON doc_chunks(deprecated);",
                ]
                for idx_sql in indexes:
                    cur.execute(idx_sql)

                # FTS5 full-text table
                cur.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS doc_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        api_name,
                        parent_title,
                        full_name,
                        search_tokens,
                        tokenize = "unicode61"
                    );
                    """
                )
        finally:
            conn.close()

    def ingest_chunks(self, chunks: List[DocChunk]) -> int:
        """Batch insert or replace DocChunks into SQLite and FTS5 index with in-memory deduplication."""
        if not chunks:
            return 0

        # In-memory deduplication by chunk_id to prevent duplicate rows in FTS5
        unique_chunks: Dict[str, DocChunk] = {}
        for c in chunks:
            unique_chunks[c.chunk_id] = c

        chunk_rows = []
        fts_rows = []

        for c in unique_chunks.values():
            # Build search tokens from all structured fields and raw markdown content
            searchable_text = f"{c.api_name} {c.parent_title} {c.full_name} {c.signature} {c.description} {c.parameters_summary} {c.return_summary} {c.error_codes_summary} {c.permission} {c.syscap} {c.raw_content}"
            search_tokens = tokenize_for_search(searchable_text)

            chunk_rows.append(
                (
                    c.chunk_id,
                    c.version,
                    c.kit,
                    c.subsystem,
                    c.module,
                    c.file_path,
                    c.file_title,
                    c.heading_level,
                    c.heading_text,
                    c.parent_title,
                    c.heading_path,
                    c.category,
                    c.api_name,
                    c.full_name,
                    c.signature,
                    c.since,
                    int(c.deprecated),
                    c.permission,
                    c.syscap,
                    c.atomic_service,
                    c.description,
                    c.parameters_summary,
                    c.return_summary,
                    c.error_codes_summary,
                    c.example,
                    c.raw_content,
                    c.created_at,
                )
            )

            fts_rows.append(
                (
                    c.chunk_id,
                    c.api_name,
                    c.parent_title,
                    c.full_name,
                    search_tokens,
                )
            )

        conn = self.get_connection()
        try:
            with conn:
                cur = conn.cursor()
                # Insert into main table
                cur.executemany(
                    """
                    INSERT OR REPLACE INTO doc_chunks (
                        chunk_id, version, kit, subsystem, module, file_path, file_title,
                        heading_level, heading_text, parent_title, heading_path, category,
                        api_name, full_name, signature, since, deprecated, permission,
                        syscap, atomic_service, description, parameters_summary, return_summary,
                        error_codes_summary, example, raw_content, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    chunk_rows,
                )

                # Update FTS5 table: delete any existing entries for these IDs, then insert once per chunk
                chunk_ids = list(unique_chunks.keys())
                cur.executemany("DELETE FROM doc_chunks_fts WHERE chunk_id = ?;", [(cid,) for cid in chunk_ids])
                cur.executemany(
                    """
                    INSERT INTO doc_chunks_fts (chunk_id, api_name, parent_title, full_name, search_tokens)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    fts_rows,
                )
        finally:
            conn.close()

        return len(unique_chunks)

    def ingest_directory(
        self,
        doc_dir: str,
        version: str,
        kit_filter: Optional[List[str]] = None,
    ) -> int:
        """Parse and ingest markdown files from a local directory."""
        if not os.path.exists(doc_dir):
            raise FileNotFoundError(f"Documentation directory not found: {doc_dir}")

        parser = DocParser(version=version)
        total_ingested = 0
        batch: List[DocChunk] = []

        for root, _, files in os.walk(doc_dir):
            # Check kit filter if provided
            if kit_filter:
                rel_from_base = os.path.relpath(root, doc_dir).replace("\\", "/")
                matched = any(k in rel_from_base for k in kit_filter)
                if not matched:
                    continue

            for f in files:
                if f.endswith(".md"):
                    full_path = os.path.join(root, f)
                    rel_path = os.path.relpath(full_path, doc_dir).replace("\\", "/")
                    try:
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                            content = fp.read()
                        chunks = parser.parse_file_content(rel_path, content)
                        batch.extend(chunks)
                        if len(batch) >= 500:
                            total_ingested += self.ingest_chunks(batch)
                            batch = []
                    except Exception as e:
                        print(f"Warning: Failed to parse {full_path}: {e}")

        if batch:
            total_ingested += self.ingest_chunks(batch)

        return total_ingested

    def ingest_zip(
        self,
        zip_path: str,
        version: str,
        kit_filter: Optional[List[str]] = None,
    ) -> int:
        """Parse and ingest markdown files directly from a zip archive."""
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Zip archive not found: {zip_path}")

        parser = DocParser(version=version)
        total_ingested = 0
        batch: List[DocChunk] = []

        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            for entry_name in namelist:
                if not entry_name.endswith(".md"):
                    continue

                if kit_filter:
                    matched = any(k in entry_name for k in kit_filter)
                    if not matched:
                        continue

                try:
                    with zf.open(entry_name) as fp:
                        content = fp.read().decode("utf-8", errors="ignore")
                    # Clean relative path
                    rel_path = entry_name
                    if "application-dev/reference/" in rel_path:
                        rel_path = rel_path.split("application-dev/reference/")[-1]

                    chunks = parser.parse_file_content(rel_path, content)
                    batch.extend(chunks)
                    if len(batch) >= 500:
                        total_ingested += self.ingest_chunks(batch)
                        batch = []
                except Exception as e:
                    print(f"Warning: Failed to parse {entry_name} from {zip_path}: {e}")

        if batch:
            total_ingested += self.ingest_chunks(batch)

        return total_ingested

    def clear_version(self, version: str) -> int:
        """Delete all chunks belonging to a version."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT chunk_id FROM doc_chunks WHERE version = ?;", (version,))
                chunk_ids = [row[0] for row in cur.fetchall()]
                cur.execute("DELETE FROM doc_chunks WHERE version = ?;", (version,))
                cur.executemany("DELETE FROM doc_chunks_fts WHERE chunk_id = ?;", [(cid,) for cid in chunk_ids])
                # Ensure no orphaned FTS records remain
                cur.execute("DELETE FROM doc_chunks_fts WHERE chunk_id NOT IN (SELECT chunk_id FROM doc_chunks);")
                return len(chunk_ids)
        finally:
            conn.close()

    def sync_fts_index(self) -> int:
        """Rebuild or sync doc_chunks_fts from doc_chunks to ensure 100% alignment without orphans."""
        conn = self.get_connection()
        try:
            with conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM doc_chunks_fts;")
                cur.execute(
                    """
                    SELECT chunk_id, api_name, parent_title, full_name, signature,
                           description, parameters_summary, return_summary,
                           error_codes_summary, permission, syscap, raw_content
                    FROM doc_chunks;
                    """
                )
                rows = cur.fetchall()
                fts_rows = []
                for r in rows:
                    searchable_text = f"{r[1]} {r[2]} {r[3]} {r[4]} {r[5]} {r[6]} {r[7]} {r[8]} {r[9]} {r[10]} {r[11]}"
                    search_tokens = tokenize_for_search(searchable_text)
                    fts_rows.append((r[0], r[1], r[2], r[3], search_tokens))
                cur.executemany(
                    """
                    INSERT INTO doc_chunks_fts (chunk_id, api_name, parent_title, full_name, search_tokens)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    fts_rows,
                )
                return len(fts_rows)
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the RAG database."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM doc_chunks;")
            total_chunks = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM doc_chunks_fts;")
            total_fts = cur.fetchone()[0]

            cur.execute("SELECT version, COUNT(*) FROM doc_chunks GROUP BY version;")
            by_version = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute("SELECT kit, COUNT(*) FROM doc_chunks GROUP BY kit ORDER BY COUNT(*) DESC LIMIT 10;")
            top_kits = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute("SELECT category, COUNT(*) FROM doc_chunks GROUP BY category ORDER BY COUNT(*) DESC;")
            by_category = {row[0]: row[1] for row in cur.fetchall()}

            cur.execute("SELECT COUNT(DISTINCT api_name) FROM doc_chunks;")
            distinct_apis = cur.fetchone()[0]

            return {
                "total_chunks": total_chunks,
                "total_fts": total_fts,
                "distinct_apis": distinct_apis,
                "by_version": by_version,
                "by_category": by_category,
                "top_kits": top_kits,
            }
        finally:
            conn.close()
