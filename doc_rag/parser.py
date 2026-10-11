"""Markdown Parser and Structured Chunker for OpenHarmony Official Reference Docs.

Specifically designed according to OpenHarmony query plan (05A):
- Splits by headings, API subsections, and examples without breaking complete signatures or examples.
- Retains platform, version, kit, subsystem, module, path, heading hierarchy, permissions, syscap, and raw markdown.
- Extracts property tables from interfaces/options/structs into distinct property chunks.
- Supports dedicated Interface/Class/Struct docs and C-API documentation seamlessly.
- Ensures different versions are never mixed without labels.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime, timezone
from doc_rag.models import DocChunk


def clean_sup(text: str) -> Tuple[str, str, bool]:
    """Extract since and deprecated tags from superscript or text, returning (clean_text, since, deprecated)."""
    since = ""
    deprecated = False

    # Check superscripts like <sup>10+</sup>, <sup>(deprecated)</sup>, <sup>10+(deprecated)</sup>
    for m in re.finditer(r"<sup>(.*?)</sup>", text):
        sup_content = m.group(1).strip()
        if "deprecated" in sup_content.lower() or "废弃" in sup_content:
            deprecated = True
        num_m = re.search(r"(\d+\+?)", sup_content)
        if num_m:
            since = num_m.group(1)

    clean = re.sub(r"<sup>.*?</sup>", "", text).strip()
    clean = re.sub(r"<!--.*?-->", "", clean).strip()
    clean = re.sub(r"^\*\*(.*?)\*\*$", r"\1", clean).strip()
    clean = re.sub(r"^\[(.*?)\]\(.*?\)$", r"\1", clean).strip()

    # Check text deprecated flags
    if "(deprecated)" in clean.lower():
        deprecated = True
        clean = re.sub(r"\(deprecated\)", "", clean, flags=re.IGNORECASE).strip()
    if "(废弃)" in clean:
        deprecated = True
        clean = clean.replace("(废弃)", "").strip()

    return clean, since, deprecated


def split_table_row(row_str: str) -> List[str]:
    r"""Split a markdown table row considering escaped pipes \|."""
    escaped = row_str.strip().replace(r"\|", "\uE000")
    if escaped.startswith("|"):
        escaped = escaped[1:]
    if escaped.endswith("|"):
        escaped = escaped[:-1]
    return [c.strip().replace("\uE000", "|") for c in escaped.split("|")]


def parse_c_decl(cell: str) -> Tuple[str, str]:
    """Parse C-style declaration in markdown table cell into (variable_name, type_name)."""
    clean = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", cell).strip()
    clean = re.sub(r"<sup>.*?</sup>", "", clean).strip()

    # Check function pointer e.g. void (*callback)(int)
    fp_m = re.search(r"\(\s*\*\s*([a-zA-Z0-9_]+)\s*\)", clean)
    if fp_m:
        return fp_m.group(1), clean

    parts = clean.split()
    if len(parts) >= 2:
        last = parts[-1]
        name = last.lstrip("*")
        stars = len(last) - len(name)
        type_part = clean[: clean.rfind(last)].strip()
        if stars > 0:
            type_part = f"{type_part} {'*' * stars}".strip()
        return name, type_part
    return clean, ""


def extract_metadata_from_text(text: str) -> Dict[str, Any]:
    """Extract standard OpenHarmony metadata tags from text, supporting colon inside and outside asterisks."""
    meta: Dict[str, Any] = {
        "permission": "",
        "syscap": "",
        "atomic_service": "",
        "since": "",
        "deprecated": False,
    }

    # Permission: **需要权限：** or **需要权限**： or **权限：** or **权限**：
    perm_m = re.search(r"\*\*(?:需要)?权限[：:]?\*\*[：:]?\s*([^\n]+)", text)
    if perm_m:
        meta["permission"] = perm_m.group(1).strip().strip("*| \t")

    # System Capability: **系统能力：** or **系统能力**：
    syscap_m = re.search(r"\*\*系统能力[：:]?\*\*[：:]?\s*([^\n]+)", text)
    if syscap_m:
        meta["syscap"] = syscap_m.group(1).strip().strip("*| \t")

    # Atomic service: **原子化服务API：** or **原子化服务API**： or **原子化服务**：
    atomic_m = re.search(r"\*\*原子化服务(?:API)?[：:]?\*\*[：:]?\s*([^\n]+)", text)
    if atomic_m:
        meta["atomic_service"] = atomic_m.group(1).strip().strip("*| \t")

    # Since version from text: **起始版本：** or **起始版本**：
    since_m = re.search(r"\*\*起始版本[：:]?\*\*[：:]?\s*(\d+\+?)", text)
    if since_m:
        meta["since"] = since_m.group(1).strip()
    else:
        # Check text pattern like 自 API version 11 开始支持 or 首批接口从 API version 8
        alt_since = re.search(
            r"(?:自\s*API\s*(?:version)?\s*(\d+\+?)\s*(?:开始)?支持|首批(?:接口|Interface)从\s*API\s*version\s*(\d+))",
            text,
            re.IGNORECASE,
        )
        if alt_since:
            meta["since"] = (alt_since.group(1) or alt_since.group(2)).strip()

    # Deprecated in text
    if re.search(
        r"\*\*废弃[：:]?\*\*[：:]?|自\s*API\s*version\s*\d+\s*开始废弃|自API\s*\d+\s*废弃|\(deprecated\)|\(废弃\)",
        text,
        re.IGNORECASE,
    ):
        meta["deprecated"] = True

    return meta


def extract_sections_by_headings(content: str) -> List[Tuple[int, str, str]]:
    """Split markdown by headings (##, ###, ####), returning list of (level, heading_line, section_body)."""
    heading_pattern = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(content))

    if not matches:
        # Fallback for documents without H2-H4 headings (e.g. Readme-CN, Constants, ErrorCodes)
        h1_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if h1_m:
            heading_text = h1_m.group(1).strip()
            body = content[h1_m.end():].strip()
            if body or heading_text:
                return [(1, heading_text, body)]
        return []

    sections = []
    # Content before first heading
    pre_content = content[: matches[0].start()].strip()
    if pre_content:
        h1_m = re.match(r"^#\s+(.+)$", pre_content)
        if h1_m:
            heading_text = h1_m.group(1).strip()
            body = pre_content[h1_m.end():].strip()
            sections.append((1, heading_text, body))
        else:
            sections.append((1, "Overview", pre_content))

    for idx, match in enumerate(matches):
        level = len(match.group(1))
        heading_text = match.group(2).strip()
        start_pos = match.end()
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        body = content[start_pos:end_pos].strip()
        sections.append((level, heading_text, body))

    return sections


class DocParser:
    """Parser for OpenHarmony developer reference documentation."""

    def __init__(self, version: str):
        self.version = version

    def parse_file_content(self, file_path: str, content: str) -> List[DocChunk]:
        """Parse markdown file content into structured DocChunk objects."""
        chunks: List[DocChunk] = []

        # Extract doc header tags
        kit_m = re.search(r"<!--Kit:\s*(.+?)-->", content)
        subsystem_m = re.search(r"<!--Subsystem:\s*(.+?)-->", content)

        kit = kit_m.group(1).strip() if kit_m else ""
        if not kit:
            # Fallback to directory name e.g. apis-network-kit -> Network Kit
            parts = file_path.replace("\\", "/").split("/")
            for part in parts:
                if part.startswith("apis-") or part.endswith("-kit"):
                    kit = part.replace("apis-", "").replace("-", " ").title()
                    break

        subsystem = subsystem_m.group(1).strip() if subsystem_m else ""

        # H1 Title
        h1_m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        file_title = re.sub(r"<!--.*?-->", "", h1_m.group(1)).strip() if h1_m else os.path.basename(file_path)

        # Extract module name (e.g., @ohos.net.http, @kit.AudioKit)
        module = ""
        mod_m = re.search(r"(@ohos\.[a-zA-Z0-9_\.]+|@kit\.[a-zA-Z0-9_\.]+)", file_title)
        if mod_m:
            module = mod_m.group(1)
        else:
            imp_m = re.search(r"import\s+.*?from\s+['\"](@[a-zA-Z0-9_\.\-]+)['\"]", content)
            if imp_m:
                module = imp_m.group(1)
            else:
                # Check C-API related module or header
                rel_mod_m = re.search(r"\*\*相关模块[：:]?\*\*[：:]?\s*\[(.*?)\]", content)
                header_m = re.search(r"\*\*(?:所在头文件|引用文件)[：:]?\*\*[：:]?\s*(?:\[(.*?)\]|<(.*?)>)", content)
                if rel_mod_m:
                    module = rel_mod_m.group(1).strip()
                elif header_m:
                    module = (header_m.group(1) or header_m.group(2)).strip()
                else:
                    module = os.path.splitext(os.path.basename(file_path))[0]

        # Check default module since
        module_since = ""
        since_intro_m = re.search(r"首批(?:接口|Interface)从\s*API\s*version\s*(\d+)", content, re.IGNORECASE)
        if since_intro_m:
            module_since = since_intro_m.group(1)

        # Check if file defines a specific container (Interface, Class, Struct, Enum)
        container_name = ""
        container_category = ""
        c_m = re.search(r"^#\s+(?:废弃的|弃用的)?(Interface|Class|Struct|Enum|Interfaces|Enums)\s*(?:\((.+?)\))?", content, re.MULTILINE | re.IGNORECASE)
        if c_m and c_m.group(2):
            raw_cname = c_m.group(2).strip()
            if raw_cname not in ["其他", "others", "Common"]:
                container_name = raw_cname
                container_category = c_m.group(1).lower().rstrip("s")
        elif not c_m and h1_m:
            # Check C-API struct file e.g. # Http_RequestOptions
            h1_raw = h1_m.group(1).strip()
            if re.match(r"^[A-Z][a-zA-Z0-9]+_[a-zA-Z0-9_]+$", h1_raw) and not h1_raw.endswith(".h"):
                container_name = h1_raw
                container_category = "struct"

        # Split into sections
        sections = extract_sections_by_headings(content)

        # Hierarchy tracking
        current_h2 = ""
        current_h2_clean = ""
        current_h2_category = "section"

        current_h3 = ""
        current_h3_clean = ""
        current_h3_category = "section"

        # Overload and disambiguation trackers across file
        overload_counters: Dict[str, int] = {}
        prop_counters: Dict[str, int] = {}
        err_counters: Dict[str, int] = {}

        for level, heading_text, body in sections:
            clean_heading, since, deprecated = clean_sup(heading_text)
            if not since and module_since:
                since = module_since

            # Extract metadata from section body
            body_meta = extract_metadata_from_text(body)
            permission = body_meta["permission"]
            syscap = body_meta["syscap"]
            atomic_service = body_meta["atomic_service"]
            if body_meta["since"]:
                since = body_meta["since"]
            if body_meta["deprecated"]:
                deprecated = True

            # Determine category, parent, api_name
            if level == 1:
                # Level 1 Overview / Container chunk
                if container_name:
                    api_name = container_name
                    category = container_category or "interface"
                    full_name = f"{module}.{container_name}" if module else container_name
                    parent_title = ""
                    heading_path = f"{file_title} > {container_name}"
                elif clean_heading in ["Constants", "常量"] or "constant" in file_path.lower():
                    category = "constant"
                    api_name = clean_heading if clean_heading != "Overview" else "Constants"
                    parent_title = ""
                    heading_path = file_title
                    full_name = f"{module}.{api_name}" if module else api_name
                elif clean_heading in ["内核错误码", "错误码"] or "errorcode" in file_path.lower() or "错误码" in file_title:
                    category = "error_code"
                    api_name = clean_heading if clean_heading != "Overview" else file_title
                    parent_title = ""
                    heading_path = file_title
                    full_name = api_name
                else:
                    parent_title = ""
                    api_name = clean_heading if (clean_heading and clean_heading != "Overview") else module
                    heading_path = file_title
                    category = "overview"
                    full_name = api_name if api_name else module
                current_h2 = ""
                current_h2_clean = ""
                current_h3 = ""
                current_h3_clean = ""
            elif level == 2:
                current_h2 = heading_text
                current_h2_clean = clean_heading
                current_h3 = ""
                current_h3_clean = ""

                if container_name:
                    # In a dedicated container file (e.g. AudioRenderer.md)
                    heading_path = f"{file_title} > {container_name} > {clean_heading}"
                    if clean_heading in ["导入模块", "完整示例", "概述", "权限列表", "使用说明", "汇总"]:
                        category = "overview"
                        api_name = clean_heading
                        parent_title = container_name
                        full_name = f"{module}.{container_name}.{clean_heading}" if module else f"{container_name}.{clean_heading}"
                    elif clean_heading in ["属性", "常量", "成员变量"]:
                        category = "section"
                        api_name = clean_heading
                        parent_title = container_name
                        full_name = f"{module}.{container_name}.{clean_heading}" if module else f"{container_name}.{clean_heading}"
                    else:
                        clean_api = clean_heading
                        if clean_api.endswith("()"):
                            clean_api = clean_api[:-2]
                        category = "method"
                        api_name = clean_api
                        parent_title = container_name
                        full_name = f"{module}.{container_name}.{clean_api}" if module else f"{container_name}.{clean_api}"
                    current_h2_category = category
                else:
                    # General module file (e.g. js-apis-http.md)
                    parent_title = ""
                    heading_path = f"{file_title} > {clean_heading}"

                    # Classify H2
                    if clean_heading in ["导入模块", "完整示例", "概述", "汇总"]:
                        category = "overview"
                        api_name = clean_heading
                        full_name = f"{module}.{clean_heading}"
                    elif clean_heading.startswith(f"{module.split('.')[-1]}.") or "." in clean_heading:
                        category = "function"
                        api_name = clean_heading.split(".")[-1].strip("()")
                        full_name = f"{module}.{api_name}"
                    elif any(clean_heading.endswith(suffix) for suffix in ["Options", "Params", "Config", "Result"]):
                        category = "interface"
                        api_name = clean_heading
                        full_name = f"{module}.{clean_heading}"
                    elif "Enum" in clean_heading or clean_heading in [
                        "RequestMethod",
                        "ResponseCode",
                        "HttpDataType",
                        "HttpProtocol",
                        "CertType",
                        "AddressFamily",
                    ]:
                        category = "enum"
                        api_name = clean_heading
                        full_name = f"{module}.{clean_heading}"
                    elif "错误码" in clean_heading or "ErrorCode" in clean_heading:
                        category = "error_code"
                        api_name = clean_heading
                        full_name = f"{module}.{clean_heading}"
                    elif re.match(r"^\d+\s+", clean_heading):
                        category = "error_code"
                        api_name = clean_heading.split()[0]
                        full_name = f"{module}.{api_name}"
                    else:
                        category = "class"
                        api_name = clean_heading
                        full_name = f"{module}.{clean_heading}"
                    current_h2_category = category

            elif level == 3:
                current_h3 = heading_text
                current_h3_clean = clean_heading

                if container_name:
                    parent_title = container_name
                    heading_path = f"{file_title} > {container_name} > {clean_heading}"
                else:
                    parent_title = current_h2_clean
                    heading_path = f"{file_title} > {current_h2_clean} > {clean_heading}" if current_h2_clean else f"{file_title} > {clean_heading}"

                clean_api = clean_heading
                if clean_api.endswith("()"):
                    clean_api = clean_api[:-2]
                api_name = clean_api

                category = "method"
                if clean_heading in ["属性", "常量", "成员变量"]:
                    category = "section"
                elif current_h2_category in ["enum", "error_code"]:
                    category = current_h2_category
                elif "函数" in current_h2_clean or "Function" in current_h2_clean or "函数" in clean_heading:
                    category = "function"
                elif any(clean_heading.endswith(suffix) for suffix in ["Options", "Params", "Config", "Result"]):
                    category = "interface"
                elif "Enum" in clean_heading:
                    category = "enum"
                elif re.match(r"^[A-Z][a-zA-Z0-9]+$", clean_heading):
                    category = "class"
                current_h3_category = category

                full_name = f"{module}.{parent_title}.{api_name}" if parent_title else f"{module}.{api_name}"

            else:  # level >= 4
                clean_api = clean_heading
                if clean_api.endswith("()"):
                    clean_api = clean_api[:-2]
                api_name = clean_api

                if current_h3_clean:
                    parent_title = current_h3_clean
                    prefix = f"{current_h2_clean} > {current_h3_clean}" if current_h2_clean else current_h3_clean
                    if container_name and container_name != current_h2_clean:
                        prefix = f"{container_name} > {prefix}"
                    heading_path = f"{file_title} > {prefix} > {clean_heading}"
                    full_name = f"{module}.{current_h2_clean}.{current_h3_clean}.{api_name}" if current_h2_clean else f"{module}.{current_h3_clean}.{api_name}"
                elif container_name:
                    parent_title = container_name
                    heading_path = f"{file_title} > {container_name} > {clean_heading}"
                    full_name = f"{module}.{container_name}.{api_name}"
                else:
                    parent_title = current_h2_clean
                    heading_path = f"{file_title} > {current_h2_clean} > {clean_heading}" if current_h2_clean else f"{file_title} > {clean_heading}"
                    full_name = f"{module}.{current_h2_clean}.{api_name}" if current_h2_clean else f"{module}.{api_name}"

                category = "method"
                if clean_heading in ["属性", "常量", "成员变量"]:
                    category = "section"
                elif current_h3_category in ["enum", "error_code"]:
                    category = current_h3_category
                elif "函数" in clean_heading or "Function" in clean_heading:
                    category = "function"

            # Extract signature
            signature = ""
            lines = [l.strip() for l in body.splitlines() if l.strip()]
            if lines:
                first_line = lines[0]
                if re.match(r"^[a-zA-Z0-9_\.]+\s*\(.*?\)(?:\s*:\s*.+)?$", first_line):
                    signature = first_line
                elif first_line.startswith("```"):
                    # Code block signature
                    block_lines = []
                    for bl in lines[1:]:
                        if bl.startswith("```"):
                            break
                        block_lines.append(bl)
                    if len(block_lines) <= 4:
                        signature = " ".join(block_lines).strip()

            # Parameters table
            params_summary = ""
            param_m = re.search(r"\*\*(?:参数|参数列表)[：:]?\*\*[：:]?\s*\n+(.*?)(?=\n\*\*|\n### |\n## |\Z)", body, re.DOTALL)
            if param_m:
                params_summary = param_m.group(1).strip()

            # Return table/text
            return_summary = ""
            ret_m = re.search(r"\*\*(?:返回值?|返回)[：:]?\*\*[：:]?\s*\n+(.*?)(?=\n\*\*|\n### |\n## |\Z)", body, re.DOTALL)
            if ret_m:
                return_summary = ret_m.group(1).strip()

            # Error codes
            error_summary = ""
            err_m = re.search(r"\*\*(?:错误码|错误代码)[：:]?\*\*[：:]?\s*\n+(.*?)(?=\n\*\*|\n### |\n## |\Z)", body, re.DOTALL)
            if err_m:
                error_summary = err_m.group(1).strip()

            # Example code block
            example_code = ""
            ex_m = re.search(
                r"\*\*(?:完整)?示例[：:]?\*\*[：:]?\s*\n+(?:<!--.*?-->\s*\n+)*(?:>.*?\n+)*```[a-zA-Z]*\n(.*?)\n```",
                body,
                re.DOTALL,
            )
            if ex_m:
                example_code = ex_m.group(1).strip()
            else:
                ex_m2 = re.search(r"\*\*(?:完整)?示例[：:]?\*\*[：:]?\s*\n+(.*?)(?=\n\*\*|\n### |\n## |\Z)", body, re.DOTALL)
                if ex_m2:
                    cb_m = re.search(r"```[a-zA-Z]*\n(.*?)\n```", ex_m2.group(1), re.DOTALL)
                    if cb_m:
                        example_code = cb_m.group(1).strip()

            # Description extraction
            description = ""
            desc_m = re.search(r"\*\*(?:描述|说明)[：:]?\*\*[：:]?\s*\n+(.*?)(?=\n\*\*|\n### |\n## |\n```|\Z)", body, re.DOTALL)
            if desc_m:
                desc_lines = [
                    l.strip()
                    for l in desc_m.group(1).splitlines()
                    if l.strip() and not l.strip().startswith(">") and not l.strip().startswith("|")
                ]
                description = " ".join(desc_lines).strip()
            else:
                desc_lines = []
                for l in lines:
                    if l == signature:
                        continue
                    if l.startswith("```"):
                        continue
                    if l.startswith("**") or l.startswith("|"):
                        break
                    if l.startswith(">"):
                        continue
                    desc_lines.append(l)
                description = " ".join(desc_lines).strip()

            # Track overload disambiguator
            path_key = f"{file_path}::{heading_path}::{api_name}"
            overload_idx = overload_counters.get(path_key, 0) + 1
            overload_counters[path_key] = overload_idx
            disambiguator = f"overload_{overload_idx}" if overload_idx > 1 else ""

            chunk_id = DocChunk.generate_id(self.version, file_path, heading_path, api_name, disambiguator)

            prefix = "#" * level
            raw_chunk = f"{prefix} {heading_text}\n\n{body}"

            chunk = DocChunk(
                chunk_id=chunk_id,
                version=self.version,
                kit=kit,
                subsystem=subsystem,
                module=module,
                file_path=file_path,
                file_title=file_title,
                heading_level=level,
                heading_text=clean_heading,
                parent_title=parent_title,
                heading_path=heading_path,
                category=category,
                api_name=api_name,
                full_name=full_name,
                signature=signature,
                since=since,
                deprecated=deprecated,
                permission=permission,
                syscap=syscap,
                atomic_service=atomic_service,
                description=description,
                parameters_summary=params_summary,
                return_summary=return_summary,
                error_codes_summary=error_summary,
                example=example_code,
                raw_content=raw_chunk,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            chunks.append(chunk)

            # Property Table extraction: if section contains a table of properties/member variables/constants
            prop_chunks = self._extract_property_chunks(
                body=body,
                parent_chunk=chunk,
                file_path=file_path,
                file_title=file_title,
                module=module,
                kit=kit,
                subsystem=subsystem,
                syscap=syscap,
                container_name=container_name,
                prop_counters=prop_counters,
            )
            chunks.extend(prop_chunks)

            # Error Code Table extraction: if section contains a table of error codes
            err_chunks = self._extract_error_code_chunks(
                body=body,
                parent_chunk=chunk,
                file_path=file_path,
                file_title=file_title,
                module=module,
                kit=kit,
                subsystem=subsystem,
                err_counters=err_counters,
            )
            chunks.extend(err_chunks)

        return chunks

    def _extract_property_chunks(
        self,
        body: str,
        parent_chunk: DocChunk,
        file_path: str,
        file_title: str,
        module: str,
        kit: str,
        subsystem: str,
        syscap: str,
        container_name: str = "",
        prop_counters: Optional[Dict[str, int]] = None,
    ) -> List[DocChunk]:
        """Extract individual properties from markdown tables in interfaces/options/enums/structs/constants."""
        # Never extract properties from method parameter lists
        if parent_chunk.category in ["method", "function"] and parent_chunk.heading_text not in ["属性", "常量", "成员变量"]:
            return []

        # Only parse tables for interfaces, classes, enums, structs, options, constants, or sections named 属性/常量/成员变量
        is_prop_candidate = (
            parent_chunk.category in ["interface", "class", "enum", "struct", "section", "constant"]
            or parent_chunk.heading_text in ["属性", "常量", "成员变量", "Constants"]
            or any(parent_chunk.heading_text.endswith(s) for s in ["Options", "Params", "Config", "Cert", "Result", "Info"])
        )
        if not is_prop_candidate:
            return []

        lines = body.splitlines()
        table_lines = [l.strip() for l in lines if l.strip().startswith("|")]
        if len(table_lines) < 3:
            return []

        headers = split_table_row(table_lines[0])
        header_map = {}
        for idx, h in enumerate(headers):
            h_clean = re.sub(r"<.*?>", "", h).strip()
            # Do NOT include "参数名" - parameter tables belong to methods/functions, not properties
            if h_clean in ["名称", "属性", "变量名", "常量", "字段", "成员变量", "枚举项", "枚举值"]:
                header_map["name"] = idx
            elif h_clean in ["类型", "数据类型"]:
                header_map["type"] = idx
            elif h_clean in ["说明", "描述"]:
                header_map["desc"] = idx
            elif h_clean in ["可选", "必填"]:
                header_map["optional"] = idx

        if "name" not in header_map or "desc" not in header_map:
            return []

        property_chunks: List[DocChunk] = []
        # Target parent name: never let parent_name be "属性", "常量" or "成员变量"
        if parent_chunk.heading_text in ["属性", "常量", "成员变量"]:
            parent_name = parent_chunk.parent_title or container_name or ""
        elif parent_chunk.category == "constant" and parent_chunk.heading_level == 1:
            parent_name = ""
        else:
            parent_name = parent_chunk.api_name

        is_c_table = "type" not in header_map
        if prop_counters is None:
            prop_counters = {}

        for row in table_lines[2:]:
            cols = split_table_row(row)
            if len(cols) <= max(header_map.values()):
                continue

            raw_name = cols[header_map["name"]]
            if not raw_name or raw_name.startswith("---") or raw_name == "-":
                continue

            clean_name, since, deprecated = clean_sup(raw_name)

            if is_c_table:
                parsed_name, prop_type = parse_c_decl(clean_name)
                clean_name = parsed_name
            else:
                # Remove markdown links like [foo](#foo)
                link_m = re.match(r"\[(.*?)\]\(.*?\)", clean_name)
                if link_m:
                    clean_name = link_m.group(1).strip()
                prop_type = cols[header_map["type"]] if "type" in header_map and len(cols) > header_map["type"] else ""

            if not clean_name:
                continue

            desc = cols[header_map["desc"]] if len(cols) > header_map["desc"] else ""

            # Check atomic service in description
            atomic_service = ""
            atom_m = re.search(r"原子化服务API[：:]\s*(.+?)(?:<br|。|\Z)", desc)
            if atom_m:
                atomic_service = atom_m.group(1).strip().strip("*| \t")

            # Check since in description if not in name
            if not since:
                since_m = re.search(r"自\s*API\s*(\d+\+?)开始支持", desc)
                if since_m:
                    since = since_m.group(1)

            # Check syscap in description if not in parent
            row_meta = extract_metadata_from_text(desc)
            prop_syscap = row_meta["syscap"] or syscap or parent_chunk.syscap
            if row_meta["since"] and not since:
                since = row_meta["since"]
            if row_meta["deprecated"]:
                deprecated = True

            full_name = f"{module}.{parent_name}.{clean_name}" if parent_name else f"{module}.{clean_name}" if module else clean_name
            heading_path = f"{file_title} > {parent_name} > {clean_name}" if parent_name else f"{file_title} > {clean_name}"
            signature = f"{clean_name}: {prop_type}" if prop_type else clean_name

            raw_row = f"| {' | '.join(cols)} |"

            prop_category = "constant" if (parent_chunk.category == "constant" or parent_chunk.heading_text in ["常量", "Constants"]) else "property"
            disambig_prefix = "const" if prop_category == "constant" else "prop"

            path_key = f"{file_path}::{heading_path}::{clean_name}::{disambig_prefix}"
            prop_counters[path_key] = prop_counters.get(path_key, 0) + 1
            cnt = prop_counters[path_key]
            disambiguator = f"{disambig_prefix}_{cnt}" if cnt > 1 else disambig_prefix

            chunk_id = DocChunk.generate_id(self.version, file_path, heading_path, clean_name, disambiguator)

            prop_chunk = DocChunk(
                chunk_id=chunk_id,
                version=self.version,
                kit=kit,
                subsystem=subsystem,
                module=module,
                file_path=file_path,
                file_title=file_title,
                heading_level=parent_chunk.heading_level + 1,
                heading_text=clean_name,
                parent_title=parent_name,
                heading_path=heading_path,
                category=prop_category,
                api_name=clean_name,
                full_name=full_name,
                signature=signature,
                since=since or parent_chunk.since,
                deprecated=deprecated or parent_chunk.deprecated,
                permission=parent_chunk.permission,
                syscap=prop_syscap,
                atomic_service=atomic_service or parent_chunk.atomic_service,
                description=desc,
                parameters_summary="",
                return_summary=prop_type,
                error_codes_summary="",
                example="",
                raw_content=raw_row,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            property_chunks.append(prop_chunk)

        return property_chunks

    def _extract_error_code_chunks(
        self,
        body: str,
        parent_chunk: DocChunk,
        file_path: str,
        file_title: str,
        module: str,
        kit: str,
        subsystem: str,
        err_counters: Optional[Dict[str, int]] = None,
    ) -> List[DocChunk]:
        """Extract individual error codes from markdown tables."""
        if parent_chunk.category != "error_code" and "错误码" not in parent_chunk.heading_text and "ErrorCode" not in parent_chunk.heading_text:
            return []

        lines = body.splitlines()
        table_lines = [l.strip() for l in lines if l.strip().startswith("|")]
        if len(table_lines) < 3:
            return []

        headers = split_table_row(table_lines[0])
        header_map = {}
        for idx, h in enumerate(headers):
            h_clean = re.sub(r"<.*?>", "", h).strip()
            if h_clean in ["错误码数值", "错误码ID", "错误码", "Error Code", "Code"]:
                header_map["code"] = idx
            elif h_clean in ["错误码定义", "错误名称", "定义", "Error Name", "Name"]:
                header_map["name"] = idx
            elif h_clean in ["错误码描述", "错误信息", "说明", "描述", "Error Message", "Description"]:
                header_map["desc"] = idx

        if "code" not in header_map and "name" not in header_map:
            return []
        if "desc" not in header_map:
            return []

        if err_counters is None:
            err_counters = {}

        error_chunks: List[DocChunk] = []
        parent_name = parent_chunk.api_name or parent_chunk.heading_text or "错误码"

        for row in table_lines[2:]:
            cols = split_table_row(row)
            if len(cols) <= max(header_map.values()):
                continue

            code_val = cols[header_map["code"]] if "code" in header_map and len(cols) > header_map["code"] else ""
            code_name = cols[header_map["name"]] if "name" in header_map and len(cols) > header_map["name"] else ""
            desc = cols[header_map["desc"]] if len(cols) > header_map["desc"] else ""

            if not code_val and not code_name:
                continue
            if code_val.startswith("---") or code_name.startswith("---"):
                continue

            api_name = code_name if code_name else code_val
            heading_text = f"{code_val} {code_name}".strip() if code_val and code_name else (code_name or code_val)
            heading_path = f"{file_title} > {heading_text}"
            full_name = f"{parent_name}.{api_name}" if parent_name else api_name
            signature = f"{code_val}: {code_name}" if code_val and code_name else heading_text
            raw_row = f"| {' | '.join(cols)} |"

            base_disambig = f"err_{code_val}" if code_val else f"err_{api_name}"
            err_key = f"{file_path}::{heading_path}::{api_name}::{base_disambig}"
            err_counters[err_key] = err_counters.get(err_key, 0) + 1
            cnt = err_counters[err_key]
            disambiguator = f"{base_disambig}_{cnt}" if cnt > 1 else base_disambig

            chunk_id = DocChunk.generate_id(self.version, file_path, heading_path, api_name, disambiguator)

            err_chunk = DocChunk(
                chunk_id=chunk_id,
                version=self.version,
                kit=kit,
                subsystem=subsystem,
                module=module,
                file_path=file_path,
                file_title=file_title,
                heading_level=parent_chunk.heading_level + 1,
                heading_text=heading_text,
                parent_title=parent_name,
                heading_path=heading_path,
                category="error_code",
                api_name=api_name,
                full_name=full_name,
                signature=signature,
                since=parent_chunk.since,
                deprecated=parent_chunk.deprecated,
                permission=parent_chunk.permission,
                syscap=parent_chunk.syscap,
                atomic_service=parent_chunk.atomic_service,
                description=desc,
                parameters_summary="",
                return_summary="",
                error_codes_summary="",
                example="",
                raw_content=raw_row,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            error_chunks.append(err_chunk)

        return error_chunks
