#!/usr/bin/env python3
"""Comprehensive test suite for OpenHarmony Official Document RAG system.

Tests:
1. DocParser Unit Tests:
   - clean_sup: version & deprecation superscripts and text tags
   - split_table_row: escaped pipes
   - parse_c_decl: C-style variable and pointer declarations
   - extract_metadata_from_text: supports colon inside and outside asterisks
   - parse_sample_doc: function, interface, property, permissions, syscap, examples
   - parser_empty_and_minimal_inputs: empty or blank doc handling
   - dedicated_container_doc: Interface/Class file (AudioRenderer.md) container chunk & method parent assignment
   - c_api_struct_and_header: C-API member variables & header function descriptions
2. DocIndexer and DocRetriever Integration Tests:
   - database_stats: chunk count & version distribution
   - search_by_name_exact: createHttp, createHttp() with parentheses, http.createHttp dotted
   - search_by_name_property: HttpRequestOptions.usingProxy, AudioRenderer.state
   - search_by_keyword: Chinese BM25, English BM25, and special characters/operators (AND/OR/NOT/quotes/brackets)
   - search_by_condition: permissions, deprecation
   - compare_api_new_in_v6_1: HttpInterceptor version detection
   - compare_api_property_additions: HttpRequestOptions new properties in 6.1
   - compare_api_exact_vs_substring: createHttp does not match createHttpResponseCache
   - search_non_existent_api: graceful empty result handling
"""

import os
import shutil
import tempfile
import unittest
from doc_rag.models import DocChunk
from doc_rag.parser import DocParser, clean_sup, split_table_row, parse_c_decl, extract_metadata_from_text
from doc_rag.indexer import DocIndexer, tokenize_for_search
from doc_rag.retriever import DocRetriever, parse_api_query


class TestDocParser(unittest.TestCase):
    def test_clean_sup(self):
        # Normal version superscript
        text, since, dep = clean_sup("requestInStream<sup>10+</sup>")
        self.assertEqual(text, "requestInStream")
        self.assertEqual(since, "10+")
        self.assertFalse(dep)

        # Deprecated superscript
        text, since, dep = clean_sup("on('headerReceive')<sup>(deprecated)</sup>")
        self.assertEqual(text, "on('headerReceive')")
        self.assertTrue(dep)

        # Version and deprecated combined
        text, since, dep = clean_sup("oldMethod<sup>8+(deprecated)</sup>")
        self.assertEqual(text, "oldMethod")
        self.assertEqual(since, "8+")
        self.assertTrue(dep)

        # Text deprecation
        text, since, dep = clean_sup("legacyApi(deprecated)")
        self.assertEqual(text, "legacyApi")
        self.assertTrue(dep)

    def test_split_table_row_escaped_pipe(self):
        row = r"| fieldName | string \| Object \| ArrayBuffer | 否 | 是 | 描述说明 |"
        cols = split_table_row(row)
        self.assertEqual(len(cols), 5)
        self.assertEqual(cols[0], "fieldName")
        self.assertEqual(cols[1], "string | Object | ArrayBuffer")
        self.assertEqual(cols[4], "描述说明")

    def test_parse_c_decl(self):
        # Basic variable
        name, ptype = parse_c_decl("uint32_t priority")
        self.assertEqual(name, "priority")
        self.assertEqual(ptype, "uint32_t")

        # Pointer variable
        name, ptype = parse_c_decl("const char *method")
        self.assertEqual(name, "method")
        self.assertEqual(ptype, "const char *")

        # Markdown linked type with pointer
        name, ptype = parse_c_decl("[Http_Headers](capi-netstack-http-headers.md) *headers")
        self.assertEqual(name, "headers")
        self.assertEqual(ptype, "Http_Headers *")

    def test_extract_metadata_colon_inside_and_outside(self):
        # Colon inside bold asterisks
        text_inside = """
**需要权限：** ohos.permission.INTERNET
**系统能力：** SystemCapability.Test.SysCap
**起始版本：** 11+
**原子化服务API：** 从API version 11开始支持
**废弃：** 自API version 12开始废弃
"""
        meta1 = extract_metadata_from_text(text_inside)
        self.assertEqual(meta1["permission"], "ohos.permission.INTERNET")
        self.assertEqual(meta1["syscap"], "SystemCapability.Test.SysCap")
        self.assertEqual(meta1["since"], "11+")
        self.assertIn("11", meta1["atomic_service"])
        self.assertTrue(meta1["deprecated"])

        # Colon outside bold asterisks
        text_outside = """
**需要权限**：ohos.permission.LOCATION
**系统能力**：SystemCapability.Location
**起始版本**：9
"""
        meta2 = extract_metadata_from_text(text_outside)
        self.assertEqual(meta2["permission"], "ohos.permission.LOCATION")
        self.assertEqual(meta2["syscap"], "SystemCapability.Location")
        self.assertEqual(meta2["since"], "9")

    def test_parse_sample_doc(self):
        sample_md = """# @ohos.net.sample (示例模块)

<!--Kit: Network Kit-->
<!--Subsystem: Communication-->

本模块提供示例功能。

## 导入模块

```ts
import { sample } from '@kit.NetworkKit';
```

## sample.doAction

doAction(param: string): void

执行特定操作。

**需要权限：** ohos.permission.INTERNET

**系统能力：** SystemCapability.Communication.NetStack

**原子化服务API：** 从API version 11开始，该接口支持在原子化服务中使用。

**参数：**

| 参数名 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| param | string | 是 | 操作参数。 |

**返回值：**

| 类型 | 说明 |
| :--- | :--- |
| void | 无返回值。 |

**错误码：**

| 错误码ID | 错误信息 |
| :--- | :--- |
| 401 | Parameter error. |

**示例：**

```ts
sample.doAction('test');
```

## SampleOptions

操作配置参数。

| 名称 | 类型 | 只读 | 可选 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| timeout<sup>9+</sup> | number | 否 | 是 | 超时时间。 |
| enableTls<sup>12+</sup> | boolean | 否 | 是 | 是否启用TLS加密。 |
"""
        parser = DocParser(version="vTest")
        chunks = parser.parse_file_content("test/sample.md", sample_md)

        # Check total chunks (overview + 导入模块 + doAction + SampleOptions + timeout prop + enableTls prop)
        self.assertGreater(len(chunks), 4)

        # Find doAction
        action_chunks = [c for c in chunks if c.api_name == "doAction"]
        self.assertEqual(len(action_chunks), 1)
        action = action_chunks[0]
        self.assertEqual(action.category, "function")
        self.assertEqual(action.signature, "doAction(param: string): void")
        self.assertEqual(action.permission, "ohos.permission.INTERNET")
        self.assertEqual(action.syscap, "SystemCapability.Communication.NetStack")
        self.assertIn("API version 11", action.atomic_service)
        self.assertIn("param", action.parameters_summary)
        self.assertIn("void", action.return_summary)
        self.assertIn("401", action.error_codes_summary)
        self.assertIn("doAction('test')", action.example)

        # Find timeout property
        timeout_chunks = [c for c in chunks if c.api_name == "timeout"]
        self.assertEqual(len(timeout_chunks), 1)
        prop = timeout_chunks[0]
        self.assertEqual(prop.category, "property")
        self.assertEqual(prop.parent_title, "SampleOptions")
        self.assertEqual(prop.since, "9+")
        self.assertEqual(prop.signature, "timeout: number")

    def test_parser_empty_and_minimal_inputs(self):
        parser = DocParser(version="vTest")
        self.assertEqual(parser.parse_file_content("empty.md", ""), [])
        self.assertEqual(parser.parse_file_content("blank.md", "   \n\n  "), [])

        one_line = parser.parse_file_content("one.md", "Just a line of text without headings.")
        self.assertEqual(len(one_line), 0)

    def test_dedicated_container_audio_renderer(self):
        audio_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-audio-kit/arkts-apis-audio-AudioRenderer.md"
        if not os.path.exists(audio_path):
            self.skipTest("AudioRenderer doc file not found")

        with open(audio_path, "r", encoding="utf-8") as fp:
            content = fp.read()

        parser = DocParser(version="v6.0.0.1-Release")
        chunks = parser.parse_file_content("apis-audio-kit/arkts-apis-audio-AudioRenderer.md", content)

        # 1. Container chunk should exist
        container_chunks = [c for c in chunks if c.api_name == "AudioRenderer" and c.category == "interface"]
        self.assertEqual(len(container_chunks), 1)

        # 2. Methods should have parent_title = AudioRenderer
        methods = [c for c in chunks if c.category == "method" and c.parent_title == "AudioRenderer"]
        self.assertGreater(len(methods), 20)

        # 3. Property state should have parent_title = AudioRenderer
        state_prop = [c for c in chunks if c.api_name == "state" and c.parent_title == "AudioRenderer"]
        self.assertEqual(len(state_prop), 1)
        self.assertEqual(state_prop[0].category, "property")

        # 4. Method parameters (like callback) must NOT be extracted as properties
        callback_props = [c for c in chunks if c.api_name == "callback" and c.parent_title == "getRendererInfo"]
        self.assertEqual(len(callback_props), 0)

    def test_c_api_struct_and_header(self):
        # 1. C-API struct
        struct_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/capi-netstack-http-requestoptions.md"
        if os.path.exists(struct_path):
            with open(struct_path, "r", encoding="utf-8") as fp:
                c_content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("capi-netstack-http-requestoptions.md", c_content)
            props = [c for c in chunks if c.category == "property" and c.parent_title == "Http_RequestOptions"]
            self.assertGreater(len(props), 5)
            prop_names = [p.api_name for p in props]
            self.assertIn("method", prop_names)
            self.assertIn("priority", prop_names)

        # 2. C-API header function
        header_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/capi-net-http-h.md"
        if os.path.exists(header_path):
            with open(header_path, "r", encoding="utf-8") as fp:
                h_content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("capi-net-http-h.md", h_content)
            func = [c for c in chunks if c.api_name == "OH_Http_CreateHeaders"][0]
            self.assertTrue(bool(func.description))
            self.assertTrue(bool(func.return_summary))

    def test_property_primary_key_collision_fixed(self):
        # 1. js-apis-audio.md: AudioRenderer.state vs AudioCapturer.state
        audio_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-audio-kit/js-apis-audio.md"
        if os.path.exists(audio_path):
            with open(audio_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-audio-kit/js-apis-audio.md", content)
            state_chunks = [c for c in chunks if c.api_name == "state"]
            self.assertEqual(len(state_chunks), 2)
            parents = set(c.parent_title for c in state_chunks)
            self.assertEqual(parents, {"AudioRenderer", "AudioCapturer"})
            chunk_ids = set(c.chunk_id for c in state_chunks)
            self.assertEqual(len(chunk_ids), 2, "State property chunk IDs must not collide")

        # 2. js-apis-socket.md: TCPSocketConnection.clientId vs LocalSocketConnection.clientId vs TLSSocketConnection.clientId
        socket_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/js-apis-socket.md"
        if os.path.exists(socket_path):
            with open(socket_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-network-kit/js-apis-socket.md", content)
            client_id_chunks = [c for c in chunks if c.api_name == "clientId"]
            self.assertEqual(len(client_id_chunks), 3)
            parents = set(c.parent_title for c in client_id_chunks)
            self.assertEqual(parents, {"TCPSocketConnection", "LocalSocketConnection", "TLSSocketConnection"})
            chunk_ids = set(c.chunk_id for c in client_id_chunks)
            self.assertEqual(len(chunk_ids), 3, "clientId property chunk IDs must not collide")

        # 3. js-apis-net-connection.md: NetConnectionPropertyInfo.netHandle vs NetBlockStatusInfo.netHandle
        conn_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/js-apis-net-connection.md"
        if os.path.exists(conn_path):
            with open(conn_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-network-kit/js-apis-net-connection.md", content)
            nethandle_props = [c for c in chunks if c.api_name == "netHandle" and c.category == "property"]
            self.assertGreaterEqual(len(nethandle_props), 2)
            parents = set(c.parent_title for c in nethandle_props)
            self.assertIn("NetConnectionPropertyInfo", parents)
            self.assertIn("NetBlockStatusInfo", parents)
            chunk_ids = set(c.chunk_id for c in nethandle_props)
            self.assertEqual(len(chunk_ids), len(nethandle_props), "netHandle property chunk IDs must not collide")

    def test_zero_chunk_docs_parsing_fixed(self):
        # 1. Audio constants doc (no H2)
        const_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-audio-kit/arkts-apis-audio-c.md"
        if os.path.exists(const_path):
            with open(const_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-audio-kit/arkts-apis-audio-c.md", content)
            self.assertGreaterEqual(len(chunks), 3)
            names = [c.api_name for c in chunks]
            self.assertIn("DEFAULT_VOLUME_GROUP_ID", names)
            self.assertIn("DEFAULT_INTERRUPT_GROUP_ID", names)

        # 2. Kernel error codes doc (no H2)
        err_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/errorcode-kernel.md"
        if os.path.exists(err_path):
            with open(err_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-network-kit/errorcode-kernel.md", content)
            self.assertGreaterEqual(len(chunks), 60)
            names = [c.api_name for c in chunks]
            self.assertIn("EPERM", names)

        # 3. Readme / navigation doc (no H2)
        readme_path = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference/apis-network-kit/Readme-CN.md"
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as fp:
                content = fp.read()
            parser = DocParser(version="v6.0.0.1-Release")
            chunks = parser.parse_file_content("apis-network-kit/Readme-CN.md", content)
            self.assertEqual(len(chunks), 1)
            self.assertEqual(chunks[0].category, "overview")

    def test_h3_class_h4_property_hierarchy_and_collision_synthetic(self):
        sample_md = """# @test.module (测试模块)
## TestNamespace
### FirstClass
#### 属性
| 名称 | 类型 | 可选 | 说明 |
| -- | -- | -- | -- |
| id | string | 否 | FirstClass ID |
### SecondClass
#### 属性
| 名称 | 类型 | 可选 | 说明 |
| -- | -- | -- | -- |
| id | string | 否 | SecondClass ID |
"""
        parser = DocParser(version="vTest")
        chunks = parser.parse_file_content("test/h3_h4.md", sample_md)
        id_chunks = [c for c in chunks if c.api_name == "id"]
        self.assertEqual(len(id_chunks), 2)
        parents = {c.parent_title for c in id_chunks}
        self.assertEqual(parents, {"FirstClass", "SecondClass"})
        self.assertNotEqual(id_chunks[0].chunk_id, id_chunks[1].chunk_id)

    def test_multiple_property_tables_same_property_name_synthetic(self):
        sample_md = """# @test.camera (测试相机)
## CameraFormat
| 名称 | 值 | 说明 |
| -- | -- | -- |
| FORMAT_RAW | 1 | 格式1 |
## CameraFormat
| 名称 | 值 | 说明 |
| -- | -- | -- |
| FORMAT_RAW | 1 | 格式1系统说明 |
"""
        parser = DocParser(version="vTest")
        chunks = parser.parse_file_content("test/multi_table.md", sample_md)
        raw_chunks = [c for c in chunks if c.api_name == "FORMAT_RAW"]
        self.assertEqual(len(raw_chunks), 2)
        self.assertNotEqual(raw_chunks[0].chunk_id, raw_chunks[1].chunk_id)

    def test_clean_sup_markdown_decorations(self):
        clean, since, dep = clean_sup("**属性**")
        self.assertEqual(clean, "属性")
        clean2, _, _ = clean_sup("[MyLink](link.md)")
        self.assertEqual(clean2, "MyLink")


class TestDocIndexerAndRetriever(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.temp_dir, "test_doc_rag.db")
        cls.indexer = DocIndexer(db_path=cls.db_path)

        # Ingest v6.0.0.1-Release network and audio kit docs
        v6_dir = "official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference"
        if os.path.exists(v6_dir):
            cls.indexer.ingest_directory(
                doc_dir=v6_dir,
                version="v6.0.0.1-Release",
                kit_filter=["apis-network-kit", "apis-audio-kit"],
            )

        # Ingest v6.1-LTS network kit docs from zip
        v6_1_zip = "official/docs-OpenHarmony-v6.1-LTS-zh-cn-application-dev-reference.zip"
        if os.path.exists(v6_1_zip):
            cls.indexer.ingest_zip(
                zip_path=v6_1_zip,
                version="v6.1-LTS",
                kit_filter=["apis-network-kit"],
            )

        cls.retriever = DocRetriever(indexer=cls.indexer)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_database_stats(self):
        stats = self.indexer.get_stats()
        self.assertGreater(stats["total_chunks"], 1000)
        self.assertIn("v6.0.0.1-Release", stats["by_version"])
        self.assertIn("v6.1-LTS", stats["by_version"])
        self.assertGreater(stats["distinct_apis"], 500)

    def test_search_by_name_exact(self):
        # 1. Search for createHttp
        results = self.retriever.search_by_name("createHttp", version="v6.0.0.1-Release")
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertEqual(top.chunk.api_name, "createHttp")
        self.assertEqual(top.chunk.signature, "createHttp(): HttpRequest")
        self.assertEqual(top.chunk.version, "v6.0.0.1-Release")

        # 2. Search with trailing parentheses: createHttp()
        res_paren = self.retriever.search_by_name("createHttp()", exact=True, version="v6.0.0.1-Release")
        self.assertGreater(len(res_paren), 0)
        self.assertEqual(res_paren[0].chunk.api_name, "createHttp")

        # 3. Search with module prefix: http.createHttp
        res_dotted = self.retriever.search_by_name("http.createHttp", exact=True, version="v6.0.0.1-Release")
        self.assertGreater(len(res_dotted), 0)
        self.assertEqual(res_dotted[0].chunk.api_name, "createHttp")

        # 4. Search for HttpRequest.request
        req_results = self.retriever.search_by_name("HttpRequest.request", version="v6.0.0.1-Release")
        self.assertGreater(len(req_results), 0)
        self.assertTrue(any("request" in r.chunk.api_name for r in req_results))

    def test_search_by_name_property(self):
        # 1. Search for property usingProxy
        results = self.retriever.search_by_name("usingProxy", version="v6.0.0.1-Release")
        self.assertGreater(len(results), 0)
        top = results[0]
        self.assertEqual(top.chunk.api_name, "usingProxy")
        self.assertEqual(top.chunk.parent_title, "HttpRequestOptions")
        self.assertEqual(top.chunk.since, "10+")

        # 2. Search for AudioRenderer.state
        state_res = self.retriever.search_by_name("AudioRenderer.state", exact=True, version="v6.0.0.1-Release")
        self.assertGreater(len(state_res), 0)
        self.assertEqual(state_res[0].chunk.api_name, "state")
        self.assertEqual(state_res[0].chunk.parent_title, "AudioRenderer")

    def test_search_by_keyword(self):
        # 1. Search Chinese keyword: 证书锁定
        results = self.retriever.search_by_keyword("证书锁定")
        self.assertGreater(len(results), 0)
        self.assertTrue(any("certificatePinning" in r.chunk.api_name or "certificatepinning" in r.chunk.file_path for r in results))

        # 2. Search English keyword: brotli
        results_brotli = self.retriever.search_by_keyword("brotli")
        self.assertGreater(len(results_brotli), 0)

        # 3. Search HTTP请求
        results_http = self.retriever.search_by_keyword("HTTP请求")
        self.assertGreater(len(results_http), 0)

    def test_fts_special_characters_and_operators(self):
        # Operators like AND, OR, NOT, NEAR must not raise sqlite3.OperationalError
        res_ops = self.retriever.search_by_keyword("AND OR NOT NEAR")
        self.assertIsInstance(res_ops, list)

        # Unbalanced quotes
        res_quotes = self.retriever.search_by_keyword('"""')
        self.assertIsInstance(res_quotes, list)

        # Parentheses and special symbols
        res_sym = self.retriever.search_by_keyword("((:::*:::))")
        self.assertIsInstance(res_sym, list)

    def test_search_by_condition(self):
        # Filter by permission
        results = self.retriever.search_by_condition(
            permission="ohos.permission.INTERNET",
            version="v6.0.0.1-Release",
            limit=10,
        )
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("ohos.permission.INTERNET", r.chunk.permission)

        # Filter by deprecated
        results_dep = self.retriever.search_by_condition(
            deprecated=True,
            version="v6.0.0.1-Release",
            limit=10,
        )
        self.assertGreater(len(results_dep), 0)
        for r in results_dep:
            self.assertTrue(r.chunk.deprecated)

    def test_compare_api_new_in_v6_1(self):
        # HttpInterceptor is added in v6.1-LTS, not in v6.0.0.1-Release
        comp = self.retriever.compare_api_across_versions("HttpInterceptor")
        self.assertIn("v6.0.0.1-Release", comp.missing_versions)
        self.assertIn("v6.1-LTS", comp.found_versions)
        self.assertEqual(comp.differences["version_status"]["v6.0.0.1-Release"], "NOT_FOUND")
        self.assertEqual(comp.differences["version_status"]["v6.1-LTS"], "AVAILABLE")
        self.assertTrue(any("首次引入" in ch for ch in comp.differences["changes_detected"]))

    def test_compare_api_property_additions(self):
        # HttpRequestOptions has new properties in v6.1-LTS (maxRedirects, sniHostName, pathPreference, customMethod)
        comp = self.retriever.compare_api_across_versions("HttpRequestOptions")
        self.assertIn("v6.0.0.1-Release", comp.found_versions)
        self.assertIn("v6.1-LTS", comp.found_versions)
        self.assertTrue(any("新增属性" in ch for ch in comp.differences["changes_detected"]))
        added_props = [ch for ch in comp.differences["changes_detected"] if "新增属性" in ch][0]
        self.assertIn("maxRedirects", added_props)
        self.assertIn("sniHostName", added_props)

    def test_compare_api_exact_vs_substring(self):
        # Comparing createHttp must ONLY match createHttp, never createHttpResponseCache
        comp = self.retriever.compare_api_across_versions("createHttp")
        v6_chunks = comp.by_version["v6.0.0.1-Release"]
        api_names = set(c.api_name for c in v6_chunks)
        self.assertEqual(api_names, {"createHttp"})
        self.assertNotIn("createHttpResponseCache", api_names)

    def test_search_non_existent_api(self):
        results = self.retriever.search_by_name("NonExistentFakeAPI12345")
        self.assertEqual(len(results), 0)

        comp = self.retriever.compare_api_across_versions("NonExistentFakeAPI12345")
        self.assertEqual(len(comp.found_versions), 0)
        self.assertEqual(len(comp.missing_versions), len(comp.target_versions))

    def test_database_stats_and_fts_alignment(self):
        stats = self.indexer.get_stats()
        self.assertGreater(stats["total_chunks"], 1000)
        self.assertEqual(stats["total_chunks"], stats["total_fts"], "doc_chunks count must strictly match doc_chunks_fts count")

        # Verify zero duplicate chunk IDs in FTS virtual table
        conn = self.indexer.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT chunk_id, COUNT(*) FROM doc_chunks_fts GROUP BY chunk_id HAVING COUNT(*) > 1;")
            fts_dups = cur.fetchall()
            self.assertEqual(len(fts_dups), 0, f"No duplicate chunk IDs allowed in FTS, found: {fts_dups}")
        finally:
            conn.close()

    def test_search_tcp_no_tls_mismatch(self):
        # Searching TCPSocketServer should return TCP connection clientId, never TLSSocketServer description
        kw_results = self.retriever.search_by_keyword("TCPSocketServer", version="v6.0.0.1-Release")
        self.assertGreater(len(kw_results), 0)
        client_matches = [r for r in kw_results if r.chunk.api_name == "clientId"]
        if client_matches:
            top_client = client_matches[0]
            self.assertEqual(top_client.chunk.parent_title, "TCPSocketConnection")
            self.assertIn("TCPSocketServer", top_client.chunk.description)
            self.assertNotIn("TLSSocketServer", top_client.chunk.description)

    def test_independent_audio_state_retrieval(self):
        # AudioRenderer.state and AudioCapturer.state must both exist and be independently retrievable
        res_render = self.retriever.search_by_name("AudioRenderer.state", exact=True, version="v6.0.0.1-Release")
        self.assertGreater(len(res_render), 0)
        self.assertEqual(res_render[0].chunk.parent_title, "AudioRenderer")

        res_capt = self.retriever.search_by_name("AudioCapturer.state", exact=True, version="v6.0.0.1-Release")
        self.assertGreater(len(res_capt), 0)
        self.assertEqual(res_capt[0].chunk.parent_title, "AudioCapturer")

    def test_zero_chunk_docs_retrieval(self):
        # Audio constants retrievable
        res_const = self.retriever.search_by_name("DEFAULT_VOLUME_GROUP_ID", version="v6.0.0.1-Release")
        self.assertGreater(len(res_const), 0)
        self.assertEqual(res_const[0].chunk.api_name, "DEFAULT_VOLUME_GROUP_ID")

        # Kernel error code retrievable
        res_err = self.retriever.search_by_name("EPERM", version="v6.0.0.1-Release")
        self.assertGreater(len(res_err), 0)
        self.assertEqual(res_err[0].chunk.api_name, "EPERM")

    def test_empty_and_whitespace_query_handling(self):
        # Empty and whitespace searches must safely return empty results, never leak arbitrary database rows
        self.assertEqual(self.retriever.search_by_name(""), [])
        self.assertEqual(self.retriever.search_by_name("   "), [])
        self.assertEqual(self.retriever.search_by_keyword(""), [])
        self.assertEqual(self.retriever.search_by_keyword("   "), [])

        comp = self.retriever.compare_api_across_versions("")
        self.assertEqual(len(comp.found_versions), 0)
        self.assertEqual(comp.api_name, "")

    def test_fts_orphan_cleanup_and_sync(self):
        # Insert a deliberate orphan record directly into doc_chunks_fts
        conn = self.indexer.get_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO doc_chunks_fts (chunk_id, api_name, parent_title, full_name, search_tokens) "
                    "VALUES ('orphan_test_123', 'orphan_api', '', '', 'orphan_token');"
                )
        finally:
            conn.close()

        # Check orphan exists in FTS
        stats = self.indexer.get_stats()
        self.assertEqual(stats["total_fts"], stats["total_chunks"] + 1)

        # Call sync_fts_index() and confirm orphan is purged and counts match 100%
        self.indexer.sync_fts_index()
        stats_synced = self.indexer.get_stats()
        self.assertEqual(stats_synced["total_fts"], stats_synced["total_chunks"])


if __name__ == "__main__":
    unittest.main()
