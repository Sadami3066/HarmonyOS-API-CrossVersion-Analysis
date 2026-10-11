# 工作计划与交接

最后更新：2026-10-09（Asia/Shanghai）。技术检查基线：35e72f782fd3c4e618b0b904b9f669f5b3f5dd2c。

## 项目目标

制作用户需求驱动的 API 查询推荐工具：AI 结合 RAG 库检索，推荐一个或多个 API，说明差异、理由及适用条件。目标和现状依据见 [docs/project-goal.md](docs/project-goal.md)。任务完成并验证后勾选对应步骤，紧邻记录实际效果和证据；自查完成与验收确认分开。

## 当前概况

源码、JSON、导入、查询、报告和网站入口已存在，见 [README](README.md) 与[数据规范](docs/data-contract.md)。
- 默认分支 master；JSON 目录 API、API4.1、API5.0、API5.1、API6.0，API 来源待确认。
- 提取存在个人 Windows 路径；_run_import.py 会清空目标默认数据库。
- 仓库尚无统一 Python/Neo4j 版本或依赖锁定。可用环境的实际版本待成员提供。
- 2026-10-03 核对 19 个文件（主要脚本、文档、HTML及各数据目录一个 JSON），样本 UTF-8 字节长度与 blob 大小一致，无 BOM、LF；未遍历全部 JSON。
- 用户提供部署地址 http://47.114.40.66:5000/；访问工具未成功读取，网站状态、部署提交及服务器版本未验证。
- 四人分工和本地执行进度尚未核实，不虚构任务指派或历史验收。

## 更新规则

成员和 AI 均可操作。**有新的进展，必须第一时间记录入 workplan.md。** 详见 [CONTRIBUTING](CONTRIBUTING.md) 与 [AGENTS](AGENTS.md)。

状态：待开始／进行中／阻塞／待验收／已验收；只在明确确认后标已验收。按任务 ID 更新，保留决定和进展，不覆盖队友记录。

## DOC-001 协作与 AI 交接文档

- 目标/范围：建立六份入口、协作、AI、数据和工作计划文档；不改业务代码或数据。
- 负责人：本次执行 AI（Codex）；团队负责人/验收人待确认。
- 状态：已合入（PR #1），验收意见待确认。
- 验收条件：用户指定文字完整、链接存在、技术说明有代码依据、交接字段可接续；独立分支 PR 审阅，合并需授权。
- 已完成：静态核对、文档准备、2026-10-05 成功创建远端分支；之前 403 已解除。
- 成果文件：README.md、CONTRIBUTING.md、AGENTS.md、CLAUDE.md、docs/data-contract.md、本文件。
- 分支/提交：docs/harmo-collaboration-handoff；文档提交 f0ee69eeeb4e20965d21c3c9f9a196b347fea0ac；PR：https://github.com/ZSY1ADBNA/HarmonyOS-API-CrossVersion-Analysis/pull/1 。本次交接补录提交可通过文件历史定位。
- 验证环境/步骤：GitHub 插件读取基线，检查原文、相对链接、默认分支和交接字段。程序、图谱、网站未运行。
- 实际结果/证据：仓库读取与分支创建成功；六份文档已发布，指定文字和相对链接检查通过，PR 已创建；未实跑流程。
- 决定/原因：跨平台协作；本轮只改文档；环境方案沿用已跑通版本，不猜版本号。
- 阻塞：仓库写入权限已恢复；本地读取工具暂不可用，按已确认方案及远端基线重新整理文档。
- 未更新产物：代码、正式 JSON、数据库和报告未改，无需因文档修改重生成。
- 下一步：保留 PR #1 合入事实；如需补充验收意见，由负责人确认。
- 更新时间：2026-10-05。
- 进展记录：2026-10-03 写入返回 403；2026-10-05 检测到 ZSY1ADBNA 应用安装并创建分支成功，随后上传六份文档并创建 PR #1；仓库所有者于 2026-10-05 合并至 master，合并提交 131a142074d68a322aafbfef9ac3f3d77b85caa2。合入不额外推断业务运行验收。

## 后续任务

以下未指派任务使用共同记录：负责人/验收人待确认；状态待开始；任务分支和提交未建立；未运行验证；更新时间 2026-10-05。接手时先补充实际信息。

### ENV-001 当前可用版本与依赖
- 目标/范围：记录已跑通环境的 Python、Neo4j DBMS、neo4j 驱动、Flask 版本，建立最小依赖说明。
- 验收条件：版本来自真实环境，新虚拟环境可安装，Windows/macOS 小样本可运行。
- 已完成/文件：确认代码引用 neo4j 和 Flask，尚无环境定义。
- 验证/证据：静态检查；运行未验证，缺成员环境。
- 决定/原因：沿用已跑通版本，先不升级或强制 uv、Docker。
- 阻塞：需可运行环境的成员提供版本。
- 未更新产物：依赖文件和版本说明。
- 下一步：在实际解释器执行 python --version、python -m pip show neo4j Flask；Neo4j Browser 执行 CALL dbms.components()，记录 DBMS 版本与 edition 后选择基线。

### ENV-002 路径与隔离数据库配置
- 目标/范围：项目相对路径、统一连接配置、独立测试实例。
- 验收条件：跨平台有效，无真实凭据入库，测试不影响共享图谱。
- 已完成/文件：静态定位 extract_versions.py、_run_extract.py、batch_extract.py 的个人路径和导入/网站连接配置。
- 验证/证据：确认清库语句与默认 session；改造及实跑未验证。
- 决定/原因：新增本地配置文件不等于代码会读取，须一起实现。
- 阻塞：目标实例和实际版本待确认。
- 未更新产物：代码/模板。
- 下一步：核对所有入口配置读取点，单独任务改造并在隔离实例实测。

### FMT-001 保持现有编码与换行
- 目标/范围：最小 .gitattributes、.editorconfig 与忽略规则。
- 验收条件：UTF-8 无 BOM、LF；Python 4 空格、JSON 2 空格，无无关全文件差异。
- 已完成/文件：19 个格式样本，JSON 生成器 indent=2。
- 验证/证据：静态样本检查，配置行为未验证。
- 决定/原因：不全仓库格式化或强制补末尾换行，避免生成数据无意义变化。
- 阻塞：待独立任务。
- 未更新产物：格式及忽略配置。
- 下一步：添加最小配置，在代表性文件与两平台核对差异。

### DATA-001 来源与 API 标识
- 目标/范围：SDK URL/SHA/版本映射、API 目录来源和 UID 碰撞验证。
- 验收条件：每版本可追溯，重载与跨模块同名小样本不错误合并。
- 已完成/文件：核对四分支映射、五个目录、UID 构造。
- 验证/证据：代码阅读；历史来源和碰撞实测未验证。
- 决定/原因：目录标签不等 API Level，不把 API 目录推断为最早版本，不以导入成功证明唯一性。
- 阻塞：生成者提供来源证据。
- 未更新产物：来源清单、完整字段定义、JSON/报告。
- 下一步：收集上游 URL/SHA，建立同名与重载样本，按影响验证下游。


## GOAL-001 目标补充与现状审查

- 目标/范围：补充 API 推荐目标和勾选规则，检查仓库、数据库、图谱网站并形成可接续计划；本轮改文档。
- 负责人：本次执行 AI（Codex）；验收人待确认。
- 状态：文档已获用户合并授权；现场检查仍阻塞，整项未完成。
- 分支：docs/api-recommendation-goal-workplan；基线 131a142074d68a322aafbfef9ac3f3d77b85caa2。
- 成果：README、CONTRIBUTING、AGENTS、CLAUDE、本文件及 docs/project-goal.md。
- 发布记录：文档提交 9de0097981b89cce79394232157dc1276f9be336；PR：https://github.com/ZSY1ADBNA/HarmonyOS-API-CrossVersion-Analysis/pull/2 。用户于 2026-10-05 明确授权合并该文档 PR；合入结果以 PR 状态及 master 历史为准。文档链接检查通过。
- [x] 核对仓库当前 AI 查询流程。效果：确认先生成回答再查数据库、未二次基于检索回答，查询限制仅提示词、null 查询处理缺陷；证据 app.py 的 SYSTEM_PROMPT、run_cypher、api_chat（基线见上）；2026-10-05，静态检查。
- [x] 抽查推荐相关数据字段。效果：API6.0 的 @ohos.bluetooth.access.json 有 31 条节点，含参数等结构化字段；对照 _run_import.py，确认导入字段需补充核对；不是完整数据质量验收。
- [x] 检查网页代码入口。效果：模板已有 AI 面板与查询结果展示，主要例子仍是版本比较；尚未定义推荐卡片和可追溯证据展示；证据 templates/index.html。
- [ ] 实查部署网站与数据库。阻塞：网页工具无法读取地址，浏览器运行环境失败；无可用只读数据库访问或输出。未验证在线状态、部署代码和实际数据，不将此失败视为服务故障。
- [x] 制定目标导向后续计划。效果：按现场基线 → 查询只读控制 → 数据完整性 → 检索 → 证据推荐 → 网站 → 验收排序，任务见下。
- [ ] 执行与自查全部完成。数据库/在线实查未完成，不能勾选整项完成。
- [ ] 验收人确认。尚未确认。
- 下一步：按用户授权合并 PR #2；有权限成员提供只读现场结果后补全 BASE-001。文档合并不代表数据库/网站实查已完成。
- 最后更新：2026-10-05（Asia/Shanghai）。
- 未更新产物：业务代码、正式 JSON、图谱、报告、部署均未改。

## 推荐工具详细后续计划

共同约定：以下负责人/验收人均待确认，状态待开始；分支/提交/实际运行结果尚无。每步完成后在本步骤勾选并写“效果、命令/输入、实际输出、证据、日期”。勾执行项不等于已获验收。本计划规定任务和验收，不表示实现已完成；可实施的现有 ENV/FMT/DATA 任务保留，避免重复建任务。

### BASE-001 建立部署与数据库真实基线（P0）

- 依赖：可用只读访问或部署成员提供输出；无需先改业务。
- 目标/范围：确认实际部署与仓库的一致性及数据是否足以检索推荐。
- [ ] 记录服务器部署提交、Python、Flask、neo4j 驱动与 Neo4j DBMS/edition；说明前后端是否同一版本。效果：待记录。
- [ ] 执行 docs/project-goal.md 的只读统计，记录各版本/标签节点数、关系数、描述与模块缺失、UID重复样本；注意 MERGE 覆盖不能仅靠重复查询发现。效果：待记录。
- [ ] 抽查蓝牙、文件、网络、相机等四类各至少一项 API，核对源码 → JSON → 图谱字段，记录描述、参数/返回、权限、since、平台与来源可用性。效果：待记录。
- [ ] 查看网站版本/概览/模块/图谱，核对只读接口与数据库实际统计；记录请求、结果和截图/日志证据位置。效果：待记录。
- [ ] 验收确认：形成基线清单及具体缺失，未知项明确未知；不能以已有 README 数字代替实查。
- 文件/证据：部署记录、查询输出和本任务链接；禁止记录真实凭据。
- 阻塞：目前无法实查。下一步：由部署成员提供上述只读结果，先完成 ENV-001 版本基线。
- 风险/未更新产物：现场真实状态未知，不在共用库运行导入。

### SAFE-001 限制 AI 查询并修复聊天边界（P0）

- 依赖：BASE-001 的测试实例信息；可先在隔离单元环境验证。
- 目标/范围：app.py 的请求解析、数据库访问、AI 输出处理及运行配置。
- [ ] 采用服务器控制的检索查询模板及参数，不把任意模型 Cypher 直接交给数据库执行；配置只读凭据、返回上限与超时。效果：待记录。
- [ ] 验证请求对象、message/history 类型和允许的历史角色，阻止客户端伪造 system 提示；处理 cypher=null、缺字段、非 JSON 响应与模型不可用。效果：待记录。
- [ ] 将正常回答、检索失败、无匹配与模型失败分开；提供清楚用户信息，不返回内部凭据或完整服务异常。效果：待记录。
- [ ] 检查在线运行 debug=True、模型 HTTP 关闭证书验证等现有行为，改为适合部署的配置；AI_MODE 回退说明与实际逻辑一致。效果：待记录。
- [ ] 验收确认：在测试实例提交写入指令和恶意历史，数据库不变；空/异常输入可预期返回；正常只读检索成功。
- 下一步：先补请求/查询边界测试，再改接口；代码与实测结果随提交更新。
- 未更新产物：现有接口未改；网站不能据本计划称为查询安全已验收。

### DATA-002 补齐推荐所需证据与标识（P0）

- 依赖：BASE-001；与现有 DATA-001 联动，来源与 UID 不另做重复修复。
- 目标/范围：提取/增强 JSON、导入映射、图谱数据，支持准确定位和版本适用性。
- [ ] 明确节点身份含版本、模块、完整限定名、类型与重载签名；对跨模块同名、重载和父级映射建立小样本。效果：待记录。
- [ ] 定义并核对推荐必需字段：名称/模块、描述、签名、参数/返回、since、废弃、权限、syscap、平台和源文件/文档位置；缺失标未知，不伪造补全。效果：待记录。
- [ ] 处理 @since 的 ArkTS 映射等实际格式；区分 SDK 标签与 API Level，并保留原文，无法解析时不错误过滤。效果：待记录。
- [ ] 将已有 JSON 的 parameters、return_description、error_codes 等按实际需求映射入图谱或检索文档；记录 Schema 变更与向后兼容。效果：待记录。
- [ ] 在隔离图谱核对小样本和重载数量，按受影响版本重生成正式数据；延期则列出数据版本和后续任务。效果：待记录。
- [ ] 验收确认：四类 API 样本可追溯，身份不错误覆盖，核心证据可检索；缺字段统计和限制有记录。
- 下一步：从 BASE 样本差异建立字段映射表，再改提取与导入，避免先全量重跑。
- 未更新产物：正式 JSON/数据库仍为现有版本。

### RAG-001 需求检索与候选排序（P1）

- 依赖：SAFE-001、DATA-002 至少代表性样本通过。
- 目标/范围：优先复用 Neo4j 和已有文档，不先强制新增向量数据库。
- [ ] 收集用户需求与约束：目标版本、场景/平台、功能、关键限制；缺失重要条件先询问，不默认为可用。效果：待记录。
- [ ] 建立受控关键词/别名检索及版本过滤，返回名称、描述、签名、来源和必要父级上下文；记录召回候选与排序理由。效果：待记录。
- [ ] 用至少 20 条代表性需求建立已人工核对的相关 API 清单，含中文功能表达、模糊需求和无匹配；先评估现有检索遗漏。效果：待记录。
- [ ] 如关键词召回不足，再单独评估向量/混合检索，记录是否引入及理由；知识库按来源和生成版本更新，避免重复和过期资料。效果：待记录。
- [ ] 验收确认：固定测试集中有证据的目标 API 可召回；版本不符合的候选被排除或明确不可用，检索可复现。
- 下一步：先定义需求输入和候选输出，再实现小样本检索；无需重构整个图谱网站。
- 未更新产物：RAG 检索组件尚未建立。

### REC-001 基于检索证据生成比较推荐（P1）

- 依赖：RAG-001。
- 目标/范围：改为检索完成后把证据交给模型，生成最终答复。
- [ ] 实现需求 → 检索 → 证据 → AI 答复闭环；记录候选和证据 ID，不再让回答先于检索结果。效果：待记录。
- [ ] 输出一个或多个推荐，明确名称/模块、版本、用途、推荐理由、候选差异、限制和来源；调用组合须有依据。效果：待记录。
- [ ] 后台校验推荐属于候选且证据 ID 有效；未知/缺证据/无候选时明确说明，不靠模型记忆补 API。效果：待记录。
- [ ] 将知识库文档作为资料而非指令，验证恶意文档或用户要求不能绕过版本过滤和只读限制。效果：待记录。
- [ ] 验收确认：同类 API 的比较理由可逐条对应证据；无匹配、缺版本、证据冲突及模型失败不返回捏造推荐。
- 下一步：先对固定候选做小样本生成和校验，再连接实时检索。
- 未更新产物：现有 /api/chat 单次模型调用仍未形成推荐闭环。

### WEB-001 需求驱动的推荐页面（P1）

- 依赖：REC-001 输出稳定。
- 目标/范围：app.py 接口与 templates/index.html 的 AI 面板；保留图谱与跨版本分析功能。
- [ ] 将需求和目标版本作为清楚输入，提供加载、失败、无结果和补充条件状态。效果：待记录。
- [ ] 展示推荐卡片、候选差异、理由、适用条件和可点击来源；图谱入口辅助解释模块/父级，不把所属关系说成调用关系。效果：待记录。
- [ ] 规范化渲染并转义模型/数据库文本，测试恶意字符串；区分推荐答复与查询调试信息。效果：待记录。
- [ ] 检查桌面/手机、连续问答、更改版本与重复请求；版本约束变化后避免沿用过期候选。效果：待记录。
- [ ] 验收确认：用户从输入需求到理解推荐与差异可完成；来源可访问；界面错误与后台状态一致。
- 下一步：按 REC 返回字段改当前面板，不先做无关界面重设计。
- 未更新产物：部署页面尚未变更，仓库 UI 检查不等于在线运行验证。

### EVAL-001 推荐效果验收与发布（P2）

- 依赖：BASE、SAFE、DATA、RAG、REC、WEB；与 ENV/FMT 任务协调。
- [ ] 对固定需求集核对候选命中、版本正确、证据覆盖、比较解释、失败提示和响应耗时；记录输入、期望、实际与失败案例。效果：待记录。
- [ ] 使用测试实例进行端到端验证；数据库节点不因聊天请求改变；统计非模型输出的实际结果。效果：待记录。
- [ ] 由成员审阅测试集期望与验收标准；不凭空给出成功率或已达标结论。效果：待记录。
- [ ] 发布前记录代码/知识库/模型配置版本、备份恢复及回退步骤；授权后部署，完成网站只读冒烟检查。效果：待记录。
- [ ] 验收人确认：符合项目目标，剩余限制明确，workplan 可由新 AI 接续。
- 下一步：先建可复现测试集，逐项补齐结果，最后请求部署/验收确认。
- 未更新产物：本轮无部署、数据库迁移或业务代码修改。

## 新任务固定字段

- ID/标题、目标与范围：
- 负责人/验收人、状态、验收条件：
- 已完成步骤、涉及文件与成果：
- 分支/提交/PR、本地未提交改动：
- 验证环境、输入、命令与工作目录：
- 预期结果、实际结果、证据：
- 决定及原因、阻塞及所需信息：
- 尚未更新的数据或报告：
- 下一步（具体文件和动作）：
- 最后更新时间（时区）、进展记录：

接手检查示例（非实际进度）：未完成提取任务需记录样本 .d.ts、已改函数、JSON 路径、预期和实际字段、任务分支及提交。尚未导入时写“图谱/网站未验证”，下一步写“核实隔离连接后导入该样本并检查节点属性”，不要仅写“继续测试”。

## DOC-003 OpenHarmony 查询助手总体计划 1.0 发布

- 目标与范围：发布用户确认的总体计划和六个技术步骤说明；同/跨版本扩展融入提取和入库，版本比较融入题集、检索与评测；仅文档修改。
- 负责人/验收人：团队负责人和验收人待确认；本次执行 AI 为 Codex。状态：文档已合入；计划内容已获用户确认，工程步骤验收另行执行。
- 基线：master 7a31e0550946594e13dcceac8f2c89645addb1fb；任务分支 docs/openharmony-query-plan-v1。
- [x] 文档内容确认（2026-10-07）：用户认可修订并授权上传和合并；不代表工程运行验收。
- [x] 独立准备发布文件：新增 docs/openharmony-query-plan/ 内七份 Markdown，README 增加入口；保留旧任务、负责人和验收条件，以任务映射衔接，去除个人绝对路径。
- [x] 发布文件自查（2026-10-07）：九个提交文件均为 UTF-8 无 BOM、LF；相对 Markdown 链接、代码块闭合、七份计划与 28 道题检查通过；无个人绝对路径/已知凭据模式，git diff --check 通过。仅文档静态检查，未运行业务、数据库或网站。
- [x] 发布并合入（2026-10-07）：[PR #4](https://github.com/ZSY1ADBNA/HarmonyOS-API-CrossVersion-Analysis/pull/4) 已 merged=true，合并提交 deb06c2159703992fc62f981c0f129a0e38cc175。PR 差异仅九个文档文件，无关联 CI 状态或工作流；按用户明确授权使用普通 merge，未强推。
- 本地状态：已有副本 workplan.md 存在未提交修改，未覆盖或发布；使用新下载的独立副本；未检查其他成员本地状态。
- 未更新产物：业务代码、正式 JSON、数据库、报告和部署未变；六个工程步骤均未因本次文档发布标完成。
- 下一步：团队按总体计划步骤 01 固定两版本样本与部署代码，步骤 02 并行收集问题并核对参考答案；原工程任务保持未完成。
- 最后更新：2026-10-07（Asia/Shanghai）。

## DOC-05A 官方说明文档 RAG 检索库与多版本属性检索（黄宇鹏）

- 目标与范围：按照总体计划 1.0 步骤 05A，完成官方 Markdown 说明文档（official/ 目录）结构化解析与切块、构建支持名称/关键词/条件检索及跨版本属性对比的 SQLite+FTS5 RAG 库；免除全版本自动化 diff 引擎，通过多版本 API 属性对账直接支撑大模型对比。首期以 v6.0.0.1-Release 与 v6.1-LTS 小样本入库与检索验证。
- 负责人/验收人：负责人：黄宇鹏；验收人：待确认；本次执行 AI 为 Antigravity。状态：待验收（执行与自查已完成）。
- 验收条件：
  1. 解析官方 Markdown 文档并结构化切块，完整保留名称、签名、起始版本（since）、废弃标记、权限、系统能力、参数、返回值、错误码及上下文；
  2. 构建独立的 SQLite + FTS5 检索数据库，支持按 API 名称、全文关键词（中文/英文/技术词）、条件过滤（版本、Kit、权限等）检索；
  3. 支持同一 API 在不同版本间属性联合检索与侧重对比（side-by-side），输出易于大模型直接分析的结构化/Markdown 证据；
  4. 具备完备单元与集成测试套件，执行真实测试通过。
- 已完成步骤、涉及文件与成果：
  - [x] 1. 数据模型与 Markdown 解析器增强（doc_rag/models.py, doc_rag/parser.py）：修复冒号置于粗体内部（如 `**参数：**`、`**返回值：**`、`**错误码：**`、`**系统能力：**`、`**需要权限：**`）导致的字段漏提取缺陷；新增独立 Interface/Class/Struct 文档（如 `AudioRenderer.md`）容器层级识别，将成员方法与属性正确归属父类；新增 C-API 结构体成员变量解析，避免将方法参数表误判为属性。
  - [x] 2. 独立 SQLite + FTS5 索引库实现与优化入库（doc_rag/indexer.py）：搭建 doc_chunks 结构表与 doc_chunks_fts 虚表，定制中英文与技术标识符分词器（CJK unigram+bigram），支持本地目录与直接读取 zip 归档入库。效果：网络、音频、通知三 Kit 共 6,582 块结构化入库完成。
  - [x] 3. 多维度检索与跨版本属性精准对比引擎（doc_rag/retriever.py）：实现查询输入规范化（支持 `createHttp()`、`http.createHttp`）、嵌套父子属性精准查询（`AudioRenderer.state`），彻底移除 `compare_api_across_versions` 中过度宽松的 `LIKE %clean_name%` 模糊匹配，消除跨 API 脏召回（如查 `createHttp` 不再混入 `createHttpResponseCache`）；增强 FTS5 操作符与特殊符号安全转义机制。
  - [x] 4. CLI 入口脚本（ingest_official_docs.py, query_official_docs.py）：支持批量导入、交互查询与 JSON 输出。
  - [x] 5. 自动化测试套件（test_official_doc_rag.py）：扩展至 29 项测试（覆盖 C-API 声明、冒号位置容错、独立 Interface 容器层级、FTS 符号容错、精确对比与属性增量、属性主键防碰撞、无H2文档解析、FTS严格对齐、TCP/TLS独立检索、H3类与H4属性层级防碰撞、同文档多同名属性表去重防碰撞、空输入与空白串安全拦截、FTS孤儿索引原子清理等），实跑 100% 通过（Ran 29 tests in 7.983s, OK）。
  - [x] 6. 修复组长反馈的属性覆盖、索引错配与零块遗漏缺陷及深度二次排查修复（doc_rag/parser.py, doc_rag/indexer.py, doc_rag/retriever.py, ingest_official_docs.py, query_official_docs.py）：
    - 修复属性主键碰撞与多级层级穿透：重构 `DocParser` 引入完整 H3/H4 多级层级追踪（`current_h3`），修复 H4 属性与方法跳过 H3 类直接挂在 H2 导致不同类同名属性（如 `AsyncLock.name` 与 `AsyncLockInfo.name`）覆盖的隐患；彻底禁止将 section 名称 `"属性"` / `"常量"` 用作父类容器名，正确绑定 `AudioRenderer`、`TCPSocketConnection`、`NetConnectionPropertyInfo` 等真实类名；将属性与错误码计数器（`prop_counters`, `err_counters`）提升至文件级作用域，彻底消除单文档内多表同名属性（如 `CameraFormat.CAMERA_FORMAT_DNG`）的主键冲突；
    - 修复 FTS 孤儿索引与搜索错配：`ingest_chunks` 增加批次内存去重与 FTS5 原子清理重插，`clear_version` 与 `sync_fts_index` 引入外连接原子孤儿数据清理（`DELETE FROM doc_chunks_fts WHERE chunk_id NOT IN (SELECT chunk_id FROM doc_chunks)`），并在 `search_by_keyword` 查询中增加 `GROUP BY dc.chunk_id`，杜绝搜 TCP 返回 TLS 描述的索引幽灵现象；
    - 修复无二级标题文档零块丢失与标题噪音：在 `extract_sections_by_headings` 中为仅含 `# H1` 的文档增加切块兜底，清洗 `clean_sup` 中粗体（`**属性**`）与 Markdown 超链接修饰，消除 `# # Overview` 等前导符号污染，并在 `DocParser` 中新增 `_extract_error_code_chunks`，使 7 份零块官方文档（音频常量文档、两版本内核错误码文档、4 份 Kit 导航首页）全部成功结构化切块入库；
    - 修复空查询与空白串泄漏：在 `search_by_name` 与 `compare_api_across_versions` 中加入对空串及纯空白字符的严格校验与短路返回，杜绝全库 LIKE 扫描与脏数据泄露。
- 分支/提交/PR、本地未提交改动：
  - 任务分支：feat/doc-rag-05a；基线：master 35e72f782fd3c4e618b0b904b9f669f5b3f5dd2c；PR：https://github.com/ZSY1ADBNA/HarmonyOS-API-CrossVersion-Analysis/pull/6 。
  - 新增/优化文件：doc_rag/__init__.py, doc_rag/models.py, doc_rag/parser.py, doc_rag/indexer.py, doc_rag/retriever.py, ingest_official_docs.py, query_official_docs.py, test_official_doc_rag.py, docs/official-doc-ingestion-audit.md。
- 验证环境、输入、命令与工作目录：
  - 环境：Linux, Python 3.13.12, SQLite 3 (内置 FTS5)
  - 工作目录：/home/whywood/project/HarmonyOS-API-CrossVersion-Analysis
  - 测试命令：python3 test_official_doc_rag.py -v
  - 重新入库命令：
    - v6.0: python3 ingest_official_docs.py --doc-dir official/docs-OpenHarmony-v6.0.0.1-Release-zh-cn-application-dev-reference/zh-cn/application-dev/reference --version v6.0.0.1-Release --kit apis-network-kit,apis-audio-kit,apis-notification-kit --clear
    - v6.1: python3 ingest_official_docs.py --zip official/docs-OpenHarmony-v6.1-LTS-zh-cn-application-dev-reference.zip --version v6.1-LTS --kit apis-network-kit --clear
  - 检索核对命令：
    - python3 query_official_docs.py --name "AudioRenderer.state"
    - python3 query_official_docs.py --name "AudioCapturer.state"
    - python3 query_official_docs.py --keyword "TCPSocketServer"
    - python3 query_official_docs.py --name "DEFAULT_VOLUME_GROUP_ID"
    - python3 query_official_docs.py --name "EPERM"
    - python3 query_official_docs.py --compare "AudioRenderer.state"
    - python3 query_official_docs.py --stats
- 预期结果、实际结果、证据：
  - 预期：测试 29/29 全部通过；5 组属性主键覆盖彻底消失；FTS 虚表记录数与主表严格 1:1 对齐（0 孤儿数据）；7 份零块文档被正确解析入库；TCP 关键词检索不再错配 TLS 属性；空查询安全短路返回。
  - 实际结果：
    - 测试结果：29 项测试全通（Ran 29 tests in 7.983s, OK）。
    - 数据库状态：总记录数达到 6,781 块（v6.0: 4,779 块, v6.1: 2,002 块）；FTS 虚表记录数精准为 6,781 块，两者差值为 0，FTS 重复主键为 0，孤儿记录为 0。
    - 全库压力审计结果：全量 4 版本 13,887 个 Markdown 文件压力解析，碰撞数彻底降为 0（v6.0 全量 73,022 块碰撞为 0，v6.1 全量 75,330 块碰撞为 0）。
    - 属性覆盖消除：`AudioRenderer.state`（“音频渲染器的状态”）与 `AudioCapturer.state`（“音频采集器状态”）均拥有独立主键，共存且独立精确检索；`TCPSocketConnection.clientId`、`LocalSocketConnection.clientId`、`TLSSocketConnection.clientId` 三者独立；`NetConnectionPropertyInfo.netHandle` 与 `NetBlockStatusInfo.netHandle` 独立。
    - 检索错配消除：检索 `TCPSocketServer` 准确返回 `TCPSocketServer` / `TCPSocketConnection` 对应条目，不再混入或返回 `TLSSocketServer` 描述。
    - 零块文档入库：7 份官方文档成功入库并可检索（`arkts-apis-audio-c.md` 提取 3 块含常量 `DEFAULT_VOLUME_GROUP_ID`、`errorcode-kernel.md` 两版本分别提取 62 块与 130 块含错误码 `EPERM`、4 份 Kit Readme 提取 1 块 Overview）。
- 决定及原因、阻塞及所需信息：
  - 决定：采用内置 SQLite FTS5，完全无外部 C 扩展或模型依赖，保证轻量、零依赖与可重现；官方大 zip 采用 zipfile 流式读取，无需解压 300MB+ 占用额外磁盘；大模型直接基于两版本属性对比检索结果进行差异总结，免除全版本自动化 diff 引擎。
  - 全量入库决策：对 4 个大版本全量 13,887 个 Markdown 审计完成，明确不试图用单一通用脚本解决全部 52 个 Kit 的所有排版差异；后续其他 Kit 与版本入库由对应 Agent 结合模块特征按需编写或适配专用脚本，重点防范主键碰撞、零切块丢失、C-API 拦截与 FTS5 无索引扫描性能陷阱。已形成专属指引文档 docs/official-doc-ingestion-audit.md 并在 AGENTS.md、README.md、步骤 05 说明中建立入口。
  - 阻塞：无。
- 尚未更新的数据或报告：
  - 本次任务不修改现有图谱与 03_extracted_json 数据，图谱网站与分析报告保持原有状态。
- 下一步（具体文件和动作）：
  - 提交当前任务分支 feat/doc-rag-05a 并创建面向 master 的 PR。
  - 配合步骤 05B（智能体调用）将 DocRetriever 包装为 Agent Tool（如 LangChain Tool 或标准函数），为大模型提供 API 属性与文档查证支撑。
- 最后更新时间（时区）、进展记录：
  - 2026-10-09（Asia/Shanghai）：完成 05A 官方文档深度审查与缺陷修复，18 项测试全部通过；完成 4 版本 13,887 文件全量压力审计与缺陷归因，发布 docs/official-doc-ingestion-audit.md 并接入主线文档入口。
  - 2026-10-11（Asia/Shanghai）：彻底修复组长反馈的 3 处核心缺陷（属性主键覆盖、FTS 索引孤儿与检索错配、无二级标题文档零块遗漏）；深度审查发现并根除 H3/H4 多级类与属性层级逃逸、文档内多表同名属性计数器重置碰撞、空查询全表 LIKE 泄露、粗体标题过滤失效等多处隐患；单元与集成测试套件扩展至 29 项全部通过；全库全量审计达到 0 碰撞，数据库记录数达到 6,781 且 FTS 虚表 1:1 严格对齐（0 脏记录），AudioRenderer/AudioCapturer 独立共存检索，7 份零块文档完整入库。
