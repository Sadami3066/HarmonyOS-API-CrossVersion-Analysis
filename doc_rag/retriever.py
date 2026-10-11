"""Search and Retrieval Engine for OpenHarmony Official Document RAG.

Supports:
- Name retrieval (exact match, parent.method match, prefix match)
- Keyword retrieval (full-text BM25 search via SQLite FTS5)
- Condition filtering (version, kit, module, category, permission, syscap, since, deprecated)
- Hybrid search (combining name boost + BM25 keyword score + filters)
- Cross-version API attribute comparison (side-by-side attribute extraction for LLMs)
"""

import sqlite3
import re
from typing import List, Dict, Any, Optional, Tuple
from doc_rag.models import DocChunk, SearchResult, SearchFilter, VersionComparisonResult
from doc_rag.indexer import DocIndexer, tokenize_for_search


def parse_api_query(name: str) -> Tuple[str, str, str]:
    """Given a query like 'HttpRequest.request()', 'http.createHttp', 'createHttp()',
    returns (clean_name, parent_query, method_query)."""
    clean = name.strip()
    clean = re.sub(r"<sup>.*?</sup>", "", clean).strip()
    clean = re.sub(r"\(\s*\)$", "", clean).strip()
    clean = clean.strip("`'\"")

    parent_query = ""
    method_query = clean
    if "." in clean and not clean.startswith("@"):
        parts = clean.split(".")
        parent_query = parts[-2]
        method_query = parts[-1]
    return clean, parent_query, method_query


class DocRetriever:
    """Retriever for querying the OpenHarmony official doc RAG database."""

    def __init__(self, db_path: str = "data/official_doc_rag.db", indexer: Optional[DocIndexer] = None):
        if indexer is not None:
            self.indexer = indexer
        elif isinstance(db_path, DocIndexer):
            self.indexer = db_path
        else:
            self.indexer = DocIndexer(db_path=db_path)

    def _get_connection(self) -> sqlite3.Connection:
        return self.indexer.get_connection()

    def search_by_name(
        self,
        name: str,
        version: Optional[str] = None,
        kit: Optional[str] = None,
        exact: bool = False,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search APIs by name (supports 'createHttp', 'HttpRequest.request', 'on(\"headersReceive\")', etc.)."""
        clean_name, parent_query, method_query = parse_api_query(name)
        if not clean_name:
            return []

        sql = """
            SELECT *,
                CASE
                    WHEN api_name = ? COLLATE NOCASE THEN 100.0
                    WHEN parent_title = ? COLLATE NOCASE AND api_name = ? COLLATE NOCASE THEN 98.0
                    WHEN heading_text = ? COLLATE NOCASE THEN 95.0
                    WHEN full_name = ? COLLATE NOCASE THEN 90.0
                    WHEN api_name LIKE ? COLLATE NOCASE THEN 70.0
                    WHEN heading_text LIKE ? COLLATE NOCASE THEN 65.0
                    WHEN full_name LIKE ? COLLATE NOCASE THEN 60.0
                    ELSE 40.0
                END as match_score
            FROM doc_chunks
            WHERE (
                api_name = ? COLLATE NOCASE
                OR full_name = ? COLLATE NOCASE
                OR heading_text = ? COLLATE NOCASE
                OR (parent_title = ? COLLATE NOCASE AND api_name = ? COLLATE NOCASE)
                OR (parent_title = '' AND api_name = ? COLLATE NOCASE AND (module LIKE ? COLLATE NOCASE OR heading_text LIKE ? COLLATE NOCASE))
                OR (? = 0 AND (
                    api_name LIKE ? COLLATE NOCASE
                    OR full_name LIKE ? COLLATE NOCASE
                    OR heading_text LIKE ? COLLATE NOCASE
                ))
            )
        """
        params: List[Any] = [
            clean_name,
            parent_query,
            method_query,
            clean_name,
            clean_name,
            f"%{clean_name}%",
            f"%{clean_name}%",
            f"%{clean_name}%",
            # WHERE clause:
            clean_name,
            clean_name,
            clean_name,
            parent_query,
            method_query,
            method_query,
            f"%{parent_query}%",
            f"{parent_query}.%",
            1 if exact else 0,
            f"%{clean_name}%",
            f"%{clean_name}%",
            f"%{clean_name}%",
        ]

        if version:
            sql += " AND version = ?"
            params.append(version)
        if kit:
            sql += " AND (kit = ? OR kit LIKE ?)"
            params.extend([kit, f"%{kit}%"])

        sql += " ORDER BY match_score DESC, rowid ASC LIMIT ?"
        params.append(limit)

        results: List[SearchResult] = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            for row in cur.fetchall():
                chunk = DocChunk.from_dict(dict(row))
                match_type = "exact_name" if row["match_score"] >= 90.0 else "prefix_name"
                results.append(
                    SearchResult(
                        chunk=chunk,
                        score=float(row["match_score"]),
                        match_type=match_type,
                        highlights={"api_name": chunk.api_name, "full_name": chunk.full_name},
                    )
                )
        finally:
            conn.close()

        return results

    def search_by_keyword(
        self,
        query: str,
        version: Optional[str] = None,
        kit: Optional[str] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search documentation by keyword using SQLite FTS5 BM25 full-text ranking."""
        raw_tokens = tokenize_for_search(query).split()
        if not raw_tokens:
            return []

        # Sanitize tokens for FTS5: wrap words in double quotes to avoid FTS operators (AND, OR, NOT, NEAR)
        fts_tokens = [f'"{tok}"' for tok in raw_tokens if tok]
        fts_match_expr = " AND ".join(fts_tokens)

        sql = """
            SELECT dc.*, MIN(fts.rank) as fts_rank
            FROM doc_chunks_fts fts
            JOIN doc_chunks dc ON dc.chunk_id = fts.chunk_id
            WHERE doc_chunks_fts MATCH ?
        """
        params: List[Any] = [fts_match_expr]

        if version:
            sql += " AND dc.version = ?"
            params.append(version)
        if kit:
            sql += " AND (dc.kit = ? OR dc.kit LIKE ?)"
            params.extend([kit, f"%{kit}%"])

        sql += " GROUP BY dc.chunk_id ORDER BY fts_rank ASC LIMIT ?"
        params.append(limit)

        results: List[SearchResult] = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            try:
                cur.execute(sql, params)
                rows = cur.fetchall()
            except sqlite3.OperationalError:
                try:
                    # Fallback to OR match
                    fts_match_expr = " OR ".join(fts_tokens)
                    params[0] = fts_match_expr
                    cur.execute(sql, params)
                    rows = cur.fetchall()
                except sqlite3.OperationalError:
                    # Final fallback to LIKE search on doc_chunks
                    clean_kw = query.strip()
                    like_sql = "SELECT * FROM doc_chunks WHERE (raw_content LIKE ? OR api_name LIKE ?)"
                    like_params: List[Any] = [f"%{clean_kw}%", f"%{clean_kw}%"]
                    if version:
                        like_sql += " AND version = ?"
                        like_params.append(version)
                    if kit:
                        like_sql += " AND (kit = ? OR kit LIKE ?)"
                        like_params.extend([kit, f"%{kit}%"])
                    like_sql += " LIMIT ?"
                    like_params.append(limit)
                    cur.execute(like_sql, like_params)
                    rows = cur.fetchall()

            for row in rows:
                row_dict = dict(row)
                row_dict.pop("fts_rank", None)
                chunk = DocChunk.from_dict(row_dict)
                score = round(abs(float(row["fts_rank"])), 4) if "fts_rank" in row.keys() else 1.0
                results.append(
                    SearchResult(
                        chunk=chunk,
                        score=score,
                        match_type="keyword",
                        highlights={"matched_query": query},
                    )
                )
        finally:
            conn.close()

        return results

    def search_by_condition(
        self,
        version: Optional[str] = None,
        kit: Optional[str] = None,
        module: Optional[str] = None,
        category: Optional[str] = None,
        permission: Optional[str] = None,
        syscap: Optional[str] = None,
        since: Optional[str] = None,
        deprecated: Optional[bool] = None,
        limit: int = 50,
    ) -> List[SearchResult]:
        """Search APIs with structured conditions (e.g. find all deprecated APIs, or APIs requiring a specific permission)."""
        conditions = []
        params: List[Any] = []

        if version:
            conditions.append("version = ?")
            params.append(version)
        if kit:
            conditions.append("(kit = ? OR kit LIKE ?)")
            params.extend([kit, f"%{kit}%"])
        if module:
            conditions.append("(module = ? OR module LIKE ?)")
            params.extend([module, f"%{module}%"])
        if category:
            conditions.append("category = ?")
            params.append(category)
        if permission:
            conditions.append("permission LIKE ?")
            params.append(f"%{permission}%")
        if syscap:
            conditions.append("syscap LIKE ?")
            params.append(f"%{syscap}%")
        if since:
            conditions.append("since LIKE ?")
            params.append(f"%{since}%")
        if deprecated is not None:
            conditions.append("deprecated = ?")
            params.append(1 if deprecated else 0)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM doc_chunks WHERE {where_clause} ORDER BY version, heading_path LIMIT ?"
        params.append(limit)

        results: List[SearchResult] = []
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            for row in cur.fetchall():
                chunk = DocChunk.from_dict(dict(row))
                results.append(
                    SearchResult(
                        chunk=chunk,
                        score=1.0,
                        match_type="condition",
                    )
                )
        finally:
            conn.close()

        return results

    def search(
        self,
        query: str,
        version: Optional[str] = None,
        kit: Optional[str] = None,
        module: Optional[str] = None,
        category: Optional[str] = None,
        permission: Optional[str] = None,
        syscap: Optional[str] = None,
        deprecated: Optional[bool] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Hybrid search combining exact/prefix name matches with keyword full-text search."""
        seen_ids = set()
        merged_results: List[SearchResult] = []

        # 1. First attempt name match
        name_results = self.search_by_name(query, version=version, kit=kit, exact=False, limit=limit)
        for r in name_results:
            if r.chunk.chunk_id not in seen_ids:
                seen_ids.add(r.chunk.chunk_id)
                merged_results.append(r)

        # 2. Attempt keyword match
        kw_results = self.search_by_keyword(query, version=version, kit=kit, limit=limit * 2)
        for r in kw_results:
            if r.chunk.chunk_id not in seen_ids:
                seen_ids.add(r.chunk.chunk_id)
                merged_results.append(r)

        # 3. Apply post-filters if specified
        filtered_results = []
        for r in merged_results:
            c = r.chunk
            if module and module.lower() not in c.module.lower():
                continue
            if category and c.category != category:
                continue
            if permission and permission.lower() not in c.permission.lower():
                continue
            if syscap and syscap.lower() not in c.syscap.lower():
                continue
            if deprecated is not None and c.deprecated != deprecated:
                continue
            filtered_results.append(r)

        return filtered_results[:limit]

    def compare_api_across_versions(
        self,
        api_name: str,
        target_versions: Optional[List[str]] = None,
    ) -> VersionComparisonResult:
        """Compare attributes of a specific API across multiple versions in the database."""
        clean_name, parent_query, method_query = parse_api_query(api_name)
        if not clean_name:
            target_versions = target_versions or []
            return VersionComparisonResult(
                api_name=api_name,
                target_versions=target_versions,
                found_versions=[],
                missing_versions=target_versions,
                by_version={v: [] for v in target_versions},
                differences={},
                summary_markdown="No API name provided for comparison.",
            )
        conn = self._get_connection()
        try:
            cur = conn.cursor()

            # Determine target versions if not specified
            if not target_versions:
                cur.execute("SELECT DISTINCT version FROM doc_chunks ORDER BY version ASC;")
                target_versions = [row[0] for row in cur.fetchall()]

            # Fetch matching chunks across versions
            if parent_query and method_query:
                sql = """
                    SELECT * FROM doc_chunks
                    WHERE (
                        (parent_title = ? COLLATE NOCASE AND api_name = ? COLLATE NOCASE)
                        OR full_name = ? COLLATE NOCASE
                        OR full_name LIKE ? COLLATE NOCASE
                        OR heading_text = ? COLLATE NOCASE
                        OR (parent_title = '' AND api_name = ? COLLATE NOCASE AND (module LIKE ? COLLATE NOCASE OR heading_text LIKE ? COLLATE NOCASE))
                    )
                    ORDER BY version ASC, heading_path ASC, rowid ASC;
                """
                params = [
                    parent_query,
                    method_query,
                    clean_name,
                    f"%.{clean_name}",
                    clean_name,
                    method_query,
                    f"%{parent_query}%",
                    f"{parent_query}.%",
                ]
            else:
                sql = """
                    SELECT * FROM doc_chunks
                    WHERE (
                        api_name = ? COLLATE NOCASE
                        OR parent_title = ? COLLATE NOCASE
                        OR full_name = ? COLLATE NOCASE
                        OR full_name LIKE ? COLLATE NOCASE
                        OR heading_text = ? COLLATE NOCASE
                    )
                    ORDER BY version ASC, heading_path ASC, rowid ASC;
                """
                params = [
                    clean_name,
                    clean_name,
                    clean_name,
                    f"%.{clean_name}",
                    clean_name,
                ]

            cur.execute(sql, params)
            rows = cur.fetchall()
        finally:
            conn.close()

        by_version: Dict[str, List[DocChunk]] = {v: [] for v in target_versions}
        found_versions_set = set()

        for row in rows:
            chunk = DocChunk.from_dict(dict(row))
            if chunk.version in by_version:
                by_version[chunk.version].append(chunk)
                found_versions_set.add(chunk.version)

        found_versions = [v for v in target_versions if v in found_versions_set]
        missing_versions = [v for v in target_versions if v not in found_versions_set]

        # Analyze differences
        differences = self._analyze_version_differences(clean_name, target_versions, by_version)

        # Generate LLM-ready markdown summary
        summary_md = self._format_comparison_markdown(clean_name, target_versions, by_version, differences)

        return VersionComparisonResult(
            api_name=clean_name,
            target_versions=target_versions,
            found_versions=found_versions,
            missing_versions=missing_versions,
            by_version=by_version,
            differences=differences,
            summary_markdown=summary_md,
        )

    def _analyze_version_differences(
        self,
        api_name: str,
        target_versions: List[str],
        by_version: Dict[str, List[DocChunk]],
    ) -> Dict[str, Any]:
        """Analyze detailed attribute differences between versions for an API."""
        diff: Dict[str, Any] = {
            "version_status": {},
            "signatures_by_version": {},
            "properties_by_version": {},
            "methods_by_version": {},
            "since_by_version": {},
            "permission_by_version": {},
            "syscap_by_version": {},
            "deprecated_by_version": {},
            "changes_detected": [],
        }

        for v in target_versions:
            chunks = by_version.get(v, [])
            if not chunks:
                diff["version_status"][v] = "NOT_FOUND"
                continue

            diff["version_status"][v] = "AVAILABLE"
            sigs = [c.signature for c in chunks if c.signature]
            props = [c.api_name for c in chunks if c.category == "property"]
            methods = [c.api_name for c in chunks if c.category in ["method", "function"]]
            sinces = sorted(list(set([c.since for c in chunks if c.since])))
            perms = sorted(list(set([c.permission for c in chunks if c.permission])))
            syscaps = sorted(list(set([c.syscap for c in chunks if c.syscap])))
            dep = any(c.deprecated for c in chunks)

            diff["signatures_by_version"][v] = sigs
            diff["properties_by_version"][v] = props
            diff["methods_by_version"][v] = methods
            diff["since_by_version"][v] = sinces
            diff["permission_by_version"][v] = perms
            diff["syscap_by_version"][v] = syscaps
            diff["deprecated_by_version"][v] = dep

        # Check additions/removals between consecutive versions
        for i in range(len(target_versions) - 1):
            v_curr = target_versions[i]
            v_next = target_versions[i + 1]

            status_curr = diff["version_status"].get(v_curr)
            status_next = diff["version_status"].get(v_next)

            if status_curr == "NOT_FOUND" and status_next == "AVAILABLE":
                diff["changes_detected"].append(f"【新增 API】{api_name} 在 {v_curr} 中不存在，在 {v_next} 中首次引入。")
            elif status_curr == "AVAILABLE" and status_next == "NOT_FOUND":
                diff["changes_detected"].append(f"【删除 API】{api_name} 在 {v_curr} 中存在，在 {v_next} 中被移除。")
            elif status_curr == "AVAILABLE" and status_next == "AVAILABLE":
                # Compare properties
                p_curr = set(diff["properties_by_version"].get(v_curr, []))
                p_next = set(diff["properties_by_version"].get(v_next, []))
                added_props = p_next - p_curr
                removed_props = p_curr - p_next
                if added_props:
                    diff["changes_detected"].append(
                        f"【新增属性】从 {v_curr} 到 {v_next}，新增属性: {', '.join(sorted(added_props))}"
                    )
                if removed_props:
                    diff["changes_detected"].append(
                        f"【删除属性】从 {v_curr} 到 {v_next}，删除属性: {', '.join(sorted(removed_props))}"
                    )

                # Compare methods
                m_curr = set(diff["methods_by_version"].get(v_curr, []))
                m_next = set(diff["methods_by_version"].get(v_next, []))
                added_methods = m_next - m_curr
                removed_methods = m_curr - m_next
                if added_methods:
                    diff["changes_detected"].append(
                        f"【新增方法】从 {v_curr} 到 {v_next}，新增方法: {', '.join(sorted(added_methods))}"
                    )
                if removed_methods:
                    diff["changes_detected"].append(
                        f"【删除方法】从 {v_curr} 到 {v_next}，删除方法: {', '.join(sorted(removed_methods))}"
                    )

                # Compare permissions
                perm_curr = set(diff["permission_by_version"].get(v_curr, []))
                perm_next = set(diff["permission_by_version"].get(v_next, []))
                if perm_curr != perm_next:
                    diff["changes_detected"].append(
                        f"【权限变化】{v_curr}: {perm_curr or 'None'} -> {v_next}: {perm_next or 'None'}"
                    )

                # Compare deprecation
                dep_curr = diff["deprecated_by_version"].get(v_curr, False)
                dep_next = diff["deprecated_by_version"].get(v_next, False)
                if not dep_curr and dep_next:
                    diff["changes_detected"].append(f"【标记废弃】{api_name} 在 {v_next} 中被标记为已废弃 (deprecated)。")

        return diff

    def _format_comparison_markdown(
        self,
        api_name: str,
        target_versions: List[str],
        by_version: Dict[str, List[DocChunk]],
        differences: Dict[str, Any],
    ) -> str:
        """Format version comparison into clean markdown for LLM consumption."""
        lines = [
            f"### API 跨版本官方文档对比：`{api_name}`",
            "",
            f"**核对版本：** {', '.join(target_versions)}",
            "",
            "#### 1. 版本存在性与核心属性概览",
            "",
            "| 版本 | 状态 | 起始版本 (Since) | 所需权限 (Permission) | 系统能力 (SysCap) | 包含条目/属性数 |",
            "|---|---|---|---|---|---|",
        ]

        for v in target_versions:
            chunks = by_version.get(v, [])
            if not chunks:
                lines.append(f"| {v} | ❌ 未提供 | - | - | - | 0 |")
            else:
                since_str = ", ".join(differences["since_by_version"].get(v, [])) or "首批支持"
                perm_str = ", ".join(differences["permission_by_version"].get(v, [])) or "无需特殊权限"
                syscap_str = ", ".join(differences["syscap_by_version"].get(v, [])) or "默认"
                count = len(chunks)
                lines.append(f"| {v} | ✅ 已支持 | {since_str} | {perm_str} | {syscap_str} | {count} |")

        lines.append("")
        lines.append("#### 2. 识别到的版本能力区别")
        lines.append("")
        if differences.get("changes_detected"):
            for change in differences["changes_detected"]:
                lines.append(f"- {change}")
        else:
            lines.append("- 未检测到显著属性增删（两版本基本属性一致或仅存在文档描述细节微调）。")

        lines.append("")
        lines.append("#### 3. 各版本详细声明与说明")
        lines.append("")

        for v in target_versions:
            chunks = by_version.get(v, [])
            lines.append(f"##### 【版本: {v}】")
            if not chunks:
                lines.append(f"此版本官方文档未收录 `{api_name}`。")
                lines.append("")
                continue

            for idx, c in enumerate(chunks, 1):
                lines.append(f"**条目 {idx}：[{c.category}] `{c.full_name}`**")
                if c.signature:
                    lines.append(f"- **签名：** `{c.signature}`")
                if c.since:
                    lines.append(f"- **起始版本：** {c.since}")
                if c.deprecated:
                    lines.append(f"- **是否废弃：** 是")
                if c.permission:
                    lines.append(f"- **权限：** {c.permission}")
                if c.syscap:
                    lines.append(f"- **系统能力：** {c.syscap}")
                if c.atomic_service:
                    lines.append(f"- **原子化服务：** {c.atomic_service}")
                if c.description:
                    lines.append(f"- **说明：** {c.description}")
                if c.parameters_summary:
                    lines.append(f"- **参数：**\n{c.parameters_summary}")
                if c.return_summary:
                    lines.append(f"- **返回值：** {c.return_summary}")
                lines.append("")

        return "\n".join(lines)
