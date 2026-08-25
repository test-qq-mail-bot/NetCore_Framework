# NetCore Framework 使用说明与可调取 API 手册

> > 适用版本：系统/框架 **20260824-V2**，数通配置卫士 **20260824-V2**，运维常用工具箱 **20260825-V2**，CMDB 资产配置管理 **20260824-V2**，Wiki 文档中心 **20260823-V1**
>
> 本文档面向使用者与二次开发者，说明如何启动、登录、使用各功能模块，以及程序对外提供的全部 HTTP API。
>

## 一、快速开始

1. **启动程序：运行 `netcore-framework.exe`（Windows 单文件）或 `python main.py`（开发模式）。
 - 默认监听 `0.0.0.0:8080`；若端口被占用会自动顺延（8081…），控制台会打印实际访问地址。
2. **打开 Web 后台：浏览器访问 `http://127.0.0.1:8080`（或控制台提示的地址）。
3. **默认账号：
 - 用户名：`admin`
 - 密码：`Admin@123!`
 - ⚠️ 首次登录后会提示「当前使用默认密码，建议尽快修改」
4. **登录过程：前端先用 `GET /api/system/crypto-key` 获取密钥，对用户名/密码做 AES-256-GCM 加密后再提交，传输过程不出现明文密码。

---

## 二、功能模块导航

| 菜单 | 路径 | 说明 |
| --- | --- | --- |
| 系统概览 | `/dashboard` | 版本、运行时长、Python 版本、插件数量、服务器时间 |
| 系统设置 → 基础设置 | `/system/basic-settings` | 软件名称、版本显示名、TOTP 开关、自动退出时间 |
| 系统设置 → 安全策略 | `/system/security` | IP 白/黑名单、登录失败锁定策略 |
| 系统设置 → 通知管理 | `/system/notify` | 邮件/Webhook 等通知渠道配置与测试 |
| 系统设置 → 日志中心 | `/system/log-center` | 日志级别调整、审计日志查询/导出/清理 |
| 系统设置 → 插件列表 | `/system/plugins` | 插件启用/禁用、热重启 |
| 数通配置卫士 | `/guardian/*` | 菜单为4项（设备管理/任务管理/通知中心/插件设置）；仪表盘已集成到设备管理页设备列表上方，统计卡为 4 格：**设备总数 / 启用设备数量（紫色）/ 健康（绿）/ 异常（红）**（顺序固定，启用设备数量位于设备总数右侧、健康卡左侧）；**设备列表恢复表格首列原生勾选框（支持全选/单选，V12 的独立共享多选组件 `GuardianMultiselect` 已删除）**，勾选后显示批量按钮（批量更新配置/测试/导出/删除）；**多个更新按钮（更新设备信息/更新配置/批量测试）可独立、并发点击，不再因全局锁被拦截**（后端按设备串行化，不会连接冲突）；编辑设备「启用」开关正确回显（0/1 整数适配），禁用设备在连接状态列显示「已禁用」标签；任务管理操作栏点击「日志」弹出日志弹窗（默认10条/页，可选5/10/20/50，内含每设备详情与变更查看，**每设备「结果」为单一标签：失败红/变更黄/无变化绿，操作列已拉宽**）；**新增/编辑任务窗口含「设备范围」（下拉多选，含「全部设备」选项）与「任务类型」（下拉多选，取值：更新设备信息/更新配置/批量测试）两个字段**；任务列表含「任务类型」展示列；**执行情况列直接关联该任务最近一条任务日志的状态并着色（成功绿/失败红/执行中·等待中蓝/未运行灰），同时显示该日志的结果摘要**；任务「执行」保持一键触发，内部按设备范围与任务类型逐台逐类型执行；**通知中心的「任务采集失败告警」点击后直达该次失败运行的详情弹窗（`detail` 携带 `task_id=X&log_id=Y` 深链）** |
| 运维常用工具箱 | `/opstoolbox/*` | 网络诊断含：连通性探测（ICMP/TCP/UDP 三合一）、MTR 式路由追踪、端口扫描（**支持 1–65535 全量，提供「常用 / 1-1024 / 1-10000 / 全量」预设按钮；扫描范围完全由输入决定，不受端口字典限制**）、**端口百科**（内置 **305 条**端口字典，含协议/服务/分类/用途说明，支持按端口号或关键字搜索）、**网络测试**（测试服务器与客户机间延迟/抖动、上传/下载速度，可自定义测试时长与传输大小，UI 自适应）；MTR 路由追踪（无需管理员权限，逐跳 IP/RTT/丢包）、SSL 证书检查、Whois 查询、IP 归属地、Wake-on-LAN、MAC/OUI 厂商、DNS 探测（HTTP/SSL/Whois/IP归属地/WOL/MAC-OUI/DNS 共 7 个工具）；**远程连接/传输**：「FTP/SFTP 客户端」（类 Windows 文件管理器，协议可切 FTP/SFTP，双击进子目录/上级目录/根目录，上传下载界面化；**中文名与历史乱码名文件的列出/上传/下载/批量下载/删除全部按原始字节精确处理**；含「停止时清理」勾选框默认开启，离开页面自动清空临时下载目录；含 SFTP，无独立 SFTP 客户端页；WebDAV 仅服务端、无客户端）与「FTP/SFTP/WebDAV/TFTP 服务端」（FTP/SFTP/WebDAV/TFTP 四类服务端合并为一页，协议单选切换，临时隔离目录默认开启、根目录默认指向该隔离目录，支持「浏览服务器目录」选目录；**启动后展示连接信息卡**——访问地址/账号/密码/根目录一键复制、密码留空即匿名免密登录、WebDAV 可「在浏览器中打开」查看目录列表，并在页内表格直接展示服务器根目录下的文件；**点击「运行中的服务端」列表任意一行即可查看该服务端的客户端连接信息**——在线连接的来源地址/登录用户/连接时长/收发字节/最近操作，以及历史连接与登录失败事件）；编码/格式/加密、文字处理、TOTP 工具中心、**二维码工具箱**（「生成二维码」「识别二维码」合一，无页内多余表头）、图片处理（**「压缩和格式转换」**，字节数带常用单位如 `10240(10.0KB)`，「体积变化」按实际增减显示「减小/增大」）、IP 工具箱；所有工具点击执行即显示「正在执行」实时反馈、结果返回立即渲染；**端口扫描开放端口为可点击标签**，点击**弹出小窗**显示该端口的协议/服务/分类/用途说明（同端口多条记录并列展示），窗内可进一步跳转完整端口百科页；工具箱各工具的执行日志统一上报至「系统设置 → 日志中心」查看（原 `/opstoolbox/logs` 独立页已下线） |
| CMDB 资产配置管理 | `/cmdb/*` | 仪表盘/IT 资产（**资产列表 + 机柜视图**双标签）/办公·实物资产/维保管理/报表中心（5 个二级页面；端口拓扑已取消，机柜视图移至 IT 资产页，新建表单按页面限定分类并默认只展开 6 项常用信息，资产详情支持**盘点时间**，打印标签内置离线二维码） |

---

## 三、认证与鉴权机制

- **凭证加密：登录密码经 AES-256-GCM（前端 `aesgcm.js` 与后端 `core.crypto_utils.CryptoUtils` 兼容）加密后传输；后端解密失败会回退为明文（便于调试）。
- **令牌：登录成功后返回 JWT（HS256），有效期由 `core.yaml` 的 `jwt.expire_minutes` 决定（默认 1440 分钟）。
- **会话空闲超时：由 `auto_logout_minutes`（基础设置，默认 5 分钟，0=关闭）控制。前端心跳（`/api/auth/heartbeat`）会续期；超时后后端 `SessionManager.touch` 返回失效，接口返回 **401**，前端**切回登录视图**（不再整页刷新，避免轮询接口瞬时 401 引发刷新死循环）。
- **请求头：所有受保护接口需在 `Authorization: Bearer <token>` 中携带令牌。

---

## 四、可调取 API 总览

> 基础前缀：`/api`。除特别标注「公开」外，均需 `Authorization: Bearer <token>`。
> 通用约定：成功返回含 `success: true`；失败返回 `success: false` 与 `message`。

### 4.1 认证 `auth`

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录；body：`{username, password(密文), totp?}` | 公开 |
| POST | `/api/auth/totp/setup` | 生成 TOTP 密钥与二维码 | 需登录 |
| POST | `/api/auth/totp/verify` | 校验并绑定 TOTP | 需登录 |
| POST | `/api/auth/logout` | 注销（清除会话） | 需登录 |
| POST | `/api/auth/heartbeat` | 心跳续期，返回 `remaining_seconds`（-1=关闭自动退出） | 需登录 |
| GET | `/api/auth/last-login` | 上次登录时间/IP | 需登录 |

### 4.2 安全 `security`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/security/whitelist` | 获取白名单 |
| POST | `/api/security/whitelist` | 添加白名单 `{ip, note?, expires_at?}` |
| DELETE | `/api/security/whitelist` | 删除白名单 `{ip}` |
| GET | `/api/security/blacklist` | 获取黑名单 |
| POST | `/api/security/blacklist` | 添加黑名单 `{ip, minutes?, note?}` |
| DELETE | `/api/security/blacklist` | 删除黑名单 `{ip}` |
| GET | `/api/security/failure-policy` | 获取登录失败锁定策略 |
| PUT | `/api/security/failure-policy` | 更新失败策略 |

### 4.3 通知 `notify`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/notify/send` | 发送通知 `{channels, title, content, priority?, recipients?, template_id?, template_vars?}` |
| GET | `/api/notify/channels` | 渠道状态列表 |
| POST | `/api/notify/test/{channel}` | 测试指定渠道 `{recipients?}` |
| GET | `/api/notify/config` | 获取通知配置（敏感字段脱敏） |
| PUT | `/api/notify/config` | 保存通知配置 |

### 4.4 审计日志 `logs`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/logs/audit` | 分页查询 `?page&size&ip&result&action&start_date&end_date` |
| GET | `/api/logs/audit/export` | 导出 `?fmt=csv\|json`（附件下载，流式输出，日志量大时不占内存） |
| DELETE | `/api/logs/audit/clean` | 清理全部审计日志 |

- **操作人字段**：各插件写入审计日志时记录的是**发起请求的真实登录账号**（取自 JWT），
  CMDB 的资产新增/修改/删除、机柜与端口变更等均可按操作人追溯，不会统一记成 `system`。
- **导出**：CSV 导出带 UTF-8 BOM，可直接用 Excel 打开而不乱码。

### 4.5 系统 `system`

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/api/system/crypto-key` | 返回加密密钥/软件名/版本/TOTP 开关 | 公开 |
| GET | `/api/system/health` | 健康检查 `{status, time}` | 公开 |
| GET | `/api/system/info` | 系统信息（版本/运行时长/插件数等） | 需登录 |
| GET | `/api/system/menus` | 当前用户菜单 | 需登录 |
| GET | `/api/system/basic-settings` | 获取基础设置 | 需登录 |
| PUT | `/api/system/basic-settings` | 保存基础设置 | 需登录 |
| PUT | `/api/system/log-level` | 调整日志级别 `{level}` | 需登录 |
| POST | `/api/system/session/reset` | 重置当前会话续期 | 需登录 |
| GET | `/api/system/session/status` | 会话剩余秒数 | 需登录 |

### 4.6 插件 `plugins`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/plugins/` | 插件状态列表 |
| POST | `/api/plugins/{name}/toggle` | 启用/禁用插件 `{enabled?}`（持久化到 user_config.yaml） |
| POST | `/api/system/plugins/reload` | 热重启单个插件 `{name}` |
| POST | `/api/system/plugins/reload-all` | 热重启全部插件 |
| POST | `/api/system/plugins/reload-failed` | 重启此前加载失败的插件 |

### 4.7 前端与插件专属

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/api/plugins/frontend-manifest` | 返回各插件 `frontend/*.js` 清单，供框架动态注入 | 公开 |
| GET | `/api/opstoolbox/health` | 运维工具箱健康与版本 `{version, tools}` | 需登录 |

### 4.8 数通配置卫士 `guardian`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/guardian/dashboard` | 仪表盘统计 `{stats:{total_devices, green, red, enabled}, recent_changes}`；**`enabled`（启用设备数量）** |
| GET | `/api/guardian/tasks` | 任务列表（含下次执行时间、`last_status` 最近日志状态、`last_log_summary` 最近日志结果摘要，用于执行情况列着色展示） |
| POST | `/api/guardian/tasks` | 新建任务 `{name, cron_expression, device_ids:[], all_devices?, task_type:[], enabled?, max_executions?, max_consecutive_failures?}`；`all_devices=true` 存 `["__all__"]` 标记，执行时实时取全部设备；**`task_type` 为任务类型 JSON 数组**（前端发数组，后端归一化为 JSON 数组字符串），取值：`refresh_info`(更新设备信息) / `collect`(更新配置) / `test`(批量测试) / `topology`(更新拓扑，20260806-V1)，可单选或多选，缺省 `["collect"]` |
| PUT | `/api/guardian/tasks/{id}` | 更新任务（字段同上，含 `task_type`） |
| DELETE | `/api/guardian/tasks/{id}` | 删除任务并移除调度 |
| POST | `/api/guardian/tasks/{id}/run` | 手动触发执行（后台线程） |
| POST | `/api/guardian/tasks/{id}/toggle` | 启用/停用 `{enabled: bool}` |
| POST | `/api/guardian/tasks/recover` | 扫描并恢复中断任务 |
| GET | `/api/guardian/task-logs` | 任务日志分页 `?task_id&page&size`（供「任务管理」页「日志」弹窗调用；通知中心「任务采集失败告警」亦通过此接口在任务管理页自动弹出对应任务日志，不再有独立任务日志页面） |
| GET | `/api/guardian/task-logs/{log_id}` | 日志详情（含每设备结果，每设备 `health` 连接状态字段，并可查看变更内容 / 跳转设备配置页） |
| GET | `/api/guardian/diffs?device_id=` | 设备配置变更差异（V3 任务日志详情「查看变更内容」调用，返回最近一次 diff 文本） |
| GET | `/api/guardian/devices/batch-export?ids=` | **加密导出：`ids` 为逗号分隔设备 ID（不传为全量），返回 CSV 附件（UTF-8 BOM），列与批量导入一致（`name,ip,device_type,vendor,auth_method,username,credential,ssh_port`）；**credential 为加密密文（前缀 `ENC:`，AES-256-GCM），不含明文密码**，仅可导回本系统（前缀 `ENC:` 直接还原，无前缀按明文自动加密存储），文件含 `#` 注释提示 |
| POST | `/api/guardian/devices/batch-action` | 批量操作 `{action, ids}`；action 支持 `test`/`refresh_info`/`collect`/`delete`/`topology`（20260806-V1：**更新拓扑信息**，对选中设备集合执行一次聚合发现并更新最新快照，非逐台执行） |
| POST | `/api/guardian/topology/discover` | **拓扑发现**（20260806-V1）`{device_ids:[], recursive?:bool, prefer_brand?:str, merge?:bool}`；按厂商 Profile 差异化发现：SNMP LLDP-MIB（v2c/v3）→ SNMP CDP（思科）→ CLI LLDP/NDP（SSH/Telnet）逐级降级；`recursive` 递归 BFS 扩展（深度受设置 `topology_max_depth` 限制）；`prefer_brand` 可按实际品牌重发现；**`merge`（20260810-V9，默认 true）增量合并**——只更新所选设备及其关联链路、保留未涉及设备，发现失败设备清除其旧链路；`merge=false` 为覆盖式全量重建。返回 `{nodes, edges, diff:{added,removed}, results, stats, duration}`，**同步执行**（内部并发，设备多时耗时较长，前端 loading）。链路边含 `src_name/src_ip/src_port/src_desc/dst_name/dst_ip/dst_port/dst_desc`（20260810-V9 补齐对端名称/IP/端口描述等 SNMP 可获取信息）；`results[]` 含 `method/message/notes/detail`（`notes` 为 SNMP→CLI 降级原因，`detail` 为 SNMP 原始查询记录 `[{oid,type,value}...]` 或 CLI 命令） |
| GET | `/api/guardian/topology/latest` | 取最近一次拓扑快照 `{success, snapshot:{nodes, edges, ...}}`（无快照时 `success=false`） |
| GET | `/api/guardian/topology/snapshots` | 快照列表（仅元信息；当前只存最新一份，覆盖式） |
| GET | `/api/guardian/topology/device-neighbors/{dev_id}` | 单设备邻居实时发现（返回发现方式/邻居列表/失败原因） |
| POST | `/api/guardian/topology/export-html` | 导出自包含 HTML 拓扑图 `{svg, nodes, edges, results}`（前端传画布 SVG；后端净化 + 字段转义防 XSS；**20260810-V9 内嵌原生 JS 交互脚本**，导出文件支持滚轮缩放/空白平移/节点拖拽，返回 `text/html` 附件） |
| POST | `/api/guardian/topology/export-excel` | 链路明细导出 Excel `{nodes, edges}`（openpyxl 生成 `.xlsx` 附件；**20260810-V9 列扩展**：本端/对端设备、IP、接口、端口描述、发现方式） |

> **任务日志使用说明：任务管理列表每行提供「运行日志」按钮 → 跳转到任务日志页并按该任务过滤。在任务日志详情中，每条设备记录显示其**连接状态**（绿/红点）；若该次执行产生了配置变更，出现「查看变更内容」按钮可查看最近一次 diff；任何设备记录均可「查看设备配置」一键跳转到该设备的配置页（默认停留在变更 diff 视图），便于核对变更前后的配置。

> **任务类型与一键执行说明：
> - **任务类型 `task_type`：新建/编辑任务时，窗口含「设备范围」与「任务类型」两个字段，均为标准下拉多选（`el-select multiple`）。`task_type` 取值：`refresh_info`=更新设备信息、`collect`=更新配置、`test`=批量测试；支持单选与多选，以 JSON 数组存库；缺省 `["collect"]`。勾选全部类型时逐类型全部执行，运行详情 message 形如 `[更新设备信息] 成功；[更新配置] 采集成功；[批量测试] 成功`。
> - **运行详情：每台设备「结果」为单一标签（失败/变更/无变化）；「任务采集失败告警」通知 `detail` 携带 `task_id=X&log_id=Y`，通知中心点击直达该次运行详情弹窗。
> - **一键执行：任务列表「执行」按钮保持一键触发（`POST /api/guardian/tasks/{id}/run`），后端按任务保存的 `device_ids`（含 `["__all__"]` 全部设备）与 `task_type` 逐台、逐类型调用设备管理连接逻辑执行，结果写入任务日志（供「执行情况」列着色与「日志」弹窗查看）。
> - **老旧网元 SSH 握手修复：批量更新配置时若报 `SSH 协议握手失败 / Incompatible ssh peer (no acceptable host key)`，通常是目标设备（如老款华为交换机）仅提供 SHA-1 的 `ssh-rsa` 主机密钥，而 netmiko/paramiko 4.x 默认禁用该算法所致。连接构造器显式 `disabled_algorithms={'keys': []}` 重新启用旧主机密钥并 `ssh_strict=False`，已用真实华为交换机 `192.168.12.100` 验证握手成功。

> **网络拓扑（20260806-V1）说明：
> - **三入口**：①「网络拓扑」页交互发现（选种子设备，默认递归 BFS）；② 设备管理页多选设备 →「更新拓扑信息」批量按钮；③ 定时任务类型「更新拓扑」（与批量按钮共用同一聚合逻辑）。
> - **按厂商差异化发现**：`huawei`(含 eKitEngine) / `huawei_smart`(华为智选 FutureMatrix) / `h3c` / `cisco` / `ruijie` / `fortinet` / `tplink` 各有独立 Profile。SNMP 优先（v2c/v3，LLDP-MIB；思科补 CDP-MIB），失败降级 CLI（SSH/Telnet，华为/华三 LLDP 关闭时补 NDP）。
> - **华为 vs 华为智选**：两者**型号可能相同**（如 S5735S-L24T4X-QA2），区分只能靠 `disp ver` 首行品牌串（`Huawei` vs `FutureMatrix`）。设备信息采集时自动识别「实际品牌」，与设备档案厂商不符时在设备详情页黄色提示；拓扑页可用「品牌」下拉按实际品牌重发现。
> - **链路差异**：发现时对比上次快照，新增（绿）/消失（红）在画布标注，「消失链路」页签可查看明细。
> - **导出**：拓扑图导出自包含 HTML（内嵌 SVG + 节点/链路/发现明细表，离线可打开）；链路明细可导出 Excel。
> - **拓扑参数**（插件设置页）：`topology_snmp_timeout`（单次 SNMP 超时秒数）、`topology_max_depth`（递归深度，0=仅种子一层）。

### 4.9 运维常用工具箱 `opstoolbox`（v20260806-V2）
> **20260806-V2 主要变更（需求③④⑤⑥⑦⑧⑨⑩）**：
> ③ **端口扫描取消「常用端口 / 1-1000(默认) / 1-10000 / 全量 1-65535」4 个预设按钮**——端口范围改为直接手填（保留输入框与「本次将扫描 N 个端口」实时提示）。
> ④ **SSH 批量执行结果增加「执行结果（N 台）」表头**——与上方主机列表/命令输入区明确分区。
> ⑤ **批量执行结果点击主机名弹窗进入该设备交互终端**——复用交互终端能力（xterm + WebSocket），可直接输入命令；后端结果行新增 `port`/`user`，支持 `user@host:port` 每行独立凭据。
> ⑥ **FTP/SFTP 删除乱码文件 450 兜底**——删除按「`path_raw` 原样 → 文件名原始字节 → 显示名按 utf-8/gbk/gb2312 重编码」候选字节集逐一尝试，任一成功即删成功（中文名「上传→列表→删除」全链路实测无 450）。
> ⑦ **服务端「浏览服务器目录」支持点击「上级目录」**——父目录越出白名单时回到顶层重新列出全部可选根目录（原逻辑按钮被禁用、用户被困子目录）。
> ⑧ **服务端面板改版**——取消独立「已启动服务端·连接信息」卡片，连接信息并入「运行中的服务端」表格展开行（协议/访问地址/用户名/密码/根目录/文件目录）；访问地址**自动列出服务器全部本机 IP**（`/server/list` 新增 `local_ips`，不再显示「请替换为服务器实际 IP」）；表格加宽至 1200px 并支持分页（默认 10 条/页，可选 5/10/20/50）。
> ⑨ **前端工具库按功能域拆分**——70KB 的 `netcore_client_lib.js` 拆为 `netcore_lib_base/ip/ipcalc/text/totp` 5 个文件（最大 39KB），全局接口 `NC_CLIENT_LIB / NC_MD5 / NC_CRC32 / NC_B32ENC / NC_TEXT_ENGINE / NC_IPCALC_ENGINE / NC_TOTP_ENGINE` 保持不变。
>
> **20260806-V1 主要变更（9 项，需求②③④⑤⑥⑦⑧⑨⑩⑪）**：
> ② **端口扫描结果点击开放端口弹出「端口用途说明」小窗**——展示协议/服务/分类/说明，支持同端口多条记录（如 TCP/UDP 各一），窗内可跳转完整「端口百科」页；端口字典 **305 条**由 `portinfo_00_db.js` 挂载到 `window.NC_PORT_DB`，扫描页与百科页共用同一份数据。
> ③ **SSH/Telnet 批量执行不再等满超时**——shell 通道输出静默 ≥1.0s 即判定命令结束立刻返回（此前需等到 `cmd_timeout` 才回结果）。真机实测（Linux 192.168.12.100）批量执行 **2.2 秒返回**；认证失败也快速返回并在 `error` 字段给出明确原因（如 `Authentication failed.`）。
> ④⑤⑥ **FTP/SFTP 中文与乱码文件名字节透明化**——列表额外返回 `raw`（文件名原始字节 base64）与 `path_raw`（完整路径原始字节 base64）；下载/上传/批量下载/批量删除全部改用 `path_raw` 精确定位，与服务器上的字节逐位一致。**批量下载不再 `550 File does not exist`、上传中文名不再乱码、删除历史乱码文件不再 `450 Error deleting file`**。破坏性删除操作全程只执行一次，不做换编码重试。
> ⑦ **服务端「浏览服务器目录」按钮修复**——`GET /fs/list` 正常拉起目录选择器。
> ⑧ **新增运行中服务端的客户端连接信息查看**——`GET /server/connections?server_id=`，返回在线连接（peer/用户/状态/连接时间/时长/收发字节/最近操作）、历史连接与事件（含登录失败）、累计连接数与协议语义提示（TFTP 无连接、WebDAV 短连接）。
> ⑨ **FTP/SFTP 客户端新增「停止时清理」选项，默认开启**——退出客户端页面自动调用 `/session/cleanup` 清空临时会话目录；偏好记忆在 `localStorage.ot_ftp_clean_on_exit`。
> ⑪ **端口扫描支持 1–65535 全量**——输入框提供「常用 / 1-1024 / 1-10000 / 全量 1-65535」预设按钮；扫描结果不受端口字典限制，**字典无记录的非常见端口（如 62764）照常扫出并显示**，只是不附带服务名。
> **稳定性加固**：FTP 服务端在 `os.remove` 抛出「无 errno 的 OSError」时不再崩掉整条控制连接（pyftpdlib 内部 `strerror(None)` 触发 TypeError），已兜底为标准 `550` 应答；FTP 客户端补上连接池失效自动重连与可读错误信息，不再出现空错误 `（）`。
>
> **20260805-V1 主要变更（7 项）**：① SSH/Telnet 批量执行增加 15 分钟显式超时与执行中状态文案，不再无限转圈；② FTP/SFTP 客户端改为类文件管理器，编码回退 `utf-8→gbk→gb2312→latin-1`，修复列出慢与 `550 Can't CWD`；③ 修复 FTP 下载 `401 未提供认证凭证`（`/session/download` 支持 `Bearer` 与 `?token=`，前端走 blob 取回）；④ 修复服务端「浏览服务器目录」按钮无反应；⑤ 服务端用户名/密码随机生成 + 空密码匿名 + 一键复制连接信息；⑥ 修复 WebDAV 浏览器打不开/不能上传（地址改用访问主机名、目录页含上传表单）；⑦ 客户端多选批量下载（递归打包为单个 zip）+ 批量删除，均带二次确认（新增 `/client/bulk/download`、`/client/bulk/delete`）。
> **SSH/Telnet 批量执行与终端：批量执行、交互终端、命令执行均走 **shell 通道**（`invoke_shell` + 逐行下发 + 静默判定结束），兼容华为/思科等仅支持 shell 通道的网络设备；超时兜底时保留已收到的部分输出，便于排查。前端每次执行前重置结果区，第二次执行结果正常显示，不会丢失第一次的输出。
> **多行命令与分页输出**：批量输入框按行下发且**保留空行**（如 `disp int brie`、空行、`1` 三行会原样依次发送，用于需要「回车确认 / 输入序号」的交互式命令）；设备输出遇 `---- More ----` / `--More--` 分页时**自动发送空格翻页**并拼接完整结果（最多 300 页），返回前统一剥离 ANSI 控制码（如 `\x1b[16D`）、退格、分页提示与行尾空白，输出干净可读，不再出现 `[16D` 之类乱码或只显示第一页的问题。
> **图片处理：选择新图片直接覆盖旧图（文件选择器默认只列图片类型）；后端 PIL 打不开的图片自动用 OpenCV `imdecode` 兜底解码，两者均失败时提示「无法识别的图片格式，支持 PNG / JPG / BMP / GIF / WebP」。图片→Base64 出结果文本框 + 「复制 Base64」按钮；Base64→图片粘贴框固定显示；产出图片的功能提供「下载图片」按钮（按目标格式自动命名扩展名）。**字节数一律「原始数值(常用单位)」双显示**（如 `10240(10.0KB)`）；**「体积变化」按实际增减给标签**——变小显示「减小 x%」，变大显示「增大 x%」并附无损格式提示，不会再出现「-4962.7% 减小」这类负数表述。
> 远程连接/传输（FTP/SFTP 文件管理器与合并服务端）、网络测试、二维码、图片压缩与格式转换等功能的接口与用法见下方各小节。

统一入口：`POST /api/opstoolbox/tool/run`，body `{tool, params}`；返回 `{success, message, data}`，`data.report` 为中文可读报告（真实换行）。**所有数据类模块（网络诊断/连通性/端口扫描/HTTP/SSL/Whois/IP 归属地/WOL/MAC-OUI/DNS、IP 工具箱、文字处理、图片处理、路由追踪）均同时展示「中文可读报告」与「原始数据(JSON)」折叠块**。

| 工具 | 关键参数 | 说明 |
| --- | --- | --- |
| `connectivity` | `{host, mode: icmp\|tcp\|udp, port?, count?, timeout?}` | `udp` 模式：收到 UDP 响应或 ICMP 端口不可达均判定可达；超时=开放或被过滤 |
| `traceroute` | `{host, max_hops?, timeout?, probes?, resolve_hostname?}` | V2 重写为 MTR 式：原生 socket TTL 逐跳探测，每跳 `probes` 枚探测包，返回 `hops[]`（ip/hostname/loss_percent/min/avg/max/rtts_ms）；`resolve_hostname=true` 反向解析主机名；无管理员权限自动回退系统 tracert（仅路径） |
| `totp_secret` | `{bytes?}` | 随机 Base32 密钥（TOTP 工具中心「生成随机密钥」按钮调用） |
| `totp_verify` | `{secret, code, digits?, period?}` | TOTP 校验（±1 时间窗容差） |
| `otpauth` | `{mode: build\|parse, ...}` | otpauth URI 生成/解析 |
| `html_entity`/`case_conv`/`ws_clean`/`line_sort`/`char_count` | 见页面表单 | 文字处理 5 项（输出区增加「输出结果」标识与复制按钮；V3 增加「原始数据(JSON)」） |

**通用工具SSE流式：**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/opstoolbox/tool/stream?tool=portscan&params={...}&token=` | 端口扫描流式：`text/event-stream` 每发现一个开放端口实时推送 `data: {port, open, scanned, total}`；扫描完成发送汇总 + `event: done`；**2000 端口上限（支持 1-65535 全量），前端关闭 SSE（点「停止」或离开页面）后端即中止扫描不再空转** |
| GET | `/api/opstoolbox/tool/stream?tool=connectivity&params={...}&token=` | **连通性探测流式：逐次推送探测结果 |
| GET | `/api/opstoolbox/traceroute/stream?host=&max_hops=20&timeout=1.5&probes=3&resolve_hostname=0&token=` | 路由追踪流式：`text/event-stream` 实时逐跳推送；token 通过 query 传递（EventSource 不能自定义请求头） |
| POST | `/api/opstoolbox/client/ssh/interactive` | **`{host, port, username, password, private_key?, timeout?(连接超时,默认30s)}` → `{success, session_id, banner}`；连接后 shell 通道保持打开供 WS/exec 复用 |
| WS | `/api/opstoolbox/client/ssh/ws/{session_id}?token=` | **WebSocket 终端桥：浏览器 xterm.js 与远端 shell 双向字节流直通（键盘全劫持透传）；文本 `{"resize":{cols,rows}}` 调整终端尺寸；断开 WS 不关闭 SSH 会话 |
| POST | `/api/opstoolbox/client/ssh/exec` | **`{session_id, command, timeout?(命令超时,默认15s，不含登录时间)}` → `{success, output, exit_code}`；走会话内持久 shell 通道（兼容网络设备） |
| POST | `/api/opstoolbox/client/ssh/disconnect` | SSH 断开：`{session_id}` → `{success, message}` |
| POST | `/api/opstoolbox/qrcode/decode` | **二维码识别：上传base64图片解码 `{image}` → `{success, text, texts[], count}` |

**网络测试（延迟/抖动/上传下载速度）：**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/opstoolbox/nettest/echo` | 轻量响应 `{ok, ts}`，前端循环请求取 RTT 计算延迟与抖动（相邻 RTT 差绝对值均值） |
| GET | `/api/opstoolbox/nettest/download?size=` | 返回 `size` 字节零字节流（默认 100MB，上限 10GB 防滥用）；服务端**分块传输（chunked，不声明 `Content-Length`）**，以规避浏览器 `net::ERR_CONTENT_LENGTH_MISMATCH` 中断，供前端测下载速度 |
| POST | `/api/opstoolbox/nettest/upload` | 流式读取请求体，返回 `{ok, received}`；**V14 前端改为普通请求体分片循环 POST**（浏览器对流式 body 强制 HTTP/2 而 uvicorn 为 HTTP/1.1，会触发 `ERR_ALPN_NEGOTIATION_FAILED`，故弃用 ReadableStream 请求体） |

> 网络测试全部在本地服务完成，不依赖外网；上传/下载大小默认 100MB，可在前端 1–10GB 间自定义，延迟测试时长可在 1–60 秒间自定义。

**运行日志、二维码多格式、正则/时间戳修复：**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| ~~GET~~ | ~~`/api/opstoolbox/logs`~~ | **已移除**（「运行日志」页面取消）：日志改由插件目录 `plugins/ops_toolbox/logs/plugin.log` 本地落盘 + 工具执行自动上报「系统设置-日志中心」（`GET /api/logs/audit` 可查） |
| POST | `/api/opstoolbox/logcenter/report` | **把一条日志发送到「系统设置-日志中心」，body `{action, detail, result: success\|failed}` → `{success}`（记录 action 前缀 `opstoolbox:`） |
| GET | `/api/opstoolbox/qrcode?text=` | 生成二维码 SVG（单文件，无需图片库） |
| POST | `/api/opstoolbox/qrcode/decode` | 上传 base64 图片识别二维码，支持 PNG / JPG / WEBP / SVG（SVG 自动栅格化） |

> V11 修复：正则测试「常用正则」列表点击行可直接把表达式填入输入框（此前点击无反应）；时间戳工具「日期 → Unix 秒」修复 dayjs 格式令牌（`yyyy-MM-dd` → `YYYY-MM-DD HH:mm:ss`）导致的 `NaN` 问题，现已可正常换算。

**FTP/SFTP 文件管理器与合并服务端：**

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/opstoolbox/fs/list?path=` | 服务端目录选择：浏览服务器文件系统，`path` 为空返回各磁盘/根，支持点选目录与上级目录（合并服务端页「浏览服务器目录」按钮调用） |
| POST | `/api/opstoolbox/session/upload` | 上传本地文件到临时会话目录（表单 `session_id`+`file`，供后续推到 FTP/SFTP 远端），返回 `{file, size}`（新增依赖 `python-multipart`） |
| GET | `/api/opstoolbox/session/files?session_id=` | 列出某临时会话目录下的文件 |
| GET | `/api/opstoolbox/session/download?session_id=&file=` | 从临时会话目录下载文件 |
| POST | `/api/opstoolbox/client/ftp/list` | FTP 远端列目录 `{host,port,username,password,tls?,remote_dir?,dir_raw?}` → `{data:{items:[{name,size,is_dir,mtime,raw,path_raw}], cwd}}`（目录在前、文件在后）；**文件名编码自动回退 `utf-8 → gbk → gb2312 → latin-1`**；**20260806-V1 起每条额外返回 `raw`（文件名原始字节 base64）与 `path_raw`（完整路径原始字节 base64）**，前端原样回传即可对中文名/历史乱码名做**字节级精确定位**，不再依赖字符串编码猜测 |
| POST | `/api/opstoolbox/client/ftp/upload` | FTP 上传 `{host,port,username,password,tls?,local_path,remote_path?,session_id,dir_raw?}`（`local_path` 为会话目录内文件名）→ `{success, message}`；`dir_raw` 为目标目录原始字节，**中文文件名按服务器协商编码原样写入，上传后列表不再乱码** |
| POST | `/api/opstoolbox/client/ftp/download` | FTP 下载 `{host,port,username,password,tls?,remote_path,session_id,path_raw?}` → 下载到临时会话目录；**优先用 `path_raw` 定位，修复中文/乱码名 `550 File does not exist`** |
| POST | `/api/opstoolbox/client/sftp/list` | SFTP 远端列目录（参数同上，`port` 默认 22，同样返回 `raw`/`path_raw`） |
| POST | `/api/opstoolbox/client/sftp/upload` | SFTP 上传（参数同上，支持 `dir_raw`） |
| POST | `/api/opstoolbox/client/sftp/download` | SFTP 下载（参数同上，支持 `path_raw`） |
| POST | `/api/opstoolbox/client/bulk/download` | **多选批量下载：`{protocol: ftp\|sftp, host, port, username, password, private_key?(sftp), tls?, remote_dir, dir_raw?, items:[{name,is_dir,raw,path_raw}], session_id}`；后端把勾选的文件/文件夹递归打包为**单个 zip** 落到临时会话目录，经 `GET /session/download` 取回；`items` 名称含 `/` `\` 或 `.`/`..` 会被拒绝（路径穿越防护）；**20260806-V1 起按 `path_raw` 逐字节定位，混选中文名 + 空格 + 多点扩展名也不会漏文件 |
| POST | `/api/opstoolbox/client/bulk/delete` | **多选批量删除：`{protocol, host, port, username, password, private_key?(sftp), tls?, remote_dir, dir_raw?, items:[{name,is_dir,raw,path_raw}]}`；文件直接删、目录递归删除后移除；**破坏性操作全程只执行一次 DELE，不做换编码重试**；失败条目在 `data.failed` 中返回「文件名（原因）」，控制连接被服务端中断时自动重连并二次确认删除结果，不再返回空错误 |
| POST | `/api/opstoolbox/server/start` | 启动文件服务端 `{type: ftp\|sftp\|webdav\|tftp, host?("0.0.0.0"), port?, username?, password?, root?, use_temp?(前端默认开), allow_write?(仅 tftp)}`；默认端口 ftp 2121 / sftp 2222 / webdav 8081 / tftp 69；`use_temp=true` 时根目录自动指向程序内临时隔离目录（每次启动独立 session，避免污染共享目录）；**密码留空即以匿名/免密方式开放**（FTP 匿名、WebDAV 无需认证、SFTP 空口令）；返回 `{success, server_id, port, root, type, temp_session}` |
| POST | `/api/opstoolbox/server/stop` | 停止指定文件服务端 `{server_id}`；若为临时隔离目录，停止时一并清理 |
| GET | `/api/opstoolbox/server/list` | 列出运行中的文件服务端 `{servers:[{server_id, type, port, alive, started_at, root}]}`（含 `root`，供前端展示连接信息） |
| GET | `/api/opstoolbox/server/files?server_id=` | **列出该服务端根目录下的文件/子目录** `{success, data:{root, items:[{name, is_dir, size}]}}`；后端已知 root，不受 `/fs/list` 白名单限制，Web 后台「服务器文件目录」表格即调用此接口 |
| GET | `/api/opstoolbox/server/connections?server_id=` | **查看运行中服务端的客户端连接信息（需求⑧，20260806-V1 新增）** → `{success, message, data:{active[], history[], total, hint, supported, server_id, type, port, root, started_at, alive}}`；`active` 为在线连接（peer 地址/登录用户/状态/连接时间/已连时长/收发字节/最近操作），`history` 为历史连接与事件（含**登录失败**记录，环形队列保留最近若干条），`hint` 给出该协议的连接语义说明（TFTP 为无连接 UDP、WebDAV 为 HTTP 短连接，故 `active` 常为空属正常）。`server_id` 不存在或服务端已停止时返回 `success:false` 与「服务端不存在或已停止」 |
| POST | `/api/opstoolbox/session/cleanup` | **清理临时会话目录 `{session_id}` → `{success}`；FTP/SFTP 客户端「停止时清理」（需求⑨，默认开启）在离开页面时自动调用 |

**服务端连接信息查看（需求⑧）**：「运行中的服务端」列表里**点击任意一行**即可展开该服务端的连接信息面板——上半部分「在线连接」实时显示每个客户端的来源地址、登录用户、当前状态、连接时刻、已连时长、上下行字节与最近一次操作（如「上传 报表.xlsx」「删除 old.log」）；下半部分「历史连接与事件」按时间倒序列出已断开的连接与**登录失败**记录，便于排查密码错误、暴力尝试等情况。TFTP 基于无连接 UDP、WebDAV 为 HTTP 短连接，面板会给出对应提示，此时「在线连接」为空属正常现象，请以「历史事件」为准。

**FTP/SFTP 客户端「停止时清理」（需求⑨）**：客户端页工具栏新增「停止时清理」勾选框，**默认开启**。开启后离开页面（切换菜单或关闭）会自动清空本次会话的临时下载目录，避免下载文件长期堆积占用磁盘；如需保留下载内容供后续查看，取消勾选即可，该偏好会被浏览器记住。

**服务端页使用要点**：启动成功后页面下方给出「连接信息卡」——协议、访问地址（如 `ftp://127.0.0.1:2121`、`sftp://…`、WebDAV 为 `http://…`）、用户名、密码、根目录，均可一键「复制全部连接信息」；密码留空时显示「(匿名)/(免密)」提示；WebDAV 额外提供「在浏览器中打开」按钮，浏览器直接访问会返回**目录列表页面**（不再出现「无该网页」）；同一张卡片内以表格实时展示服务器根目录下的文件与子目录。

> WebDAV 客户端（`clients/webdav.py`）已移除，仅保留 WebDAV 服务端（归入「FTP/SFTP/WebDAV/TFTP 服务端」合并页）；原独立 SFTP 客户端页取消，SFTP 功能并入「FTP/SFTP 客户端」（协议切换）；**「临时 HTTP 服务」已下线**（功能被 WebDAV 服务端覆盖，`type=temp_http` 会返回「不支持的服务端类型」）。图片「压缩和格式转换」工具 id 为 `img_compress_convert`（`POST /api/opstoolbox/tool/run`，参数 `quality`/`fmt`）。

### 4.10 CMDB 资产配置管理 `cmdb`

| 方法 | 路径 | 说明 | 鉴权 |
| --- | --- | --- | --- |
| GET | `/api/cmdb/dashboard` | 仪表盘统计（资产总数/IT数/机柜U位/即将过保/总原值） | 需登录 |
| GET | `/api/cmdb/assets` | 资产列表 `?page&size&search&category&exclude_category` | 需登录 |
| POST | `/api/cmdb/assets` | 新建资产（自动生成编号，可含 ports；支持 `inventory_time` 盘点时间字段，格式 `YYYY-MM-DD`；**支持 `config.system_info` 系统信息数组**，见下方说明） | 需登录 |
| GET | `/api/cmdb/assets/{id}` | 资产详情（含 ports、config、inventory_time；`config.system_info` 中密码返回解密明文） | 需登录 |
| PUT | `/api/cmdb/assets/{id}` | 更新资产（含 ports；可单独更新 `inventory_time`） | 需登录 |
| DELETE | `/api/cmdb/assets/{id}` | 删除资产 | 需登录 |
| POST | `/api/cmdb/assets/batch-update` | **批量更新盘点时间**：body `{ids:[int], inventory_time:"YYYY-MM-DD"}`；事务内更新选中资产的 `inventory_time` 与 `updated_at`，跳过不存在的 id，返回 `{success, updated}`；`inventory_time` 非法（非 YYYY-MM-DD）或 `ids` 为空返回 400 | 需登录 |
| GET | `/api/cmdb/assets/{id}/ports` | 端口列表 | 需登录 |
| PUT | `/api/cmdb/assets/{id}/ports` | 更新端口配置 | 需登录 |
| GET | `/api/cmdb/assets/import-template` | **下载 CSV 导入模板（UTF-8 BOM 附件，首部 `#` 注释逐列说明填写方法） | 需登录 |
| POST | `/api/cmdb/assets/import-csv` | **CSV 批量导入资产，body `{content: CSV文本}`；逐行校验（name 必填），返回 `{success, added, failed, errors[]}` | 需登录 |
| GET | `/api/cmdb/racks` | 机柜列表（含设备占用） | 需登录 |
| GET | `/api/cmdb/racks/{rack_id}` | 机柜详情（U位占用） | 需登录 |
| POST | `/api/cmdb/racks` | 新建机柜（`rack_id` 必填且不可重复，缺失/重复返回 400） | 需登录 |
| PUT | `/api/cmdb/racks/{rack_id}` | **更新机柜（名称/位置/总U数/状态/备注等，`rack_id` 本身不可改；不存在返回 404） | 需登录 |
| DELETE | `/api/cmdb/racks/{rack_id}` | 删除机柜；`?force=0`（默认）机柜内仍有已上架设备时返回 400（body 含 `devices` 数）；`?force=1` 先解绑下架内部设备（清空 `rack_id/u_start/u_height`，**资产台账保留**）再删；不存在返回 404 | 需登录 |
| POST | `/api/cmdb/assets/{id}/unbind-rack` | 将单台资产从机柜下架（清空 `rack_id/u_start/u_height`，**资产台账保留**），不影响资产本身 | 需登录 |
| GET | `/api/cmdb/maintenance` | 维保列表（即将到期/正常） | 需登录 |
| GET | `/api/cmdb/reports/export` | 报表导出 `?type=inventory|dept|warranty&format=html|csv` | 需登录 |
| GET | `/api/cmdb/backup/export` | **全量备份导出：下载含全部机柜/资产/端口的 JSON 文件（附件下载） | 需登录 |
| POST | `/api/cmdb/backup/import` | **备份导入/恢复：body `{content, mode}`；`content` 为备份 JSON 文本，`mode=merge`（默认，按资产编号/SN 合并）或 `overwrite`（先清空再导入） | 需登录 |
| POST | `/api/cmdb/demo-data/restore` | **手动恢复演示数据（20260806-V1 新增）：把内置的示例机柜/资产/端口重新写入数据库，供演示或初次体验使用。**仅在用户主动点击时执行，程序启动不会自动调用** | 需登录 |

#### CMDB 演示数据的播种规则（需求①，20260806-V1）

- **只在「全新安装、数据库尚未初始化」时播种一次**：首次启动写入内置示例机柜与资产后，会在 `meta` 表落一个 `demo_seeded=1` 标记；此后每次启动都先读该标记，**已标记则完全跳过播种逻辑**。
- 因此**你删掉的数据不会在重启后被重新添加回来**——无论是删掉部分资产、删光全部资产，还是把机柜也一并删空，重启后都保持你删除后的状态（实测：资产 0 + 机柜 0 → 重启 → 仍为 0）。
- **老版本数据库自动迁移**：从 20260806-V1 之前的版本升级上来时，若库里已有数据但缺少该标记，启动时会**补写标记而不重新播种**，同样不会出现「删了又回来」。
- 如果确实想要回演示数据（例如做演示或培训），调用 `POST /api/cmdb/demo-data/restore` 手动恢复，恢复动作完全由你控制。

#### CMDB 系统信息（仅 IT 资产）

- 新建/编辑 IT 资产时，表单含可折叠「系统信息」区，可添加多条记录，每条含：IP、登录方式（SSH/Telnet/Web/RDP/Console/其他）、端口、账号、密码、备注。
- **登录方式选「其他」时会出现「自定义方式」输入框**（字段 `custom_method`，20260806-V2 需求①），保存后详情页显示「其他(自定义值)」。
- **端口信息（仅 IT 资产）每条新增「MAC 地址 / IP 地址」列**（字段 `mac`/`ip`，20260806-V2 需求⑩），详情页端口表同步显示。
- **常用信息新增「颜色 / 存储大小 / 内存大小」三个字段**（`color`/`storage`/`memory`，20260806-V2 需求⑪）：资产列表页显示对应列，顶部搜索框可按颜色/存储/内存关键词**快速查询设备**；详情页「基础信息」区展示。
- 数据以 JSON 存于 `assets.config.system_info`（数组）；**密码入库前经 AES-256-GCM 加密**（与数通卫士同一套 `CryptoUtils`），加密值带 `enc:` 前缀且幂等（重复保存不会二次加密）。
- 脱敏策略：`GET /api/cmdb/assets`（列表）中密码一律返回 `******`；`GET /api/cmdb/assets/{id}`（详情）返回解密明文，前端详情页默认掩码显示、点击可切换明文。

#### CMDB U 位占用规则（20260729-严格校验）

- **U 位冲突拒绝：保存（新建/编辑）资产时，其 U 位区间 `[u_start, u_start+u_height-1]` 若与同一机柜内任一既有资产的 U 位区间重叠，直接返回 400 并提示「U位 X–Y 已被资产『名称』占用（A–BU），请选择其他U位」，**旧资产不会被覆盖、也不会被解除占位**。
- **U 高超限拒绝：资产 `u_start + u_height - 1` 不得超过所属机柜的 `total_u`，否则返回 400 并提示「U位 X–Y 超出机柜『名称』总U数（ZU），请调整起始U位或U高」。
- **机柜视图固定渲染高度：机柜视图始终按机柜 `total_u` 渲染 U 位格，不再随设备占用自动扩展到超出总 U（避免「48U 机柜被撑成 55U」）。
- 校验前提：`rack_id` 与 `u_start` 均填写才触发；`u_start=0` 视为非法（起始 U 位必须 ≥ 1）；U 高必须 ≥ 1。

#### CMDB 备份导出/导入说明

**用途：将所有设备（资产台账、机柜 U 位、端口与配置）一次性导出为单个 JSON 文件用于备份，可在需要时再导入恢复，实现配置迁移与灾备。

**导出：
- 入口：CMDB「报表中心」页的「数据备份与恢复」卡片，或「资产台账 / 机柜U位」列表页头部的「导出备份」按钮。
- 也可直接 `GET /api/cmdb/backup/export`，返回文件名形如 `cmdb_backup_YYYYMMDD_HHMMSS.json`。
- 导出内容结构：
 ```json
 {
 "meta": {"type": "cmdb-backup", "version": "20260804-V4", "exported_at": "...", "asset_count": 12, "rack_count": 3},
 "racks": [ {机柜全字段...} ],
 "assets": [ {资产全字段..., "ports": [ {端口...} ]} ]
 }
 ```

**导入（两种模式）：
- **合并更新 `merge`（默认，推荐）：按「资产编号（asset_no）」优先、其次「序列号（SN）」匹配已有资产——已存在则更新，不存在则新增；机柜按名称/编号 upsert。不会删除现有数据，适合日常增量恢复。
- **覆盖恢复 `overwrite`：先清空端口/资产/机柜三张表再导入，适合整机灾难恢复。**该模式不可逆**，Web 端点击时会二次确认。
- 返回体示例：`{"success": true, "mode": "merge", "added": 2, "updated": 10, "skipped": 0, "racks_added": 0, "racks_updated": 3, "errors": [], "total_after": 12}`。
- 前端上传遵循框架惯例：读取文件文本后以 `{content: 文本, mode}` 作为 JSON body 提交（非 multipart）。

> 各插件（数通卫士、运维工具箱、CMDB）还提供各自的业务接口，详见插件目录下的开发项目书（`wiki/10-插件项目书-数通配置卫士.md`、`wiki/10-插件项目书-运维常用工具箱.md`、`wiki/10-插件项目书-CMDB.md`）。

---

## 本期修复（20260820 第十批 / 框架 20260820-V1 / 数通配置卫士 20260820-V2 / 运维常用工具箱 20260820-V2 / CMDB 20260820-V1）

> 本轮聚焦 6 项 bug/变动需求（①~⑥）。版本号：框架 `20260820-V1` 不变（改动均在插件层）；数通配置卫士 `20260820-V1 → 20260820-V2`（通知中心列序）；运维常用工具箱 `20260820-V1 → 20260820-V2`（DNS 崩溃修复、SSH 终端样式、Telnet 双模式与全局超时）；CMDB `20260820-V1`、Wiki `20260815-V1` 不变。

1. **数通配置卫士通知中心列序（需求①）**：`notifications.js` 列序改为「时间 → 标题 → 内容 → 等级 → 渠道 → 状态」（时间列为第一列）；「级别」标签改「等级」（`prop="level"` 不变）；「操作」（查看详情）保留最右，其余列相对顺序不受影响。
2. **DNS 探测打开即跳回系统概览修复（需求②，根因修复）**：`tools_01_net_11_dns.js` 模板把 `常用 ${modeLabel} 服务器` 写在了 JS 模板字符串（反引号）内——`${modeLabel}` 在**模块加载时**被当作 JS 插值立即求值，而 `modeLabel` 是对象内后定义的 computed，加载时作用域不存在 → `ReferenceError: modeLabel is not defined` → 模块加载即崩、页面未注册 → 点击「DNS 探测」回退系统概览（浏览器控制台 44 行报错已证实）。改为 Vue mustache `{{ modeLabel }}`，一行修复。
3. **SSH 交互终端底部留白加大（需求③）**：主交互终端、批量内嵌终端、弹窗终端三处容器底部留白 `24px → 34px`，最末行光标 `_` 不再被裁掉看不见。
4. **SSH 交互终端固定宽度+自动折行（需求④，方案A）**：终端容器维持固定宽度（`max-width:1000px`），依赖 xterm 原生自动折行——命令超过宽度时自动「掉头」换到下一行显示剩余内容、不截断；不引入横向滚动条（xterm 模型不支持，方案 A 为稳健选择）。
5. **Telnet 新增「交互终端/批量执行」双模式（需求⑤，与 SSH 一致）**：
   - 后端：`clients/telnet.py` 新增 `telnet_connect()`（连接→协商→登录→保持 socket 打开，会话存 `_telnet_sessions`）与 `telnet_disconnect()`；`routes/ssh.py` 新增 `POST /api/opstoolbox/client/telnet/interactive`（建会话返 `session_id`+`banner`）、`WS /api/opstoolbox/client/telnet/ws/{sid}`（xterm↔socket 双向桥，读时经 `_negotiate` 剥离 IAC 并回应对端、会话锁内发送防写冲突）、`POST /api/opstoolbox/client/telnet/disconnect`。
   - 前端：`ssh_terminal.js` 协议选 Telnet 时显示「模式」单选（交互终端/批量执行）；交互终端 → 连接 → 建立 Telnet 会话 → 打开 xterm 网页终端（键盘直通，与 SSH 一致）；批量执行 → 原命令框 + 执行。
6. **Telnet 批量执行卡死修复（需求⑥，根因修复）**：`telnet_exec` 命令循环此前仅靠「静默 1.5s」判定完成——若设备持续下发 IAC 协商字节，`recv` 每 <0.2s 有数据、idle 永不满足 → while True 死循环，前端永远显示「正在执行 Telnet 命令」。现增加**全局墙钟超时**（以入参 timeout 为整段会话上限），任意时刻超时即强制收尾并返回已收集输出（`truncated=true` 注明截断）。验证：mock「协商风暴」服务器持续下发 IAC，修复版在超时预算内返回（旧实现永久卡死）；正常回显无 IAC 字节污染；真实设备 `10.10.201.121:23` 无凭证连接存活 `success=True`（0.9s 返回）。
7. **版本号**：运维常用工具箱 `routes/common.py` `PLUGIN_VERSION`、数通配置卫士 `plugin.py`、`notifications.js`/`dns.js` `JS_VERSION` 升 `20260820-V2`；框架 `SYSTEM_VERSION`/`FRAMEWORK_VERSION`/`index.html`、CMDB、Wiki 不变。

---

## 本期修复（20260822 第十二批 / 运维常用工具箱 20260822-V1）

> 本轮聚焦「2 项修复/需求（①②）」。版本号：运维常用工具箱 `20260821-V2 → 20260822-V1`（跨天重计）；框架、数通配置卫士、CMDB、Wiki 未改动，版本不变。

1. **① DNS 探测-常用-国内 IPv4 精简**：`tools_01_net_11_dns.js` 删除 `182.254.116.116（腾讯）`、`211.136.17.107（移动）`，列表剩 7 项。
2. **② CLI 终端双 div 布局（自适应分辨率）**：`ssh_terminal.js` 终端盒（`termbox`/`dlgTermbox`/`termBox_`）改为 `nc-term-box`（flex 居中、黑底 #000、移除固定 padding）；`.xterm` 占宽/高 **90%**，四周各 5% 纯黑留空（百分比自适应，不做其他处理）；**隐藏 xterm 原生滚动条**（`scrollbar-width:none` + `::-webkit-scrollbar{display:none}`），滚动功能保留（鼠标滚轮/触控板滑动）；fit 后**行数减 2** 使底部直接空出 2 行，末行光标 `_` 不被底栏/盒缘遮挡。
3. **版本号**：运维常用工具箱 `routes/common.py` `PLUGIN_VERSION` 升 `20260822-V1`；`tools_01_net_11_dns.js`、`ssh_terminal.js` `JS_VERSION` 升 `20260822-V1`；`index.html` `meta[nc-asset-version]` 升 `20260822-V1`；框架 `SYSTEM_VERSION` 未动（无框架改动）；EXE 版本戳经 `build.py --version 20260822-V1` 写入「详细信息」。

## 本期修复（20260821 第十一批 / 框架 20260821-V1 / 运维常用工具箱 20260821-V2）

> 本轮聚焦「6 项修复/需求（①②③④⑤⑥）」。版本号：框架 `20260820-V1 → 20260821-V1`（需求①改框架前端）；运维常用工具箱 `20260821-V1 → 20260821-V2`（需求②③④⑤⑥改插件前端，同日递增）；数通配置卫士、CMDB、Wiki 未改动，版本不变。

1. **① 基础设置「保存设置」按钮靠左**：`frontend/pages/core/basic-settings.js` 按钮外层容器 `text-align:right` → `text-align:left`，按钮移至左侧。属框架前端改动，框架版本 `SYSTEM_VERSION` 升 `20260821-V1`。
2. **② DNS 探测-常用服务器-海外拆分**：`tools_01_net_11_dns.js` 原 `8.8.8.8 / 8.8.4.4（Google）` 拆分为 `8.8.8.8（Google）`、`8.8.4.4（Google）` 两项，点击填入各得单 IP。
3. **③ DNS 探测-常用服务器-国内 DoT 调整**：`dot.pub` 标注由「公钥」改为「腾讯」；删除 `dot.360.cn（360）`。
4. **④ DNS 探测-常用服务器-国内 DoH 调整**：`https://doh.pub/dns-query` 标注由「公钥」改为「腾讯」（DoH 未提删除，`doh.360.cn` 保留）。
5. **⑤ CLI 终端三区域视觉隔离**：`ssh_terminal.js` 终端挂载盒（`termbox`/`dlgTermbox`/`termBox_`）改纯黑 `#000` + 四周 `padding:12px` 留空并居中；`.xterm-viewport.nc-xterm-scrollbar` 右侧 15px 滚动条槽 + 左侧分隔线 `border-left`；`.xterm` 底部边界线；`.xterm-rows` 底部留 2 行空白使末行光标 `_` 可见。滚动条落入黑底留空区、不压文本，主内容/滚动条/底部三区域视觉独立。
6. **⑥ Telnet 批量执行隐藏「主机/IP」表单项**：`ssh_terminal.js` 该表单项 `v-if` 由 `protocol==='telnet'` 改为 `protocol==='telnet' && telnetMode==='interactive'`，仅交互模式显示，批量模式只保留「主机列表」。
7. **版本号**：运维常用工具箱 `routes/common.py` `PLUGIN_VERSION` 升 `20260821-V2`；`tools_01_net_11_dns.js` `JS_VERSION` 升 `20260821-V1`；`ssh_terminal.js` `JS_VERSION` 升 `20260821-V2`；框架 `SYSTEM_VERSION` 升 `20260821-V1`；`index.html` `meta[nc-asset-version]` 为 `20260821-V1`；EXE 版本戳经 `build.py --version 20260821-V1` 写入「详细信息」。

## 本期修复（20260821 第十批 / 运维常用工具箱 20260821-V1）

> 本轮聚焦「4 项修复/需求（①②③④）」。版本号：运维常用工具箱 `20260820-V1 → 20260821-V1`（跨天重计）；框架 `20260820-V1`、数通配置卫士、CMDB、Wiki 未改动，版本不变。

1. **DNS 探测 DoT 模式支持主机名（需求①，根因修复）**：`plugins/ops_toolbox/tools/dns.py` 的 `dot` 分支原把「指定 DNS」直接作为 `dnspython.query.tls(where)` 的 `where`，而 dnspython 2.8.x 的 `where` 仅接受 IP 字面量，对主机名（如 `dns.alidns.com`）抛无参 `ValueError`，被外层捕获后只显示空文本的「DNS 探测失败（dot）：」。现先 `socket.getaddrinfo` 解析主机名→IP 再发起 TLS 查询（已是 IP 则跳过解析）；解析失败给出明确报错（如 `DoT 服务器解析失败（no-such-host.invalid）：...`）。验证：`dns.alidns.com` → `success:true` 并回显 A 记录；无效主机名 → `success:false` 且 message 含具体解析原因（不再空文本）。
2. **SSH 交互终端滚动条隔离 + 光标留白（需求②③，视觉修复）**：`plugins/ops_toolbox/frontend/ssh_terminal.js` 注入全局 CSS——`.xterm .xterm-rows` 加 `padding-bottom:2em`（末行命令光标 `_` 不被底部裁切、预留 2 行空白）；`.xterm-viewport` 加 `nc-xterm-scrollbar` 类并 `right:15px`（滚动条右侧预留 15px 槽位，不再压住长命令输出）。`mountTerm`/`_mountEmbed` 在 `term.open` 后给 `.xterm-viewport` 加该类并重适配 `fit.fit()`。
3. **Telnet 协议-批量执行对标 SSH（需求④，功能补齐）**：后端 `clients/telnet.py` 新增 `telnet_batch`（并发线程池 + 逐台登录 + 多行命令 + 静默判定 + 分页自动翻页），与 `ssh_batch` 同构；`routes/ssh.py` 的 `/client/telnet` 改为 `hosts` 为列表时走 `telnet_batch`、否则保持原 `telnet_exec`（向后兼容）。前端新增 Telnet 批量主机列表表单（与 SSH 批量共用 `batchCommand`），结果内嵌终端、点击主机进入交互终端等体验与 SSH 批量完全一致。验证：Telnet 批量（hosts 列表）走 `telnet_batch` 返回 `results` 结构（含 host/port/user/output/success/error），无 500；Telnet 单主机向后兼容走 `telnet_exec`，无 500。
4. **版本号**：运维常用工具箱 `routes/common.py` `PLUGIN_VERSION` 与 `ssh_terminal.js` `JS_VERSION` 统一升 `20260821-V1`；框架 `SYSTEM_VERSION`、数通配置卫士、CMDB `plugin.py`、Wiki 未改动；`index.html` `meta[nc-asset-version]` 随插件升版升 `20260821-V1`；EXE 版本戳经 `build.py --version 20260821-V1` 写入「详细信息」。

---

## 本期修复（20260820 第九批 / 框架 20260820-V1 / 数通配置卫士 20260820-V1 / 运维常用工具箱 20260820-V1 / CMDB 20260820-V1）

> 本轮聚焦「11 项 bug/体验修复（①~⑪）」。版本号：框架 `20260819-V1 → 20260820-V1`（跨天重计）；数通配置卫士 `20260818-V5 → 20260820-V1`（通知中心去 ID 列）；运维常用工具箱 `20260819-V1 → 20260820-V1`；CMDB `20260818-V5 → 20260820-V1`（仪表盘表头排序/筛选）；Wiki `20260815-V1` 不变。

1. **表头文字点击即可排序（需求①）**：`frontend/ui/framework.js` 的 `nc-sf-th` 组件 label 加 `@click="sortKey ? toggleSort() : null"`——点击列名文字即触发排序（与右侧排序箭头等价）；无 `sort-key` 的列保持纯展示。
2. **CMDB 仪表盘表头排序+筛选（需求②）**：「最近等级资产」表的「名称/子类」(name)、「位置」(location)、「状态」(status) 三列均改用配对 `nc-sf-th`（`sort-key`+`filter-key` 同组件），支持点名排序与按值筛选；排序/筛选以 `name` 字段为准。
3. **数通配置卫士通知中心移除 ID 列（需求③）**：删除通知列表的「ID」列（含其 `nc-sf-th`），表格更紧凑。
4. **排序/筛选统一成对（需求④）**：所有 `nc-sf-th` 的排序 SVG 与筛选 SVG 必须位于同一组件 div 内（label + sort + filter 同 `nc-sf-th`），禁止把筛选图标拆到独立元素，确保表头语义完整、自检一致。
5. **运维工具箱取消「原始数据(JSON)」模块（需求⑤）**：`tools_01_net_00_base.js` 的 `netTool` 新增第 7 参数 `noRaw`，原始数据折叠块与 fallback `<pre>` 均加 `v-if="${!noRaw} && ..."`；WOL（`tools_01_net_09_wol.js`）与 MAC/OUI 厂商（`tools_01_net_10_macoui.js`）注册时传 `true`，不再展示 JSON 原始数据。
6. **DNS 探测按方式显示常用服务器（需求⑥-⑧）**：`tools_01_net_11_dns.js` 重写——弃用 `netTool` 改为自定义页，按 `plain/dot/doh` 三档分别列出国内常用服务器（阿里/腾讯/114/百度/电信/移动；DoT：dns.alidns.com/dot.pub/dot.360.cn；DoH：https://dns.alidns.com/dns-query 等），点击直接填入「指定 DNS」（去括号说明，DoH/DoT 保留协议前缀）；切换服务器方式时自动清空带 `://` 前缀的地址，避免跨方式误带入。
7. **SSH 交互模式主机/IP 文本框置空（需求⑨）**：交互模式「主机/IP」输入框去除 `placeholder="192.168.1.10"`，默认空、无占位提示（避免与真实值混淆）。
8. **SSH 交互终端底部留空（需求⑩）**：主交互终端、批量内嵌终端、弹窗终端三处容器统一加 `padding-bottom:24px;margin-bottom:12px`，防止终端内容被页面底部元素遮挡。
9. **Telnet 像 SSH 一样可用（需求⑪，根因修复）**：
   - 根因：后端 `clients/telnet.py` 此前用裸 socket，未处理 Telnet 协议协商（IAC 字节）。真实设备（华为/华三/思科等）连接建立后立即下发 `DO/WILL` 协商，客户端若不回应，服务端等待超时后主动 RST 关闭连接，前端表现为 `WinError 10054` / 旧版误报「本次执行无输出」。
   - 后端：`telnet.py` 新增 `_negotiate()` 解析 IAC 序列——对服务端 `DO X` 回 `WONT X`、对 `WILL X` 回 `DONT X`、忽略子协商（`SB`），并把控制字节从应用数据剥离；登录前/后 `drain` 阶段均走 `_negotiate` 完成握手，服务端不再因「无响应」断开。
   - 前端：`ssh_terminal.js` Telnet 分支先判 `body.success === false`，为真时直接 `this.$message.error(body.message)` 并显示真实错误，不再吞掉异常误报「无输出」。
   - 验证：单元测试用 mock Telnet 服务端（下发协商后等待回应，未回应则 RST）对比——修复版完成握手并返回输出、朴素版被 RST（`WinError 10053/10054`）；并在真实设备 `10.10.201.121:23` 上做无凭证连接存活探针，`success=True`（连接未被重置）。
10. **版本号**：框架 `SYSTEM_VERSION`、`index.html ?v=`/`meta[nc-asset-version]`、`framework.js` `FRAMEWORK_VERSION`、12 个前端 `JS_VERSION` 盖章、运维常用工具箱 `routes/common.py` `PLUGIN_VERSION`、数通配置卫士/CMDB `plugin.py` 版本统一升 `20260820-V1`；Wiki `20260815-V1` 不变。

---

## 本期修复（20260819 第八批 / 框架 20260819-V1 / 数通配置卫士 20260818-V5 / 运维常用工具箱 20260819-V1 / CMDB 20260818-V5）

> 本轮三项：① DEBUG 改为**按页面输出当前模块 JS 版本**（取消打开网站即输出全部 JS 信息）；② 底层**取消一切 cookie / 浏览器存储缓存**（axios 禁 XSRF-cookie、fetch 禁 cookie、删除 ops 全部表单参数记忆、删除时区 localStorage 持久化）；③ 运维工具箱交互优化（DNS 探测恢复常用 DNS 提示、主机/IP 浅色占位默认值补齐）。版本：框架/运维常用工具箱 `20260818-V5 → 20260819-V1`（跨天重计）；数通配置卫士/CMDB 代码未变保持 `20260818-V5`（仅前端 JS_VERSION 盖章常量同步为 V1，避免版本自检误报）。

1. **DEBUG 输出当前页面模块 JS 版本（需求 1）**：
   - `frontend/app.js`：删除启动时的「各模块 JS 版本」全量输出与 crypto-key 回调中的「JS版本：」追加（不再打开网站就显示）；改为在 `watch currentComponent` 中，DEBUG 开启且进入/切换页面时输出该页面模块的 JS 版本：`[NCDBG] [app] [NC] 当前页面 guardian_devices JS 版本：20260819-V1`；页面未盖章（可能旧缓存）时提示按 Ctrl+F5。
2. **底层取消一切 cookie / 浏览器存储缓存（需求 2）**：
   - `frontend/ui/framework.js`：`axios.create` 显式 `withXSRFToken:false / xsrfCookieName:null / xsrfHeaderName:null / withCredentials:false`——不再读取浏览器 XSRF-TOKEN cookie、不携带凭证 cookie（后端经审计本就零 `Set-Cookie`）。
   - `ops_toolbox/frontend/nettest.js`：上传/下载两处原生 `fetch` 加 `credentials:'omit'`。
   - `ops_toolbox` 全部表单参数记忆删除：`tools_01_net_00_base.js`（netTool 保存/回填）、`tools_01_net_01_connectivity.js`、`tools_01_net_03_portscan.js`、`ssh_terminal.js`（含 SSH 用户名明文）、`tools_02_ftp_client.js`（清理偏好）。**所有诊断工具每次打开表单均为空白**（default/placeholder 兜底），页面不残留任何历史输入。
   - 时区不再持久化：删除 `localStorage.nc_timezone` 全部读写；`fmtTime` 恒按浏览器当前时区转换；基础设置「时区」选项保留并显示浏览器当前时区（登录自动更新时区天然满足）。
   - 保留项：登录态 `nc_token`（localStorage，非 cookie，取消会导致刷新即掉登录）；WebSocket 握手 cookie 由浏览器强制携带，但后端不 Set-Cookie 故实际零 cookie。
3. **运维工具箱交互优化**：
   - DNS 探测「指定 DNS」文本框下方恢复提示文字（浅灰小字）：「留空使用系统默认 DNS。国内常用：223.5.5.5（阿里）、119.29.29.29（腾讯）、114.114.114.114（114DNS）；海外：8.8.8.8（Google）」；文本框值仍默认空白（keepEmptyWhenBlank，空白即系统默认）。
   - 主机/IP 类文本框浅色占位默认值补齐：SSL 证书检查 host `www.baidu.com`、Whois target `www.baidu.com`、IP 归属地 ip `8.8.8.8`、DNS 探测 domain `www.baidu.com`（HTTP 探测/连通性/端口扫描已有）；输入时自动隐藏占位，留空按默认值执行。
4. **版本号**：框架 `SYSTEM_VERSION`、`index.html ?v=`/`meta[nc-asset-version]`、`framework.js` `FRAMEWORK_VERSION`、运维常用工具箱 `tools_00_common.js` `JS_VERSION` 与 `routes/common.py` `PLUGIN_VERSION` 统一升 `20260819-V1`；数通配置卫士/CMDB `plugin.py` 版本保持 `20260818-V5`（代码未变），前端 JS_VERSION 盖章常量同步为 V1。

---

## 本期修复（20260819 第七批 / 框架 V5 / 数通配置卫士 V5 / 运维常用工具箱 V5 / CMDB V5）

> 本轮两项：① 重启后首屏「只有文字无 UI」（`index.css` `ERR_TOO_MANY_RETRIES`）根因修复；② DEBUG 增强——浏览器控制台列出 JS/模块版本（防旧缓存加载）。版本：框架 `20260818-V3 → V5`（`index.html ?v=` 同步升 V5）；数通配置卫士 `20260818-V3 → V5`、CMDB `20260818-V1 → V5`（前端显式 JS_VERSION 盖章）；运维常用工具箱保持 V5；Wiki `20260815-V1` 不变。

1. **首屏白屏修复（Part A）**：
   - `frontend/index.css` 内联进 `frontend/index.html` `<head>` 的 `<style>` 块，不再单独请求 `/assets/index.css`——消除首屏对独立样式表网络请求的依赖，即使 TLS 首请求异常也不可能因样式表加载失败而白屏（原 index.css 文件保留在源码树，已不再被引用）。
   - `main.py` uvicorn 显式 `http="h11"`（原默认 httptools），规避 HTTPS 首请求 keep-alive/连接重置触发的浏览器 `ERR_TOO_MANY_RETRIES`（该错误即白屏的浏览器侧表现）。
   - 根因结论：非证书/端口时序问题（证书与静态资源在监听前已就绪、`/assets` 后续全 200），而是启动「卡死」窗口内首个到达的 index.css 请求被浏览器重试耗尽；内联后该请求不再存在。
2. **DEBUG 显示 JS/模块版本（Part B）**：
   - `index.html` 新增 `<meta name="nc-asset-version" content="20260818-V5">`（资源版本单一真源，与全部 `?v=` 同步）。
   - `frontend/app.js`：DEBUG 开启时版本行显示 `[NCDBG] [app] [NC] NetCore Framework 内置版本：20260818-V5 JS版本：20260818-V5`；并额外输出「各模块 JS 版本」表（逐模块 `id: 版本`）。
   - 每个模块 JS 显式盖章版本号：数通配置卫士 6 个前端页、CMDB 5 个页面 + 3 个共享组件均加 `JS_VERSION="20260818-V5"` 并盖章进 `NC.jsVersions`（运维常用工具箱已有同机制）；框架 core 页由 `framework.js` 统一盖章。
   - 修复 `frontend/ui/framework.js` `NC.FRAMEWORK_VERSION` 硬编码漂移（`20260817-V3` → `20260818-V5`，与 `SYSTEM_VERSION` 对齐），消除 app.js 启动自检误报「请清除浏览器缓存」。
3. **版本号**：框架 `SYSTEM_VERSION` `20260818-V3 → V5`；`index.html ?v=` `V4 → V5`；数通配置卫士 `plugin.py` `20260818-V3 → V5`；CMDB `plugin.py` `20260818-V1 → V5`；运维常用工具箱保持 V5；Wiki 不变。

---

## 本期修复（20260819 第五批 / 框架 V3 / 数通配置卫士 V3 / 运维常用工具箱 V5 / CMDB V1）

> 本期仅改运维常用工具箱前端（`tools_01_net_11_dns.js`）与版本号（`common.py` PLUGIN_VERSION、`tools_00_common.js` JS_VERSION）；框架 core、数通配置卫士、CMDB 未改动，按「变动才升版」规则仅运维常用工具箱升 `20260818-V5`（`index.html` 核心资源 `?v=` 未升——插件前端经 `/plugin-assets` 以 `?v=<mtime>` 加载，改动后浏览器自动刷新，无需破缓存）。需求①（首次运行生成 TLS 证书与端口监听顺序）经核实源码：证书在 `main.py` bind/serve 前同步生成、静态资源在模块导入期已从 `_MEIPASS` 解包落盘，竞态不存在，未改动代码；历史「首屏只剩文字」为 20260818 自签证书 SAN 不含访问 IP 导致 `/assets` 被拦截（同轮已修复）。

1. **DNS 探测「指定 DNS」文本框移除提示文字**：`tools_01_net_11_dns.js` 的 `nameserver` 字段原带 `hint`（输入框下方长提示「留空使用系统默认 DNS。常用 · ...」），已删除该 `hint` 一行；字段本就无 `default`、无 `placeholder`，现文本框默认完全空白、无任何提示文字（保留 `keepEmptyWhenBlank:true`，空白即代表使用系统默认 DNS）。
2. **运维常用工具箱版本号升 V5**：`common.py` `PLUGIN_VERSION` 与 `tools_00_common.js` `JS_VERSION` 由 `20260818-V4` 升 `20260818-V5`。

---

## 本期修复（20260818 第四批 / 框架 V3 / 数通配置卫士 V3 / 运维常用工具箱 V4 / CMDB V1）

> 本期仅改运维常用工具箱前端（`tools_01_net_01_connectivity.js`），未触达框架 core、数通配置卫士、CMDB；按「变动才升版」规则，仅运维常用工具箱升 `20260818-V4`，`index.html` 核心资源破缓存 `?v=` 同步升 `20260818-V4`。DNS「指定 DNS」文本框空白在上轮（V3）已落实，本轮回归确认，无代码改动。

1. **探测明细「序号」列取消排序与筛选**：连通性探测（ICMP/TCP/UDP 模式）的「探测明细」表中「#」序号列原为 `nc-sf-th label="#" sort-key="probe" filter-key="probe"`，同时渲染排序与筛选图标；序号为自增序号、无可枚举筛选值，已改为纯静态表头 `<nc-sf-th label="#"></nc-sf-th>`（无 sort-key/filter-key，组件本身不渲染图标）。
2. **MTR 信息「跳数」列取消排序**：路由追踪(tracert) 逐跳 MTR 表的「跳数」列原为 `nc-sf-th label="跳数" sort-key="hop"`，渲染排序图标（无筛选）；跳数为固定序号，已改为纯静态表头 `<nc-sf-th label="跳数"></nc-sf-th>`。
3. **DNS 探测「指定 DNS」文本框确认空白（回归）**：该字段上轮（V3）已移除 placeholder、且从无 default，文本框默认空白即代表使用服务器自身 DNS；本轮仅做回归确认，无代码改动。

---

## 本期修复（20260818 第三批 / 框架 V3 / 数通配置卫士 V3 / 运维常用工具箱 V3 / CMDB V1）

> 框架 `SYSTEM_VERSION` 升 `20260818-V3`（本期改了 `basic-settings.js` 等 core 前端，属 core 改动，按规则必须升）；数通配置卫士、运维常用工具箱同步升 `20260818-V3`；CMDB 本轮未改动，维持 `20260818-V1`。`index.html` 核心资源破缓存 `?v=` 同步升 `20260818-V3`。

1. **通知中心「内容」列取消排序**：该列文本无法枚举，原排序无意义，已移除排序（保留为静态表头）。MTR 逐跳表无「内容」列，故不适用。
2. **DNS 探测「指定 DNS」默认空白 = 系统 DNS**：移除该文本框的自带 placeholder 内容，默认空白即代表使用服务器自身 DNS（后端 `nameserver` 为空时走系统 DNS，已验证）。
3. **基础设置删除原「保存设置」按钮**：原卡片内保存按钮移除，功能迁至页面底部统一保存（见第 5 项）。
4. **基础设置新增「TOTP认证」卡片**：新建「TOTP认证」卡片，将「TOTP 双因素认证」开关（改名为「TOTP设置」）与「TOTP 双因素认证绑定」子节一并移入，组成完整 TOTP 模块。
5. **基础设置页底新增统一「保存设置」按钮**：页面底部新增保存按钮，点击后统一写入「基础设置」全部配置（含软件名/版本/自动退出/时区/TOTP 开关/证书 SAN 地址）与 HTTPS 开关（通过 `PUT /api/system/basic-settings` + `POST /api/system/https/switch`）；HTTPS 两个开关不再即时写入，改为统一保存（HTTPS 开关需重启服务生效）。
6. **DNS 探测提示文字改为国内 DNS**：「指定 DNS」字段下方常驻提示文字由原来的含国外 DNS（Google 8.8.8.8 / Cloudflare 1.1.1.1 / dns.google）改为仅腾讯与阿里云（普通 DNS 223.5.5.5(阿里) / 119.29.29.29(腾讯)；DoT 223.5.5.5 / 119.29.29.29；DoH https://223.5.5.5/dns-query / https://doh.pub/dns-query）。

---

## 本期修复（20260818 第二批 / 框架 V2 / 数通配置卫士 V2 / 运维常用工具箱 V2 / CMDB V1）

> 框架 `SYSTEM_VERSION` 升 `20260818-V2`（本期改了 `framework.js` 的 `nc-sf-th` 筛选图标配色，属 core 改动，按规则必须升）；数通配置卫士、运维常用工具箱同步升 `20260818-V2`；CMDB 本轮未改动，维持 `20260818-V1`。`index.html` 核心资源破缓存 `?v=` 同步升 `20260818-V2`。

1. **设备管理「数据加载失败：r is not defined」修复**：根因为 `devices.js` 的 `load()` 在引入「派生连接状态字段」时漏写 `const r = await http.get('/api/guardian/devices', { params })`，直接引用未定义的 `r` 触发 `ReferenceError` 被 catch 显示「数据加载失败」。修复：补回拉取请求，设备列表正常渲染。
2. **筛选图标筛选后变色**：`nc-sf-th` 的筛选漏斗图标在 `vals.length>0`（已筛选）时由灰（`#909399`）变为主题蓝（`#409eff`），一眼可见是否处于筛选态。全局所有表头生效。
3. **通知中心「内容」列取消筛选**：该列文本无法枚举，原筛选无意义，已移除筛选（保留排序）。
4. **连通性探测-tracert「跳」列改名「跳数」并取消筛选**：MTR 逐跳表的「跳」列重命名为「跳数」，并移除该列筛选（IP 地址、主机名列保留筛选）。
5. **DNS 探测「指定 DNS」默认系统 + 字段下方显示常用服务器**：后端 plain 模式 `nameserver` 为空时已使用系统 DNS（无需改动）；前端在「指定 DNS」字段下方新增常驻提示文字，列出常用普通 DNS / DoT（端口 853）/ DoH 端点（如 223.5.5.5、119.29.29.29、8.8.8.8、1.1.1.1、https://dns.google/dns-query、https://doh.pub/dns-query 等），placeholder 同时提示「留空用系统」。

---

## 本期修复（20260818 / 框架 V1 / 数通配置卫士 V1 / 运维常用工具箱 V1 / CMDB V1）

> 框架 `SYSTEM_VERSION` 维持 `20260818-V1`（与 HTTPS SAN 修复为同一版，不单独升 V2）；数通配置卫士 / 运维常用工具箱 / CMDB 本次均有前端与后端改动，统一升 `20260818-V1`。

1. **表单「清除」按钮清不掉筛选修复**：`nc-sf-th` 的 `clearFilter` 现在派发 `filter` 事件（vals 为空数组），父组件收到后立即清空该列筛选条件，列表恢复全量。
2. **连接状态筛选框显示值与列表一致**：数通配置卫士设备管理-设备列表「连接状态」列后端派生 `conn_status`（禁用/正常/失败/未知）中文，筛选框枚举与显示完全对齐，不再暴露 `green/red` 原始枚举。
3. **「最后采集」筛选对齐显示**：该列 `nc-sf-th` 增加 `:value-formatter="fmtTime"`，筛选候选值显示与列相同的「日期+时分秒」格式。
4. **列显示什么筛选框就显示什么**：`nc-sf-th` 新增 `valueMap` / `valueFormatter`，筛选项标签可映射为中文/自定义文案，匹配仍用原始值（如设备详情结果列「成功/失败」）。
5. **CMDB / 通知中心 / 任务页操作列随滚动条拖拽**：移除相关表格操作列的 `fixed="right"`（原固定列机制使其脱离横向滚动容器、无法随其他列移动），操作列现在与其他列一起随横向滚动条移动。
6. **网络拓扑-设备详情表头加排序/筛选**：链路汇总、链路明细、消失链路、发现明细四张表全部接入 `nc-sf-th`（排序 SVG + 筛选 SVG）。明细表按表独立维护排序/筛选状态，互不串扰；汇总视图的「端口数/本端端口/对端端口」、链路明细「发现方式」、发现明细「结果」等派生列也已可排序/筛选。
7. **路由追踪合并进连通性探测**：取消独立的「路由追踪」菜单与页面，其能力作为「连通性探测」的 **tracert** 探测方式存在（逐跳 MTR 表独立 div 展示）；后端路由追踪 SSE 端点保留复用。
8. **端口扫描改名「批量端口扫描」**：菜单、页面标题、注册名三处展示统一为「批量端口扫描」。
9. **DNS 探测 nameserver 报错修复**：根因为「指定 DNS」输入框的 `placeholder` 是提示长文本，前端旧逻辑会把空值字段的 placeholder 当值塞进请求体，导致后端校验 `is not a dns.nameserver` 失败。修复：该字段标记 `keepEmptyWhenBlank`，空值不再回填 placeholder；后端对非法 nameserver 增加兜底——无效时回退系统 DNS 并告警，不再直接报错。
10. **FTP/SFTP 上传 500 修复**：上传落盘后文件被设为只读，同名再次上传时 `open("wb")` 在 Windows 抛 `PermissionError → 500`。修复：覆写前先解除只读位、目录确保存在；整段包 `try/except`，权限不足/写入失败返回友好 JSON（`权限不足：…` / `写入临时会话目录失败：…`）而非裸 500。
11. **文字处理取消「原始数据 (JSON)」**：移除文字处理页底部的「原始数据 (JSON)」折叠块。

---

## 本期修复（20260817 第四批 / 框架 V3 / 数通配置卫士 V4 / 运维常用工具箱 V4 / CMDB V2）

1. **筛选/排序改为纯客户端（全量拉前端）**：设备列表、通知中心、日志中心、IT 资产主表、物理资产主表、CMDB 公共组件，以及端口百科/连通性探测/路由追踪/端口扫描等结果表，统一改为「首次全量拉取（size:10000）到前端 + `SF_MIXIN` 客户端排序/筛选/分页」。点击表头「筛选」确认后立即对当前已加载数据生效，不再与后端往返。后端 `filter_col/filter_values/sort_by` 接口参数不再被这些页面使用（接口保留不删）。
2. **表头不收缩 + 横向滚动**：`nc-sf-th` 表头 `min-width:max-content`，文字过宽靠横向滚动条/拖拽查看，不再挤压换行；含操作按钮的表格，操作按钮随表头一并横向滚动（不单独悬浮）。
3. **前端模块版本自检**：框架与各 ops 模块注册时盖章 JS 版本号；页面打开时校验是否为最新，过期则 `ElMessage.warning('检测到前端资源可能不是最新，请清除浏览器缓存或按 Ctrl+F5 刷新缓存')`。
4. **运维工具箱浏览器不缓存**：新增 FastAPI 中间件对 `/api/opstoolbox` 与 `/plugin-assets/ops_toolbox` 返回 `Cache-Control: no-store`，避免接口响应/前端资源被浏览器缓存。
5. **运维输入框浅色占位默认值**：连通性探测/路由追踪/端口扫描/HTTP 探测等「主机/IP」「URL」输入框占位符默认 `www.baidu.com`；用户留空直接执行时自动回退使用该默认值（用户输入则优先）。
6. **FTP/SFTP/WebDAV/TFTP 服务端随机高位端口**：服务端端口统一在 50000–60000 随机取未占用端口；切换「协议」自动重新生成端口 + 用户名 + 密码，避免复用。
7. **图片处理二维码拆入 ot-tabs**：删除「二维码」合并页，将「生成二维码」「识别二维码」并入图片处理页 `ot-tabs` 标签页。

## 本期修复（20260817 第三批 / 框架 V2 / 数通配置卫士 V3 / 运维常用工具箱 V3 / CMDB V1）

1. **全量表格统一排序/筛选表头（nc-sf-th）**：新增框架全局表头组件——排序 SVG 三角形图标 + 筛选 SVG 漏斗图标，**文字左、图标右**（flex space-between，表头靠右）；筛选弹层=列值枚举多选 + 搜索 + 全选/反选 + 重复项/唯一项 + 候选值升/降序（与设备列表同款交互）。全部页面表格接入：
   - **前端数组表**（框架 SF_MIXIN 前端排序/筛选）：FTP/SFTP 客户端（目录优先排序保留）、连通性探测、路由追踪、服务器管理、正则测试、任务列表、守护仪表盘、CMDB 仪表盘/维保/公共机柜组件、安全设置/通知渠道/插件列表核心页；
   - **后端分页表**（排序/筛选传后端参数）：设备列表、通知中心、日志中心、IT 资产主表、物理资产主表——对应接口新增 `sort_by/sort_order/filter_col/filter_values` 参数（审计日志 `/api/logs/audit`、通知 `/api/guardian/notifications`、资产 `/api/cmdb/assets`，均有列白名单校验）。
2. **删除原排列图标**：设备列表原手工 SVG 排序/筛选图标、FTP 客户端排序图标、各表原生 el-table 排序箭头（caret-wrapper）全部移除，统一为 nc-sf-th。
3. **端口百科删除顶部说明文字**。
4. **IP 工具箱、图片处理删除「原始数据 (JSON)」折叠块**（数据计算展示不受影响）。

## 上期修复（20260817 第二批 / 框架 V1 / 数通配置卫士 V2 / 运维常用工具箱 V2）

1. **设备列表取消 el-table 默认排序箭头**：`数通配置卫士-设备管理-设备列表` 表头不再渲染 Element Plus 默认的 `span.caret-wrapper`（与自定义排序图标双图标叠加）；排序保留自定义 SVG 三角形图标（点图标升/降序切换，后端排序），筛选图标不变。
2. **排序图标全局统一为 SVG**：全项目查找所有 el-table 排序实现（数通卫士设备列表 6 列 + FTP/SFTP 客户端文件列表 3 列），统一移除默认 caret 箭头、改用同一套 SVG 三角形排序图标（FTP 客户端新增 toggleSort，同列升/降切换、换列默认升序，目录优先排序行为不变）。
3. **端口百科提升为二级菜单**：`运维常用工具箱-网络诊断-端口百科` 移至「运维常用工具箱」二级菜单（与 IP 工具箱同级），路径/页面不变。
4. **TOTP 工具箱提升为二级菜单**：`运维常用工具箱-编码/格式/加密-TOTP 工具箱` 移至「运维常用工具箱」二级菜单，路径/页面不变。
5. **二维码工具箱并入图片处理**：取消「编码/格式/加密-二维码工具箱」独立菜单；生成二维码 / 识别二维码两项功能并入「运维常用工具箱-图片处理」页（funcs 第 5 项「二维码」，内含生成/识别两个子 tab），后端生成/识别接口不变。原独立页面文件已删除。

## 上期修复（20260817 / 框架 V1 / 数通配置卫士 V1 / 运维常用工具箱 V1）

1. **IP 工具箱 IPv6 三项计算报错修复**：`地址范围`、`二进制/十六进制`、`批量范围` 点击计算报「chunk is not defined / nToGroups is not defined」——`chunk`/`nToGroups` 此前仅定义在 base/ip 工具库内部且未导出，ipcalc 闭包直接引用导致 ReferenceError。已在本文件补齐与 base/ip 一致的定义，三项计算恢复正常。
2. **IP 工具箱空输入默认值**：输入框不再预填示例值（此前 schema 默认值直接显示在框内，易被误认为真实数据）；点击计算时若某字段为空，自动用内部默认值兜底保证可算出结果（标准地址库等无输入项的功能不受影响）。
3. **标准地址库自动展示**：`IPv4 标准地址` / `IPv6 标准地址` 无任何输入项，进入页面自动展示完整标准地址表，不再需要（也不显示）「计算」按钮；导出 CSV/Excel 仍可用。
4. **WebDAV 浏览器页删除「文件目录」面包屑**：`FTP/SFTP/WebDAV/TFTP 服务端` 的 WebDAV 网页不再显示顶部 `div.crumb` 路径导航，页面更简洁。
5. **拓扑 AF-Code 重复邻居根治**：设备表新增 `lldp_sysname` 列（兼容迁移），拓扑发现时持久化每台设备自身 LLDP 系统名；聚合匹配索引 `by_sysname` 改为从**全部已纳管设备**初始化（此前仅收集同一发现层，跨批次/跨层/该设备本层异常时失效 → 10.10.203.15 的邻居 AF-Code 匹配不到 10.10.200.5 而裂成重复节点）；未纳管→已纳管二次合并增加「系统名精确匹配」判据，并带防误并保护（同名未纳管多台如 28 台 DS-3E1526P-S 不并入唯一已纳管设备）。
6. **设备列表表头排序/筛选图标美化**：表头改为与文字同行的 **SVG 排序图标 + SVG 筛选图标**（原自定义表头覆盖了 el-table 排序箭头、且筛选是文字按钮）；点击排序图标切换升/降序（同列切换方向、换列默认升序），点击筛选图标打开筛选弹层。
7. **连接状态排序语义化**：`连接状态` 列排序不再按 health_status 字符串序（green<red…导致禁用设备穿插中间、点击无变化），改为语义分组——升序：正常→失败→未知→禁用；降序反向。
8. **插件设置新增「配置保存时长」**：默认 **90**（每台设备保留的备份份数）。备份由「只保留最新 1 份」改为**保留最近 N 份**：超出时删除最旧备份（文件 + 记录 + 其关联 diff），diff 链保持「上一份→本次」连续；被删最旧的变更信息随其删除、以较新记录为准。建议 ≥2 才能看到配置变更 diff。
9. **设备配置 diff 恢复**：此前「只保留 1 份」导致旧备份与 diff 全被删除，设备详情/通知中心的「设备配置变更」点进去只有最新配置、无差异可看；保存时长功能上线后 diff 链路自动恢复。
10. **备份文件名恢复「设备名称-获取时间.cfg」**（如 `AF-Code-20260814-102753.cfg`），与用户命名规范一致。
11. **框架缓存参数统一升级**：index.html 全部静态资源 `?v=` 升为 20260817-V1（修复 20260815 轮次只升内置版本号未升缓存参数、浏览器沿用旧前端的问题）。

## 上期修复（20260815 第三批 / 框架 V1 / 数通配置卫士 V3 / 运维常用工具箱 V3）

1. **SNMP 端口扫描漏报根因修复（BER 编码错位）**：运维常用工具箱 UDP 端口扫描对 SNMP(161) 的探测报文 BER 长度字段层层错位（最外层 SEQUENCE 声明长度 35 实际 38、OID 声明 7 实际 8），任何标准 SNMP Agent 收到均直接丢弃 → 无响应 → 判不通 → 端口不显示（如 `10.10.200.1:161` 扫不出）。现改用「自动计算长度的 BER 编码器」重建报文，并新增单测断言整包 TLV 长度自洽、可被递归解析（回归防护同类错误）。探针默认团体字 `public`，与系统其它 SNMP 查询兜底一致；若目标设备使用其它团体字仍可能扫不出（UDP 无凭证探测固有限制）。
2. **批量导入 vendor 说明补「华为智选」**：设备管理 - 批量导入弹窗内联 CSV 格式说明的 vendor 行，由 `huawei / h3c / cisco / ruijie / fortinet / tplink` 补充为 `huawei / huawei_smart(华为智选) / h3c / cisco / ruijie / fortinet / tplink`。厂商下拉框与下载模板此前已含 `huawei_smart`，仅说明文字遗漏。
3. **批量导入按 IP upsert（IP 为唯一标识）**：设备管理 - 批量导入改为「先按 IP 去重（文件内同一 IP 出现多次取最下面一条），再按 IP 查重」——库中已存在该 IP 则更新设备信息，不存在则新增；不再允许相同 IP 重复添加。返回 `created/updated/failed` 计数。
4. **批量导入重新上传文件改为替换**：选择文件控件改为重新选择即替换旧文件（limit=1 + on-exceed 替换），界面只显示一个文件，`csvText` 只保留最新一份内容，不再追加。
5. **导出 HTML 交互完全复刻「拓扑图」内页（方案 A）**：导出 HTML 内嵌交互脚本重写，在保留缩放 [0.3,3] / 平移 / 拖拽 + 相连边端口标注跟随的基础上，新增并完全对齐内页：①点击节点进入「聚焦模式」——仅显示该节点及其直连邻居、隐藏其余，并显示聚焦提示条（可点击「退出聚焦」）；②拖拽对齐辅助线（容差 6，与其他节点中心水平/垂直对齐时显示蓝色虚线）；③拖拽时端口标签按内页 `edgeList` 三模式（垂直/水平/对角，阈值 20px）**实时重排**端口名位置与旋转，而非固定偏移平移。已用 jsdom 真实脚本验证（聚焦隐藏、拖拽实时翻模式、对齐线均 PASS）。

## 本期修复（20260815 第二批 / 框架 V1 / 数通配置卫士 V2 / 运维常用工具箱 V2）

1. **UDP 端口扫描开放端口漏报修复（服务感知探针通用化）**：原 UDP 探测只发 1 字节通用包，对 NTP 这类「只回合法协议包、对空包无响应」的静默型服务只能判为不通（unreachable），叠加 R2「只显示能通端口」后端口彻底不可见（如 NTP 设备 192.168.12.1:123 扫不出）。现按端口发送对应协议探针：NTP(123)/DNS(53)/SNMP(161)/TFTP(69)/NetBIOS(137,138)，收到合法应用层响应即判开放（open）；未知端口维持原通用探测。新增 `plugins/ops_toolbox/tests/test_portscan_udp_probes.py` 单元验证（11 例全通过）。
2. **数通卫士配置备份文件名顺序修正**：备份文件仍平铺存于 `data/backups/`，文件名由 `<设备名>-<时间>.cfg` 改为 **`<时间>-<设备名>.cfg`**（如 `20260815-103825-AF-Code.cfg`）；每设备仅保留最新一份（保存新备份后删除旧 `.cfg`/DB 记录/diff 记录的 R4 逻辑不变）。
3. **导出 HTML 拖拽整图端口标注一起平移修复**：导出 HTML 内嵌拖拽脚本的 `edgeKeys` 收集循环此前遍历**全量线**（未过滤相连边），导致 `collectEdgeTexts` 装进全图所有 `data-edge`，拖任意节点时全图端口标注一起平移。现收窄为只收录「与被拖节点相连」的边（`st.lines[lk2].a || .b` 为真）。行为对齐「数通配置卫士 - 网络拓扑 - 拓扑图」内页（拖 A 只更新 A 及相连边端点/标注，非相连不动）。已用 jsdom 真实脚本验证：拖节点 6 仅 4 个端口标注（2 相连边 × 2 标注）位移，不再全图 68 个一起动。

## 本期修复（20260815 / 框架 V1 / 数通配置卫士 V1 / 运维常用工具箱 V1）

1. **HTTPS 安全访问「自动转跳」开关**：基础设置新增「自动转跳」开关（默认开）。启用后，单主机上主服务占用主端口（如 8080），自动在「主端口+1」起一个反向协议服务，误用协议访问时返回 307 跳转回主服务（如 http 误访问 https 端口、或 https 误访问 http 端口）。开关与跳转端口均可在 `user_config.yaml` 的 `https.auto_redirect` / `https.redirect_port` 配置；关闭则仅在正确协议下可访问。
2. **UDP 端口扫描只显示能通的端口**：结果区不再展示「开放或被过滤（open_filtered）」计数与黄框；仅上报**明确开放（open）**的端口，不通端口（含原 open_filtered）一概不显示、不计数。后端语义由 `open_filtered` 改为 `unreachable`（不通），前端移除相关展示与计数。
3. **DEBUG 模式浏览器控制台输出模块切换信息**：前端 `app.js` 的 `navigate()` 在 `NC_LOG_LEVEL=DEBUG` 时打印 `[NCDBG] [module] 模块切换: <标题> (<页面id>)`，与后端日志时间对齐。
4. **数通卫士备份仅保留一份**：保存新备份后，自动删除本设备此前所有旧的 `.cfg` 备份文件、对应 DB 记录及其关联 diff 记录，避免备份文件无限堆积。文件名仍为 `<设备名>-<时间>.cfg`（最新一份）。
5. **AF-Code 重复邻居修复**：SNMP LLDP 发现补采集本机 `lldpLocSysName`（.1.0.8802.1.1.2.1.3.3.0）并回传 `local_sysname`，使聚合 `by_sysname` 能正确建立，修复对端按系统名匹配失败导致的重复节点（如 10.10.203.15 多出 AF-Code，实为 10.10.200.5）。
6. **拓扑聚合引擎拆分 + 单测**：`engine/topology/aggregate.py`（444 行混装）拆分为 `match.py`（邻居匹配/去重）、`build.py`（聚合/快照）、`diff.py`（链路差异）三文件 + `aggregate.py` 兼容性 shim（导入契约不变），并新增 `plugins/netconfig_guardian/tests/test_aggregate_split.py` 单元验证（15 例全通过）。
7. **DEBUG 点击/输入追踪 + 交互元素定位**：框架 `framework.js` 在 DEBUG 下对 document 的 click/input 事件做全局追踪，记录「所属模块 + tag + id + class + 文本/输入内容 + XPath 路径」，便于复现与定位问题；页面交互元素继续由 `registerPage` 注入 `nc-module-<id>` / `nc-card` 模块 class。

## 本期修复（20260814 / 框架 V1 / 数通配置卫士 V1 / 运维常用工具箱 V1）

1. **端口扫描 TCP 开放端口显示 'undefined' 修复**：端口扫描页前端 `openPorts` 数组元素为纯数字（后端推送 `d.port`），模板却按 `p.port` 取值导致显示 undefined、点击弹窗标题变为「端口 undefined 用途说明」——模板统一改为直接使用端口数字。
2. **DEBUG 模式浏览器控制台带时间与模块标签**：框架前端调试输出（NCDBG）统一为 `[YYYY-MM-DD HH:MM:SS] [NCDBG] [模块] 内容`（模块标签 http/app 等），与后端日志时间对齐便于排查；页面注册与内置版本日志同样带时间。
3. **UDP 端口扫描结果展示修复 + 耗时提示**：结果区显示条件由「仅有开放端口」放开为「开放端口 / 开放或过滤 / 扫描完成」任一即显示——此前 UDP 扫描 0 个明确开放端口时整块结果区（含「开放/过滤」汇总）被隐藏，看起来"什么都没扫出来"；同时补充 UDP 全量扫描耗时说明（约 端口数÷200×超时 秒，建议缩小范围）。
4. **网页全部模块自动注入 class（debug 定位）**：框架 `registerPage` 注册时自动给每个页面根元素注入 `nc-module nc-module-<页面id>` + `data-module="<页面id>"`，页面内每个 `nc-card` 追加模块级 class；布局壳动态组件再叠加 `nc-page nc-page-<页面id>`。所有核心页与插件页（40+ 页面）无需逐页手改即可在 DOM 中定位模块位置。
5. **配置备份文件名带设备名称（平铺存储）**：数通配置卫士备份文件由 `data/backups/<设备id>/<时间戳>.cfg` 改为**平铺**存于 `data/backups/` 下，文件名 = **设备名称-获取时间.cfg**（如 `AF-Code-20260814-102753.cfg`，设备名自动净化 Windows 非法字符）；历史子目录备份文件保留可用，设备删除时新旧两种布局一并清理。
6. **拓扑点击设备 _withMods 崩溃根治**：根因=`exitFocus` 方法被误放在 `methods` 对象之外（Vue 静默忽略顶层未知选项），聚焦提示条按钮 `@click.stop="exitFocus"` 的 handler 实为 undefined → Vue 编译 `withModifiers(undefined)` → 运行时读 `undefined._withMods` 崩溃。已把 `exitFocus` 移回 `methods` 内；同时修复时间戳工具页唯一遗留的纯修饰符 `@submit.prevent`（补 handler）；框架错误边界对 `_withMods` 类错误增加专属诊断提示（直接在界面上指出事件 handler 未定义的可能原因与排查命令）。
7. **导出 HTML 拖拽只跟随被拖节点的标注**：导出 HTML 内嵌拖拽脚本此前在 mousedown 时收集了整张 SVG 的**全部**线中标注，拖动任意设备时图上所有端口标注一起平移——现只收集 `data-edge` 属于被拖节点相连边（与连线同键）的标注，未连边的标注保持不动。

## 上期修复（20260813 第二批 / 框架 V1 / 数通配置卫士 V2 / 运维常用工具箱 V2）

1. **首屏白屏修复（ERR_TOO_MANY_RETRIES）**：移除前端资源加载失败「自动重试注入」逻辑——此前手动重试叠加浏览器自身网络重试，同一资源累计请求次数超过 Chrome 上限即报 `ERR_TOO_MANY_RETRIES`（首屏只有文字无样式）；现失败仅显示提示横幅（Ctrl+F5 或刷新）。框架缓存参数升级为 v=20260813-V1 强制浏览器拉取最新资源。
2. **UDP 多端口扫描卡死修复 + TCP/UDP 拆分**：端口扫描后端拆分为**两个独立文件**——`portscan.py`（TCP，工具 ID=portscan）与 `portscan_udp.py`（UDP，工具 ID=portscan_udp），前端协议下拉分别调用；UDP「开放或过滤」结果前端**折叠**展示（只显示总数 + 前 100 个示例端口，不再全量渲染数千个标签导致浏览器 DOM 爆炸卡死）；后端 open_filtered 逐条推送节流（上限 200 条，超出仅计数）、UDP 并发上限收窄至 200。
3. **导出 HTML 拖拽标注跟随修复**：导出 HTML 内嵌拖拽脚本改为「记录标注初始位置 + 累计偏移」平移，**transform 旋转中心随节点同步更新**——对角模式端口标注不再乱飞/不跟随，垂直/水平模式的偏移保留。
4. **拓扑邻居合并条件收紧（HUB 判定）**：未纳管节点合并条件 = **系统名相同 且（Chassis ID（MAC）相同 或 管理 IP 相同）**——名称+MAC/IP 全部一致的同一台设备（含 HUB 下挂多路上报）合并成 1 台；名称相同但 MAC/IP 不同（如 28 台 DS-3E1526P-S）各自独立显示；华三/华为 verbose 解析器补 Chassis ID（MAC）字段，保证 CoreSW（MAC 相同）正确合并。
5. **拓扑线标注只保留端口名**：线中标注不再拼接端口描述（如 "GigabitEthernet1/0/26 Interface" / "->>Hik-Code;"），只显示端口名；描述仍保留在下方链路明细中。

## 上期修复（20260813 / 框架 V3 / 数通配置卫士 V1 / 运维常用工具箱 V1）

1. **端口扫描 UDP 结果展示**：UDP 扫描「开放或过滤」（open_filtered，超时无响应，与 nmap -sU 语义一致）不再被丢弃——后端实时推送、前端黄色标注「开放/过滤」展示；此前 UDP 常见端口（如 123/NTP）扫不出来。
2. **拓扑点击设备白屏修复**：聚焦提示条按钮的纯修饰符事件（无 handler）导致 Vue `undefined._withMods` 报错——已删除，聚焦/退出恢复正常。
3. **华为 LLDP 邻居详细命令修正**：华为正确命令为 `display lldp neighbor`（此前误配华三 `display lldp neighbor-information verbose`，华为不支持 → CLI 0 行 → 降级 brief 表格列错位）。新增华为详细块格式解析（System name / Chassis ID / Port ID / Port description / Management address），设备能正确识别 CoreSW 等邻居并连入拓扑。各厂商详细命令已核实：华为 `display lldp neighbor`、华三 `display lldp neighbor-information verbose`、思科/锐捷 `show lldp neighbors detail`。
4. **拓扑邻居合并收紧**：未纳管节点仅「IP 相同或一方无 IP」才按系统名合并——28 台不同 IP 的同名设备（如 DS-3E1526P-S）各自独立显示；同一台 CoreSW（CLI 带 IP + SNMP 无 IP）仍正确合并。
5. **画布自适应**：节点众多时画布按布局包围盒动态扩大（用满区域），节点与字号按密度自动缩小（>25 节点 0.85 倍、>50 节点 0.75 倍），30+ 节点完整可读。
6. **拓扑线端口标注三模式**（按《数通配置卫士 - 网络拓扑 - 拓扑路线端口描述展示规范》）：垂直竖排内嵌（Vertical Stacked，|ΔX|≤20px）/ 水平内嵌（Horizontal Inline，|ΔY|≤20px）/ 对角旋转（Diagonal Staggered，rotate θ 沿链路并保正读）；字号 12px、深色 #333333 + 白色描边；拖动节点改变排列方向实时切换。


> **框架核心（20260812-V3）**：
> ① **DEBUG 日志内容补全（需求1）**——此前开启 DEBUG 后日志文件仍只有 INFO（代码无 debug 级输出）。现框架关键路径新增 `logger.debug()` 调用点：HTTP 请求中间件记录「方法/路径/状态码/耗时」、插件加载详情（路由数/菜单数/版本）、SNMP 查询参数（密钥字段打码）；开启 DEBUG 后日志文件与控制台即有可见的调试信息。
> ② 版本号随核心改动升级至 20260812-V3。

> **数通配置卫士（20260812-V3）**：
> ① **SNMP v3 noAuthNoPriv 查询修复（需求2/3）**——「用户报文认证方式/加密方式」均留空（noAuthNoPriv）时，华为等设备报 `usmStatsUnsupportedSecLevels` / GETNEXT「无返回数据」的根因：auth 未启用时仍填充 20 字节零 authParameters（报文自相矛盾）。修复：auth 未启用时 authParameters 传空串（与 net-snmp `-l noAuthNoPriv` 一致）；查询参数显式空串=明确无认证/无加密，不再回退设备缓存或默认 SHA-256；`CACHE` 或未传才回退缓存。三种安全级别（noAuthNoPriv / authNoPriv / authPriv）均正常。
> ② **拓扑线端口标注方向（需求7/8/9）**——设备上下排列（线垂直）→ 端口描述**竖排内嵌**（Vertical Stacked）；设备左右排列（线水平）→ 端口描述**水平内嵌**（Horizontal Inline）；白色描边加粗至 4px 增强任何背景下可读性；拖动节点改变排列方向时**自动切换**标注方向。
> ③ **聚焦模式退出修复（需求5）**——退出按钮 `@mousedown.stop`/`@click.stop` 阻断事件穿透；`exitFocus()` 完整复位（聚焦节点/选中节点/明细筛选/分页），画布与明细全部恢复原状。
> ④ **画布交互增强（需求10A，参考 draw.io 交互范式）**——双击已纳管节点**就地改名**（draw.io 式，调用设备更新接口并同步节点与下拉列表）；拖拽节点时与相邻节点中心水平/垂直对齐显示**辅助线**（蓝色虚线，容差 6 画布单位）；背景网格保留。

> **运维常用工具箱（20260812-V2）**：
> ① **端口扫描支持 UDP（需求4）**——新增「协议」下拉（TCP/UDP）。UDP 探测语义与 nmap -sU 一致：收到应用层响应=开放、ICMP 端口不可达=关闭、超时=开放或被过滤；结果文案标注协议类型。

> **CMDB（20260812-V2）/ Wiki（20260812-V1）**：无变更（版本号保持）。

---

## 本期修复（20260812 / 框架 V2 / 数通配置卫士 V2 / 运维常用工具箱 V1 / CMDB V2）

> **框架核心（20260812-V2）**：
> ① **日志级别联动修复（需求1/2）**——日志级别是啥，日志文件与控制台就存啥：开启 DEBUG 后**程序控制台同步输出请求/响应明细**（此前控制台固定 INFO，开 DEBUG 与 INFO 无区别）；**uvicorn 的 HTTP 访问日志（`GET /api/... 200`）首次进入日志文件**（此前只走 uvicorn 自身 logger，从不落盘）；日志中心进入页面先同步服务端实际级别（此前前端写死 INFO，改了 DEBUG 刷新仍显示 INFO）。
> ② **使用文档 404 根因修复（需求4）**——定位根因：插件管理页「启用插件」只重新加载插件、未重新挂载路由，导致**菜单出现但 API 全部 404**。修复：启用/热重载后自动补挂路由（幂等防重）；启动横幅输出每个插件的路由数，路由为 0 的插件明确告警。
> ③ **白屏容错增强（需求3）**——静态资源（CSS/JS）加载失败时自动重试 2 次（重新注入带新时间戳的资源），仍失败才显示明确提示条。
> ④ **notify.yaml 详细中文注释（需求5）**——重写默认模板与保存渲染器：每个字段附带详细中文注释（含义/默认值/允许值/配置方法/示例），旧配置文件启动时自动补注释。

> **数通配置卫士（20260812-V2）**：
> ① **拓扑画布三层状态机（需求13/14）**——默认进入显示全部设备拓扑；「发现设备」选择器单选/多选时画布**只显示所选设备+它们的直连邻居**；**点击设备节点进入聚焦模式**（暂时隐藏其他设备，只显示该节点+直连邻居，顶部提示条显示节点数），**点击空白处恢复**为选择器视图；变更选择器自动退出聚焦。
> ② **「全部设备」互斥修复（需求9）**——此前首次点击其他设备会被误判为「勾选全部设备」而清空（需点两次）；修复后一次点击即生效。
> ③ **链路明细「汇总视图」（需求12）**——按「本端设备+对端设备」合并去重，多台设备共有的邻居（如 CoreSW-officeSW）只出现一组，展示端口数与本端/对端端口列表；可切换回逐条明细。
> ④ **拓扑线路加粗 + 接口信息全部嵌入（需求10）**——线宽 1.6→2.4（未纳管 1.3→2.0）；端口标注由「仅端口名」改为「端口名+描述」完整嵌入线中（如 `GigabitEthernet1/0/26 Interface`），竖排/横排自适应保留。
> ⑤ **SNMP v3 查询超时修复（需求8）**——UDP 丢包/设备繁忙时自动重试（总超时切分 3 段），消除「有概率 timed out，重新查询又好了」。
> ⑥ **编辑设备弹窗换行修复（需求11+截图）**——`label-width` 120→150px 且禁止换行，「用户报文认证方式/加密方式」一行显示；SNMP 所有下拉增加「留空不修改」placeholder；SNMP v3 凭据仍不回显（需求24 保留），未修改时保存不覆盖原配置。
> ⑦ **演示数据随机生成（需求7）**——触发条件与 CMDB 一致（guardian 数据文件完全不存在才生成）；内容改为随机：8~12 台设备，厂商/类型/认证方式/SNMP 版本/认证协议/加密协议/自动监测开关全部从候选池随机抽取且互不相同，用户名/密码/邮箱/品牌/型号等文本字段全部随机填充。
> ⑧ **未纳管邻居按系统名合并**——CLI（带管理 IP）与 SNMP（不带 IP）上报的同一邻居不再裂成多个节点（CoreSW-officeSW 只出现一次）。

> **运维常用工具箱（20260812-V1）**：
> ① 无变更（版本号保持）。

> **CMDB（20260812-V2）**：
> ① **IT 资产详情-系统信息取消「密码」模块（需求6）**——移除「显示密码」按钮与密码列（密码已加密存储且不再展示，防敏感信息泄漏）。

> **Wiki 文档中心（20260812-V1）**：
> ① 无变更（版本号保持；404 根因已在框架层修复）。

---

## 本期修复（20260812 / 框架 V1 / 数通配置卫士 V1 / 运维常用工具箱 V1 / CMDB V1）

> **框架核心（20260812-V1）**：
> ① **版本号/软件名输出**——程序控制台、日志文件、浏览器控制台统一输出**内置**软件名与版本号（不随用户自定义 name/version 变化；WEB 界面仍优先显示自定义值）；`/api/system/crypto-key` 新增 `builtin_name/builtin_version` 字段。
> ② **Windows 连接重置噪声根治**——`ConnectionResetError(10054)` 回调异常处理器改挂到**实际运行的事件循环**（手动 uvicorn.Config/Server + running loop handler），控制台不再刷 `_ProactorBasePipeTransport._call_connection_lost` 异常；同时缓解浏览器资源加载重试导致的概率性白屏（ERR_TOO_MANY_RETRIES）。
> ③ **系统概览增强**——新增主机名/架构/CPU 核数/进程 PID/启动时间/服务器时间展示；运行时长格式化为「X天X小时X分X秒」。
> ④ **notify.yaml 中文注释保留**——通知配置保存改用带注释渲染器（此前 yaml 重写每次保存都会抹掉中文注释）。
> ⑤ **HTTPS 证书文本化存储**——上传自定义证书/私钥后，PEM 内容直接写入 `user_config.yaml`（`https.cert_content/key_content`），不再保存文件路径（文件丢失即失效的问题消除）；旧版路径配置自动读取转存。
> ⑥ **配置项精简**——删除 `server.debug`（日志等级统一由 `logging.level` 控制）、删除 `session.idle_timeout_minutes`（自动退出统一由 `system.auto_logout_minutes` 控制）；旧配置文件启动时自动清理。
> ⑦ **审计日志排序修复**——跨天日志按 `timestamp_utc` 严格降序（此前跨文件乱序，最新日志不是第一页第一条）；日志中心删除「用户」列，表头支持排序，默认时间最新在前。
> ⑧ **使用文档 404 防御**——wiki 文档缺失返回结构化 JSON（区分「文件缺失」与「路由不存在」）；首次加载失败的插件热重载成功后自动补挂路由（消除重载成功但接口仍 404）。

> **数通配置卫士（20260812-V1）**：
> ① **拓扑画布全量渲染**——36 个节点全部显示（不再按所选/所点设备过滤子图）；点击节点仅高亮并联动下方明细；**点击画布空白恢复原状**（取消选中、恢复全量明细）。
> ② **明细多设备联动**——发现明细/链路明细支持按「发现设备」多选集合筛选（此前只显示最早点击的一台；链路明细此前始终为全量）。
> ③ **「全部设备」双向互斥**——勾选「全部设备」自动取消其他设备；勾选其他设备自动取消「全部设备」（此前只能单向）。
> ④ **SNMP 原始记录乱码修复**——OCTET STRING 值做可打印检测：二进制值按 snmpwalk 风格输出 `Hex-STRING`（如 `3C C7 86 8D 8A 00`），不再显示乱码。
> ⑤ **编辑设备弹窗加宽**——560px→760px，两列排布，「用户报文认证方式/加密方式」不再换行。
> ⑥ **SNMP v3 凭据不回显**——编辑设备时用户名/认证方式/加密方式/密钥全部置空（显示「留空则不修改」），保存时空串保留原配置。
> ⑦ **导出 HTML 拖拽加固**——端点匹配容差、节点中心动态计算、拖拽基准重置、实时兜底扫描，线/接口标注与节点拖动严格同步。
> ⑧ **首次运行演示数据**——guardian.db 首次创建时播种 5 台演示设备（覆盖全部字段与 SNMP v2c/v3 配置，各记录选项不同），文件存在即不再回灌。

> **运维常用工具箱（20260812-V1）**：
> ① **下载速度修复**——取消「多并发分段下载」改为单流，进度条随流式读取实时更新（修复 data 字段缺失导致进度恒 0%、无过程）；文案改为「默认 100MB，最大 10240MB（10GB）」。
> ② **SSH 批量执行 ≤5 台提速**——interactive 连接移入线程池（不再阻塞事件循环导致多台串行排队，此前首台连接完成前其余请求全部挂起）；内嵌 CLI 终端展示批量执行结果（此前只有登录 banner）。
> ③ **批量输出排版修复**——行首异常空格（≥8 个）自动清除（`GE1/0/24` 等接口行对齐），正常嵌套缩进保留。

> **CMDB（20260812-V1）**：
> ① **IT 资产列表删除「存储/内存」2 列**，编辑表单同步取消显示（数据保留，点击详情仍可见）。
> ② **演示数据全面补全**——12 台资产覆盖全部表单字段（品牌/型号/SN/颜色/存储/内存/合同/供应商/原值/购买/保修/盘点/系统信息/端口），且每个选项各不相同（状态 5 种、子类 11 种），用于测试各选项、文本框与 UI。

> **Wiki 文档中心（20260812-V1）**：
> ① **文档缺失错误结构化**——404 时返回 JSON `{"detail":"文档不存在：<文件名>（请检查程序目录 wiki/ 文件夹是否完整）"}`，便于区分「文件缺失」与「路由不存在」。

---

## 本期修复（20260811 / 框架 V8 / 数通配置卫士 V12 / 运维常用工具箱 V12 / CMDB V11）

> **框架核心（20260811-V8）**：
> ① **core.yaml 中文注释恢复**——配置迁移改为文本级段落裁剪（不再 yaml 重写抹注释），logging/session/https/debug 全部迁至 user_config.yaml，core.yaml 只保留 server(host/port)/crypto/jwt 且带完整中文注释。
> ② **user_config 去「迁移自」标注**——不再出现「（20260811-V7 由 core.yaml 迁移至此）」类版本注释，统一正常中文说明。
> ③ **日志级别落盘**——系统设置改日志级别同时写入 user_config.yaml，重启后保持（此前重启回退 INFO）。
> ④ **日志中心记录配置修改前后差异**——基础设置/日志级别等保存时审计「修改前 -> 修改后」。
> ⑤ **前端插件页面首访渲染竞态修复**——URL 直接访问插件页（/cmdb/it-assets 等）此前有概率空白（只显示菜单文字），根因是插件清单异步加载期间动态组件解析成空标签后不再重建；已为动态组件加 `:key=pagesVersion` 强制重建。
> ⑥ **资源加载失败白屏容错**——前端核心库/脚本加载失败时给出明确提示（不再无声白屏）。
> ⑦ **版本号输出**——启动控制台/日志文件/浏览器控制台输出真实版本；EXE 文件属性「详细信息-产品版本」显示版本号；index.html 缓存参数统一。
> ⑧ **稳定性**——Windows 客户端 keep-alive 断开的 ConnectionResetError(10054) 回调噪声优雅捕获，不再刷屏。

> **数通配置卫士（20260811-V12）**：
> ① **SNMP BER 编码根因修复**——LLDP-MIB 等含 >127 子标识（8802）的 OID 编码错误导致「配了 SNMP 却查不到 LLDP 表、永远走 CLI」（真实设备实测复现并验证修复：121 通过 SNMP 正确识别 CoreSW-officeSW/CoreSW-Produce）。
> ② **CLI brief 解析修复**——华为部分型号 `display lldp neighbor brief` 无「Neighbor Dev」列时不再把对端接口名当设备名（10.10.201.121 与 13 连同一 CoreSW 不再裂成两个节点）。
> ③ **导出 HTML 增强**——拖拽节点时接口标注随线移动；支持点击节点切换选中高亮；导出前清空选中态（不再与网页状态耦合）。
> ④ **任务日志每设备结果单操作按钮**——失败=「查看编辑设备」（直达编辑界面）、变更=「查询变更内容」、无变化=「查看设备配置」。
> ⑤ **拓扑交互**——拖动空白处可平移画布；「全部设备」与其他设备互斥；选择设备后拓扑图只渲染该设备及其直连子图、明细联动；已纳管设备按连通分量分区布局（关联设备同区、互不重叠）；接口信息按线方向嵌入拓扑线（水平线竖排/垂直线横排）并随拖动；明细每页条数单选移至分页左侧。

> **运维常用工具箱（20260811-V12）**：
> ① **网络测试改名**——「上传/下载速度」改为「平均上传/下载的速度」，显示平均速度；进度区显示「已传输 X MB / 共 Y MB」。
> ② **SSH 批量执行重做**——取消「xterm 显示数量（每页）」模块；设备数 ≤5 台结果区直接内嵌**可交互 CLI 终端**（点击即可输入命令）；超过 5 台显示静态输出 + 提示点击主机名进入该设备 CLI；输出 `\r\r\n` 归一化不再错乱。
> ③ **FTP/SFTP/WebDAV/TFTP 服务端监听端口随机化**——每次打开/刷新页面自动从高位段（50000-60000）分配空闲端口作为默认监听端口，避免端口重复使用。
> ④ **TOTP 二维码缩小**——生成尺寸由 200px 降至 160px、模块密度调小。

> **CMDB（20260811-V11）**：
> ① **办公/实物资产批量删除**——与 IT 资产一致，多选后「批量删除」（二次确认）。
> ② **报表中心删除「演示数据」模块**——不再提供手动恢复入口；演示数据仅在 CMDB 无任何数据文件（首次运行）时自动生成一次。

---

## 本期修复（20260811 / 框架 V7 / 数通配置卫士 V11 / 运维常用工具箱 V11 / CMDB V10）

> **框架核心（20260811-V7）**：
> ① **HTTPS 开关修复**（`/api/system/https/switch` 此前因缺导入必然 500，现已修复）。
> ② **审计日志全局倒序**——日志中心查询改为严格按时间从新到旧（此前「按天倒序、天内正序」，当天最新操作沉底）。
> ③ **logging/notify 配置迁移**——`core.yaml` 不再承载日志/通知频率限制配置，全部迁至可读写的 `user_config.yaml`（旧实例启动时自动迁移，`core.yaml` 不留注释）。
> ④ **时区配置自动补齐**——旧实例 `user_config.yaml` 缺 `system.timezone / auto_update_timezone` 时自动补默认值（`Asia/Shanghai`、登录自动更新），避免系统设置读不到、保存时被抹掉。
> ⑤ **`server.debug` 真正生效**——`core.yaml server.debug: true` 时日志级别强制 DEBUG（含文件）且 uvicorn 降为 debug 级；默认 false 保持 INFO，不影响 NCDBG 联动。

> **数通配置卫士-网络拓扑（20260811-V11）**：
> ① **导出 HTML 拖拽连线跟随**——导出文件内拖动节点时，以该节点为端点的链路同步平移（此前只动节点不动线）。
> ② **链路明细 / 消失链路 / 发现明细三表格分页**——每页 5/10/20/50 可选。
> ③ **发现设备「全部设备」默认选中**——选中后实时取全部设备参与发现。
> ④ **画布焦点过滤**——点击节点或选择设备后，画布仅高亮该设备及其直连链路，其余淡化。
> ⑤ **按已纳管/未纳管分组布局**——已纳管设备排画布左侧半圆、未纳管排右侧。
> ⑥ **端口标注竖排**——链路上端口标注取消描述、只留端口名并竖排嵌入线中。
> ⑦ **LLDP-MIB 列号映射修复**——chassisId/portId/sysName/portDesc 此前取值错位导致「配了 SNMP 却提示 LLDP-MIB 无邻居/邻居信息错乱」，现按标准列号解析。
> ⑧ **同设备不裂成两节点**——未纳管节点与已纳管设备按名称包含/IP 相等二次合并（此前一台 CoreSW 可能被画成两个节点）。

> **运维常用工具箱（20260811-V11）**：
> ① **网络测试按 librespeed 风格重写**——上传/下载均改为多并发（3 路）分段传输，高带宽路径吞吐显著提升；下载上限 2GB→10GB（后端 422 根因修复）、提示文本与上限对齐。
> ② **SSH 批量执行内嵌终端改为「批量输出展示」**——≤阈值台数时结果区以内嵌只读终端直接显示批量执行输出（成功=命令输出，失败=红色失败原因），不再另开交互会话造成「看不到批量输出」的误解；交互终端仍可点主机名进入。
> ③ **FTP 服务端连接信息调整**——用户名/密码去掉独立「复制」按钮（点击值本身即可复制），访问地址每项加「复制」按钮。
> ④ **TOTP 解析还原标签/账户**——`otpauth://` URI 的 label 做 `decodeURIComponent`（此前 `%3A` 不解码导致「标签=账户」）。
> ⑤ **路由追踪「已收/已发」修复**——前端透传后端 `received/probes_sent/probes_lost`（此前被丢弃恒显示 0/0）。
> ⑥ **二维码 webp 输出修复**——canvas 探测条件 `indexOf('image/webp')===0` 恒 false（实际前缀为 `data:image/webp`），导致所有浏览器都输出 gif；已修正为按 `data:image/webp` 前缀判定，现代浏览器输出 webp（体积更小）。

> **CMDB（20260811-V10）**：
> ① **批量删除**——IT 资产列表多选后支持「批量删除」（二次确认，后端 `/api/cmdb/assets/batch-delete`，关联端口一并删除）。
> ② **维保「报废」按钮**——维保管理过期/正常列表均可一键标记报废（二次确认），报废后不参与维保统计。
> ③ **演示数据条件修正**——仅在 `cmdb.db` 数据库文件**不存在**（首次运行）时播种演示数据；文件一旦存在（即使数据被清空）重启绝不回灌，手动恢复走「设置-恢复演示数据」。

---

## 本期修复（20260807-V1 / CMDB 20260807-V1 / 运维常用工具箱 20260807-V1 / 数通配置卫士 20260807-V1）

> **CMDB（20260807-V1）**：
> ① **办公/实物资产取消「存储大小」「内存大小」**——这两个字段仅 IT 设备展示（编辑表单与详情页同步，`v-if=isIT`）。
> ② **编辑资产「系统信息」「端口信息」按钮区改弹性布局**——窄屏自动换行，不再挤压/显示不全。

> **运维常用工具箱（20260807-V1）**：
> ③ **SSH/Telnet 批量执行结果改为每台独立卡片**——修复多主机结果按阶梯比例截断（第 1 台全量、末台仅 1/N 的问题）。
> ④ **批量结果点击主机名进入终端弹窗提速**——弹窗立即打开（显示"正在连接…"）并并行建连，不再等待连接完成才弹出；终端挂载未就绪自动重试；早期输出进缓冲区挂载后统一写入（修复输入不显示/输出丢失）。
> ⑤ **FTP/SFTP 客户端 与 FTP/SFTP/WebDAV/TFTP 服务端 页面清除所有 emoji 表情**。
> ⑥ **服务端「浏览服务器目录」支持选择服务器任意目录**——顶层列出全部盘符（Windows）/ `/`（Linux），可直接输入任意绝对路径跳转；原白名单（环境变量 `OPS_TOOLBOX_FS_ALLOWED_ROOTS`）仍可配置以恢复限制。
> ⑦ **「运行中的服务端」用户名/密码显示真实凭证**——此前刷新后丢失显示"(匿名)"；现在 `/server/list` 回传 `cred_username/cred_password/anonymous`。
> ⑧ **修复「刷新文件目录」报错 `this.$set is not a function`**（Vue 3 移除 `$set`，改为直接赋值）。
> ⑨ **客户端连接信息弹窗加宽至 1200px 并增加分页**（默认 10 条/页，可 5/10/20/50），在线连接与历史连接均支持。
> ⑪ **WebDAV/文件目录大小人性化显示**（B/KB/MB/GB，1024 进制）。

## 本期修复（20260815-V7 / 运维常用工具箱 20260815-V5 / 框架 20260815-V3 / CMDB+Wiki 20260815-V1）

> 本轮聚焦「11 项 bug/体验修复」。版本号：框架 20260815-V2→V3；数通卫士 20260815-V6→V7（本轮 .csv 白屏修复已先行升 V6，本期再加表头排序+品牌识别升 V7）；运维常用工具箱 20260815-V4→V5；CMDB/Wiki 不变。

| 编号 | 模块 | 修复/新增内容 |
|------|------|--------------|
| ① | 运维-路由追踪 | **MTR 表单主机名显示正确**：勾选「解析主机名」后，无 PTR 记录时 `_resolve` 改 `socket.gethostbyaddr` 返回空串（前端显 `-`），不再误显 IP |
| ② | 运维-HTTP 探测 | **任意方法解压报错修复**：`httpx` 强制 `Accept-Encoding: identity` 规避坏 `Content-Encoding` 的 `DecodingError`，并补针对性异常兜底（此前报错 `Error -3 while decompressing data`） |
| ③ | 运维-IP 工具箱 | **菜单调整**：从「网络诊断」三级子项移出，改作「运维常用工具箱」直接二级菜单 |
| ④ | 运维-IP 工具箱 | **未填值给默认值**：所有仅 placeholder 无 default 的字段补可直跑默认值，方便测试 |
| ⑤ | 框架-静态资源 | **刷新白屏修复（ERR_TOO_MANY_RETRIES）**：根因为自签名证书 SAN 仅含 `localhost`/`127.0.0.1`，以 LAN IP 访问时 Chrome 拒载 `/assets` 子资源；`core/https_utils.py` 现把本机所有非回环 IPv4/IPv6 + hostname 纳入 SAN，旧证书未覆盖当前 LAN IP 则删旧重生 |
| ⑥ | 运维-服务端(FTP) | **FTP 上传实测**：启动 FTP 服务端用 `ftplib` 实测（含 Explorer 风格引号空格文件名、建子目录后子目录内上传）全部成功，写权限 `elradfmwM` 与引号剥离已就绪。Windows 文件管理器无法上传属其 wininet FTP 客户端固有限制（写操作/中文路径易 550），非服务端问题；建议改用 WinSCP/Cyberduck/rclone |
| ⑦ | 运维-服务端(WebDAV) | **WebDAV 嵌套目录显示**：实测 GET 网页逐级显示嵌套子目录正常（根→a/→b/→c/ 均可点进）；`PROPFIND` 根集合 `href` 原取本地根目录 basename 生成 `/<root_basename>` 错误路径，已修正为正确相对路径（`/` 或 `/子目录`），提升 Windows 映射网络驱动器等 WebDAV 客户端枚举兼容性 |
| ⑧ | 运维-编码小工具 | **Hash 计算 SHA1/256/512 报错修复**：`crypto.subtle.digest` 只认带连字符算法名，界面 value `sha1/sha256/sha512` 映射为 `SHA-1/SHA-256/SHA-512`（此前 `toUpperCase()` 得 `SHA1` 非法） |
| ⑨ | 数通卫士-设备列表 | **表头排序**：6 列 `sortable="custom"`，后端 `_SORT_COLS` 白名单，默认 IP 升序；点击表头走 `@sort-change` 交后端排序 |
| ⑩ | 数通卫士-设备列表 | **筛选升降序对数值排序**：筛选弹层升/降序按钮改为对候选值列表排序（IP 段优先数字比较，其余数值/中文 `localeCompare`） |
| ⑪ | 数通卫士-品牌识别 | **海康 OEM 华三识别**：`profiles.py` 的 h3c `brands` 补 `"hik"`，`display version` 首行含 Hikvision 时正确识别为 h3c/华三（原仅 `h3c`/`comware`，漏判导致实际品牌显示 `-`） |

**接口/行为变化**：`GET /api/guardian/devices` 默认 `ORDER BY ip asc`（此前显式传参才排序）；刷新白屏改为证书层修复（非前端重试规避）。

## 本期修复（20260815-V5 / 运维工具箱 20260815-V4 / Wiki 20260815-V1 / 框架 20260815-V2）

> 本轮聚焦「深度审计后清理孤儿路由」。版本号：数通卫士 20260815-V4→V5，运维工具箱 20260815-V3→V4，Wiki 20260812-V1→20260815-V1（日期重置），框架 20260815-V1→V2。

| 编号 | 模块 | 修复/新增内容 |
|------|------|--------------|
| ① | 全项目（深度审计） | **删除 13 条零引用孤儿路由及其 handler**：经运行时内省 `app.openapi()` 权威核对（后端路由 130→117 条、前端调用 90 条），确认以下路由全仓库无任何调用方，安全删除——核心 `auth/last-login`；数通卫士 `drivers(+test)`、`logs(+clean)`、`reports/export`、`topology/snapshots`、`devices/{id}/refresh-info`、`devices/{id}/snmp-query`；运维 `client/ssh/exec`、`logcenter/report`、`session/files`；Wiki `wiki/list` |
| ② | 全项目（深度审计） | **保留 4 条外部/框架预留路由**（虽零引用但属规划能力，未删）：`/api/notify/send`、`/api/system/time`、`/api/system/session/reset`、`/api/system/session/status`；以及 2 条健康检查 `/api/system/health`、`/api/opstoolbox/health` |

**接口变化（下列接口已移除）**：`GET /api/auth/last-login`、`GET /api/guardian/drivers`、`POST /api/guardian/drivers/test`、`GET /api/guardian/logs`、`DELETE /api/guardian/logs/clean`、`GET /api/guardian/reports/export`、`GET /api/guardian/topology/snapshots`、`POST /api/guardian/devices/{dev_id}/refresh-info`、`POST /api/guardian/devices/{dev_id}/snmp-query`、`POST /api/opstoolbox/client/ssh/exec`、`POST /api/opstoolbox/logcenter/report`、`GET /api/opstoolbox/session/files`、`GET /api/wiki/list`。

**深度审计结论（权威版）**：运行时内省真实路由 **117** 条 vs 前端调用 **90** 条——前端调用后端无路由 **0 处真实坏链**（2 处为拼接前缀 token 与 WebSocket 端点误报）；后端无前端调用的 23 条中 19 条确有内部/文档引用保留、4 条外部/框架预留保留、13 条纯孤儿已删除。

## 本期修复（20260815-V4 / CMDB 20260815-V1）

> 本轮聚焦「数据导入类型收敛」+「拓扑交互与布局优化」+「深度审计清理」。框架、运维工具箱、Wiki 版本号不变。

| 编号 | 模块 | 修复/新增内容 |
|------|------|--------------|
| ① | 全项目导入 | **数据导入入口统一限制文件类型**：数通卫士设备批量导入限 `.csv`；CMDB IT 资产/物理资产批量导入限 `.csv`、备份恢复限 `.json`；运维二维码识别限图片（png/jpg/webp/svg 等）；非法类型直接拒绝并提示（FTP/SFTP 客户端、SSH 命令脚本上传属文件传输工具，不限制） |
| ② | 数通卫士-设备列表 | **表头排序+筛选**：每列表头内嵌弹层，支持升序/降序、值搜索、全选/反选/重复项（值出现≥2 次）/唯一项（值仅 1 次）；后端 `_SORT_COLS` 白名单防注入，`list_column_values` 全量返回列去重值+计数，前端按需分页拉取（含筛选后仍带分页） |
| ③ | 数通卫士-拓扑布局 | **全分辨率响应式**：删除右侧「节点详情/发现统计」两栏，拓扑图改为全宽度（`SVG width:100%`，手机铺满 / 桌面合理上限 / 4K 清晰）；「发现统计」改为拓扑图下方、设备详情上方的一行文字；选中节点信息并入该行 |
| ④ | 数通卫士-拓扑交互 | **拖拽/平移 1:1 跟手**：坐标换算补 `viewBox→渲染宽` 缩放因子 `S=canvasW/rect.width`，修复高 DPI/宽屏下「鼠标移 100px 设备只动约 40px」；内页与导出 HTML 同步修复 |
| ⑤ | 数通卫士-导出 HTML | **聚焦逻辑与内页一致**：点击节点始终聚焦该节点（不再 toggle 退出），退出聚焦改由点击空白或「退出聚焦」按钮触发 |
| ⑥ | 运维工具箱 | **清理死代码**：删除无菜单入口的 `opstoolbox_config`（连接配置）页、合并残留桩 `opstoolbox_tfa`（2FA），及已无前端调用的孤儿后端工具 `tfa2.py` |

**接口变化**：`GET /api/guardian/devices` 新增查询参数 `sort_by`(白名单列)、`sort_order`(asc/desc)、`filter_col`、`filter_values`(数组)；新增 `GET /api/guardian/devices/column-values?column=` 返回该列去重值+计数（非法列返回 400）。

**深度审计结论（本轮附加，初版）**：前端 `/api/*` 调用 91 条 vs 后端路由 128 条交叉核对——前端调用后端无路由 **0 处真实坏链**（2 处为模板字符串/框架路由误报）；后端无前端调用的 17 条路由中 3 条为健康检查（`/api/opstoolbox/health`、`/api/system/health`）合理保留，其余 14 条为内部/待接前端能力，初查未擅自删除。**（终版见上方 20260815-V5 节：经运行时内省权威复核为 13 条纯孤儿，已全部删除）**。

> **数通配置卫士（20260807-V1）**：
> ⑫⑬ **修复批量测试/更新设备信息/更新配置 NameError `_get_device_lock is not defined` 导致的批量按钮全部失效**——根因：`from ._base import *` 不导入下划线开头符号，`routes/devices.py` 缺显式导入（同一根因还修复了 `routes/snmp.py` 的 `_decrypt_snmp` 与 `routes/reports.py` 的 `_build_report_html` 两处潜伏 NameError）。
> ⑭ **插件设置页删除「网络拓扑（20260806-V1）」分组标题文字**。
> ⑮ **删除设备级联清理该设备所有关联数据**——`device_snmp`/`device_info`/`backup_records`/`diff_records`/磁盘备份目录/所有任务 `device_ids` 数组；任务日志不再出现"设备#N：设备不存在或已删除"记录（静默跳过）。
> ⑯ **SNMP 查询 Community 回退链修复**——请求值 → 设备缓存 SNMP 信息 → `public` 兜底；`v2` 与 `v2c` 归一等价。
> ⑰ **SNMP 查询新增 v3 支持**——设备详情 SNMP 查询页版本切换 v2c/v3；`snmp-get`/`snmp-getnext`/`snmp-query` 均支持 v3（参数优先请求体，回退设备已存配置，密钥解密）。
> **engine/topology.py 拆分为 `engine/topology/` 包**（profiles/brand/parsers/snmp/cli/discover/aggregate），对外接口不变。

## 本期修复（20260806-V2 / CMDB 20260806-V2 / 运维常用工具箱 20260806-V2）

本轮 11 项需求（①~⑪）全部完成并测试通过（客户身份全量实测 31/31 项 API 用例 + FTP 兜底单测 4/4 + 前端断言全过）。

| 编号 | 模块 | 修复/新增内容 |
|------|------|--------------|
| ① | CMDB 编辑资产 | 「系统信息」「端口信息」表格列宽压缩 + 表格 100% 宽，**全部列完整显示不再错乱/截断**；弹窗加宽至 960px；登录方式选「其他」时**出现自定义输入框**，保存后详情页显示「其他(自定义值)」 |
| ② | CMDB 编辑资产 | 「添加端口」按钮前错误的 `<i class="el-icon">＋</i>` 符号已去除（该写法在 Element Plus 中渲染为乱码字符） |
| ③ | 端口扫描 | 取消「常用端口 / 1-1000(默认) / 1-10000 / 全量 1-65535」4 个预设按钮，端口范围改为直接手填 |
| ④ | SSH 批量执行 | 执行结果表格上方增加「执行结果（N 台）」表头，与主机列表/命令输入区明确分区 |
| ⑤ | SSH 批量执行 | 点击结果中的**主机名弹窗打开该设备交互终端**（xterm + WebSocket，可输入命令）；后端批量结果行补充 `port`/`user` 字段（支持 `user@host:port` 每行独立凭据） |
| ⑥ | FTP/SFTP 客户端 | 删除乱码/混合编码文件名报 450 的兜底修复：删除时按 `path_raw → 文件名原始字节 → 显示名重编码(utf-8/gbk/gb2312)` 候选字节集逐一尝试，任一成功即删除成功；中文名文件「上传→列表→删除」全链路实测无 450 |
| ⑦ | 服务端-浏览目录 | 「浏览服务器目录」支持点击「上级目录」逐级返回；父目录越出白名单时回到**顶层重新列出全部可选根目录**（原逻辑按钮被禁用、用户被困子目录） |
| ⑧ | 服务端面板 | 取消独立「已启动服务端·连接信息」卡片，连接信息并入「运行中的服务端」表格**展开行**（协议/访问地址/用户名/密码/根目录/服务器文件目录 + 复制按钮）；访问地址**自动列出服务器全部本机 IP**（不再显示「请替换为服务器实际 IP」）；表格加宽至 1200px 并支持分页（默认 10 条/页，可选 5/10/20/50） |
| ⑨ | 前端模块化 | 70KB 的 `netcore_client_lib.js` 按功能域拆分为 5 个文件：`netcore_lib_base.js`(10K)、`netcore_lib_ip.js`(13K)、`netcore_lib_ipcalc.js`(39K)、`netcore_lib_text.js`(6K)、`netcore_lib_totp.js`(6K)，全局接口 `NC_CLIENT_LIB / NC_MD5 / NC_CRC32 / NC_B32ENC / NC_TEXT_ENGINE / NC_IPCALC_ENGINE / NC_TOTP_ENGINE` 全部保持兼容（node 全功能冒烟通过） |
| ⑩ | CMDB 端口信息 | 端口表新增 **MAC 地址 / IP 地址** 两列（字段 `mac`/`ip`，随端口行存储），资产详情页端口表同步显示 |
| ⑪ | CMDB 常用信息 | 新增 **颜色 / 存储大小 / 内存大小** 三个字段（`color`/`storage`/`memory`），资产列表页新增对应列并可参与**搜索查询**（后端搜索扩展匹配），详情页基础信息区展示；老库自动迁移补列 |

**接口变化**：`GET /api/opstoolbox/server/list` 响应新增 `local_ips`（本机全部 IPv4 列表）；`POST /api/opstoolbox/client/ssh` 批量结果每行新增 `port`/`user` 字段；CMDB `POST/PUT /api/cmdb/assets` 支持 `color`/`storage`/`memory` 字段与端口 `mac`/`ip` 字段，`GET /api/cmdb/assets?search=` 搜索范围扩展至颜色/存储/内存。

## 本期修复（20260806-V1 / CMDB 20260806-V1 / 运维常用工具箱 20260806-V1）

> 本期共处理 **11 项**用户反馈（①~⑪）。框架、数通配置卫士、文档插件本期未改动，版本号按规则保持不变（框架 `20260805-V1`、数通卫士 `20260805-V1`、文档插件 `20260804-V1`）。

| # | 现象 | 根因 | 处理 |
| --- | --- | --- | --- |
| ① | CMDB 删除所有数据后，重启软件数据又被加回来 | 演示数据播种逻辑每次启动都执行「表为空就写入」，删空正好触发重新播种 | 改为**一次性播种**：首次初始化后在 `meta` 表落 `demo_seeded=1` 标记，之后永不自动播种；老库升级自动补标记；另提供 `POST /api/cmdb/demo-data/restore` 供手动恢复 |
| ② | 端口扫描的「开放端口」点了没反应，看不懂端口用途 | 结果区只是纯文本标签 | 点击端口弹出「端口用途说明」小窗（协议/服务/分类/说明，同端口多条并列），可跳转完整端口百科页；字典 305 条 |
| ③ | SSH/Telnet 批量执行点了要等很久才出结果 | 命令执行后一直读到 `cmd_timeout` 超时才返回 | shell 通道输出**静默 ≥1.0s 即判定结束**立刻返回；真机实测 2.2s 出结果，认证失败同样快速返回并给出明确原因 |
| ④ | FTP/SFTP 批量下载部分文件报 `550 File does not exist` | 文件名经字符串编解码后与服务器实际字节不一致 | 列表返回 `raw`/`path_raw`（原始字节 base64），下载按字节精确定位 |
| ⑤ | 上传中文名文件后变成乱码 | 上传时按固定编码转换文件名 | 按服务器协商编码原样写入字节，配合 `dir_raw` 定位目标目录 |
| ⑥ | 删除乱码文件报 `450 Error deleting file` | 同 ④，删除请求命中不到真实文件 | 删除改用 `path_raw` 字节定位，**只执行一次不做换编码重试**；失败原因逐条回显 |
| ⑦ | 服务端「浏览服务器目录」按钮无反应 | 目录选择器调用链断裂 | 修复 `GET /fs/list` 调用，按钮正常拉起目录树 |
| ⑧ | 想看某个运行中服务端有哪些客户端连着 | 无此能力 | 新增 `GET /server/connections?server_id=`，点击服务端行即展开在线连接 + 历史连接与事件（含登录失败） |
| ⑨ | FTP/SFTP 客户端下载的临时文件一直堆着 | 无清理入口 | 新增「停止时清理」勾选框，**默认开启**，离开页面自动清空会话临时目录；偏好本地记忆 |
| ⑩ | `plugins/ops_toolbox/frontend` 里的文件太大不好维护 | 单文件承载过多页面 | 拆为 **35 个 js 模块**（27 个业务模块 + 公共基座 + 数据/第三方库），单个业务文件均 < 30KB；共享函数收敛到 `window.OT` 基座；文件名数字前缀保证注入顺序 |
| ⑪ | 端口扫描是不是只显示 `COMMON_PORTS` 里的端口 | 误解（字典只用于附加服务名） | 确认扫描范围完全由输入决定，**字典无记录的端口照常扫出并显示**；输入框补「常用 / 1-1024 / 1-10000 / 全量 1-65535」预设按钮 |

**附带修复的两个稳定性问题（本期实测中发现）**

- **FTP 服务端整条控制连接被掐断**：pyftpdlib 处理删除异常时调用 `os.strerror(err.errno)`，遇到 `errno` 为 `None` 的 OSError（部分安全软件/受限环境会抛出）直接触发 `TypeError`，导致客户端连接被服务端强制中断。已在服务端兜底捕获，统一转换为标准 `550` 应答，服务端不再断连。
- **客户端空错误提示 `（）`**：控制连接失效时错误信息为空，用户无法判断原因。已加入连接池失效检测 + 自动重连 + 删除结果二次确认，失败时给出可读原因。

**组件加载误报 ERROR（本期实测中发现并修复）**：`plugins/ops_toolbox/servers/__init__.py` 的 `__all__` 里混入了本文件内定义的类名（`ConnTracker`/`ServerHandle`），而该 `__all__` 会被组件加载器当作「服务端子模块名清单」逐个 import，启动时因此刷出 4 条 `No module named ...` 的**误报错误日志**（功能实际正常）。已从 `__all__` 移除类名，并在加载器侧增加白名单守卫做双保险。修复后启动日志 **0 ERROR**。

---

## 本期修复（20260805-V1）

- **CMDB 机柜视图——删除机柜 / 移出设备**：机柜卡片与 U 位详情弹窗新增「删除」按钮；机柜内仍有已上架设备时默认拒绝删除并返回设备数，二次确认 `force=1` 后仅解绑下架（清空 `rack_id/u_start/u_height`），**资产台账保留**；U 位详情内单台设备支持「移出」（仅解绑 U 位，资产保留）与「删除」（从台账移除）。对应新增接口 `DELETE /api/cmdb/racks/{rack_id}` 与 `POST /api/cmdb/assets/{id}/unbind-rack`。
- **登录字段解密告警**：`frontend/app.js` 登录提交补上对 `username` 的 AES-256-GCM 加密（此前仅 `password/totp` 加密，明文 `username` 被后端按密文解密失败并回退明文，控制台打印「字段解密失败」WARNING）。修复后与 `core.api` 解密逻辑对齐，登录不再产生该告警；后端仍保留明文兼容作为密钥不一致探针。

---

## 本期模块化（20260806-V1，需求⑩）

> 本轮仅做前端代码结构重组，**功能与对外接口完全不变**。

- **`plugins/ops_toolbox/frontend` 由少数几个巨型文件拆为 35 个 js**：其中 27 个业务模块（`tools_01_net_00_base` … `tools_06_misc_03_image`）、1 个公共基座（`tools_00_common.js`）、端口字典与端口百科页（`portinfo_00_db.js` / `portinfo_10_page.js`）、以及 SSH 终端、网络测试、二维码库等独立模块。**单个业务文件均 < 30KB**，定位与维护成本大幅下降。
- **注入顺序靠文件名保证**：框架 `/api/plugins/frontend-manifest` 按文件名**字母序**注入，故用数字前缀锁定次序。公共基座 `tools_00_common.js` 暴露 `window.OT`（http / reg 等），**所有引用 `OT` 的文件必须排在它之后**；`portinfo_*.js`（字母序在 `tools_*` 之前）是**零依赖纯数据/页面模块**，只用 `window.NC.registerPage` 原生注册、不使用 `OT`，因此提前加载不会报错——修改这些文件时请务必保持该约定。
- **端口字典单点维护**：`portinfo_00_db.js` 挂载 `window.NC_PORT_DB`（305 条），端口扫描弹窗与端口百科页共用同一份数据，新增端口只需改这一处。
- 版本号随之提升：运维常用工具箱 → `20260806-V1`；框架 / 数通配置卫士 / 文档插件本期未改动，版本不变。

## 框架优化（20260806-V1，代码审查整改）

> 全量代码审查（242 个源文件）整改项：**语法 0 错误、产品代码 0 处 print 调试、0 处高危模式（eval/exec/os.system/shell=True）、0 处硬编码密钥**；测试套件由 15/18 提升至 **18/18 通过**。

1. **FastAPI 生命周期迁移**（`core/framework.py`）：`@app.on_event("startup")` 弃用警告消除，改为 `lifespan` 事件（启动时序：bootstrap → 通知重载 → 日志 → 密码重置 → 插件加载挂载；关闭时自动调用插件 `on_unload` 清理），启动行为与之前完全一致。
2. **登录字段解密告警优化**（`core/auth.py` `decrypt_field`）：仅当值形态像密文（合法 base64 且 ≥ 28 字节）才尝试解密并告警；明文用户名/密码直传直接按明文返回，不再产生 `Invalid base64 / Nonce` 误导性告警（设备连接失败仍返回明确错误信息，如「TCP 连接设备失败（目标不可达或端口未开放）」）。
3. **测试套件修复**（`tests/test_suite.py`）：①设备 CRUD / 任务备份用例改为注入模拟采集（monkeypatch `_real_collect`），不再依赖真实设备与明文凭证；②移除设置页过时断言 `mock_mode`（产品 `DEFAULT_SETTINGS` 无此字段）。全套件 **18/18 PASS**。
4. **残留清理**：历史手动测试脚本 28 个归档至 `tests/_archive/`；删除源码树 `__pycache__`（22 目录 / 174 pyc）、插件运行时数据库（`cmdb.db`/`guardian.db`）、构建沙盒、dist 旧版 `netcore_client_lib.js` 残留；`plugins/ops_toolbox/__init__.py` 补齐中文 docstring（原为 0 字节空文件）。

> 版本号：框架 `20260805-V1 → 20260806-V1`；数通配置卫士 / 运维工具箱 / CMDB / 文档插件本期无功能改动，版本不变。

## 本期修复（20260809-V8 / CMDB 20260809-V8 / 数通配置卫士 20260809-V7 / 运维常用工具箱 20260809-V7 / core 20260809-V3）

> **CMDB（20260809-V8）**：编辑资产操作列按钮 `删` → `删除`。
>
> **数通配置卫士（20260809-V7）**：
> - 设备工具栏批量 div 固定高度（滚动条占位，列表不再位移）。
> - SNMP v2c 查询 NoneType 报错修复（`_v2_community` 函数体恢复）。
> - SNMP v3 查询新增「设备缓存认证/加密」选项（value=CACHE，默认选中），用户名留空用设备缓存。
> - SNMP v3 认证/加密错误误报「查询成功」修复（usmStats 前缀 OID 即判失败并翻译）。
> - SNMP v3 GETNEXT 超时可读化（带排障建议；华为设备固件对 GETNEXT 静默不响应为设备行为）。
> - 拓扑发现 `engine.snmp_v3` 相对导入错误修复（`..`→`...`）；CLI 连接超时 8s→20s（从 settings 读）；SSH/Telnet 失败原因一并展示。
> - 通知中心/任务日志/设备时间统一走框架全局 fmtTime（按系统设置时区）。
> - 版本号：数通配置卫士 `20260809-V6 → 20260809-V7`。
>
> **运维常用工具箱（20260809-V7）**：
> - 终端大写/空格双输出彻底修复（统一 sendDedup 出口去重，真实浏览器验证 S/空格/s 各发送 1 次）。
> - 批量执行内嵌终端连接失败可见化。
> - 网络测试上传：分片 2MB + 单分片失败自动重试 2 次（网易UU隧道 TCP RST 自愈）。
> - 网络测试下载：响应加 `X-Accel-Buffering: no`；前端 15s 看门狗（不再无限转圈）。
> - 版本号：运维常用工具箱 `20260809-V6 → 20260809-V7`。
>
> **core（20260809-V3）**：
> - 新增 `GET /api/system/time`：返回系统设置时区的当前时间（timezone / local_time / utc_time / offset_seconds / offset_hours）。
> - 前端资源统一加 `?v=20260809-V3` 版本参数（cache-busting，避免浏览器/跳板机缓存旧 JS 导致通知时间仍显示 UTC+0）。
> - 全局 `window.NC.fmtTime` 作为所有时间显示的统一切口。

---



> **CMDB（20260809-V7）**：
> - 编辑资产「系统信息 / 端口信息」列改 min-width 自适应，高分辨率自动铺满弹窗（不再右侧空白），窄屏出横向滚动条；操作列表头保留、无冻结。
> - 版本号：CMDB `20260809-V6 → 20260809-V7`。
>
> **数通配置卫士（20260809-V6）**：
> - 设备管理工具栏：批量按钮与右侧按钮同尺寸；批量区 v-show 固定高度占位（多选后列表不下移）；预留滚动条高度。
> - SNMP v2c 概率超时：UDP 重试 2 次 + request-id 校验。
> - SNMP v3 错误误报"成功"修复：error/NULL varbind 判失败，usmStats 翻译。
> - SNMP GET/GETNEXT 全部分离为 4 个独立 py 文件（v2c_get/v2c_getnext/v3_get/v3_getnext + snmp_common）。
> - SNMP v3 查询参数默认折叠（默认用设备缓存，自定义才展开）。
> - 拓扑发现：错误带插件版本号；CLI 超时收紧（8s/15s）；SSH 失败自动降级 Telnet。
> - 通知中心时间按配置时区显示；删除设备级联清理任务日志。
> - 版本号：数通配置卫士 `20260809-V5 → 20260809-V6`。
>
> **运维常用工具箱（20260809-V6）**：
> - 批量执行输出分页清理彻底修复（真实设备字节验证：Eth-Trunk 成员端口行首缩进保留）。
> - 设备终端大写/空格双输出修复（兜底 input 增量去重）。
> - 网络测试：上传每片 Connection: close（B 方案）；下载定长 Content-Length（上限 2GB，不转圈）。
> - 批量执行结果直接内嵌 CLI 终端（≤5/10/20 台可选，保持连接至刷新页面；超阈值走静态+弹窗；分页）。
> - 版本号：运维常用工具箱 `20260809-V5 → 20260809-V6`。
>
> **core（20260809-V2）**：系统设置新增时区选项（默认浏览器时区 + 登录自动更新勾选），全局时间按配置时区显示。

---


> **CMDB（20260809-V6）**：
> - 编辑资产「系统信息 / 端口信息」列改固定宽度（内容完整显示），超出弹窗容器出现横向滚动条可拖拽；「操作」列增加表头；操作列无 fixed 随表滚动。
> - 版本号：CMDB `20260808-V5 → 20260809-V6`。
>
> **数通配置卫士（20260809-V5）**：
> - 「已选 x 台」移到设备列表标题右侧。
> - **SNMP v3 timed out 彻底解决（真实设备验证 PASS）**：六层根因——msgGlobalData SEQUENCE 包裹（RFC 3412）、msgMaxSize 3 字节编码、engineTime 4 字节编码（华为 VRP 固定长度解析）、engineTime 同步流逝秒数、localized key 派生算法（pysnmp hash_passphrase，HMAC 逐字节验证匹配）、priv key 独立派生 + AES-CFB-128 无 padding；另修复响应 scopedPDU 解析。真实设备（服务器 → 华为 S5735）discovery + GET + GETNEXT 全链路 PASS。
> - v3 查询默认使用设备缓存配置（不再写死 SHA-256/AES-128）；安全级别联动（noAuthNoPriv/authNoPriv/authPriv）。
> - 网络结论（修正）：本机（192.168.12.101）与服务器（192.168.12.100）到设备的 SNMP/SSH 均可达；此前本机 UDP 161 超时为客户端报文不合规被设备丢弃（已修复），非 ACL 拦截。
> - 版本号：数通配置卫士 `20260808-V4 → 20260809-V5`。
>
> **运维常用工具箱（20260809-V5）**：
> - 批量执行与单机执行输出去掉 `.strip()`，输出首尾原样保留，与 SSH 工具逐字节一致（含行首缩进）。
> - 版本号：运维常用工具箱 `20260808-V4 → 20260809-V5`。

---


> **CMDB（20260808-V5）**：
> - 编辑资产「系统信息 / 端口信息」全分辨率适配：弹窗 90vw+max-width:1280px、列改 min-width 自适应、媒体查询适配手机/电脑；操作栏确认无冻结（随表滚动）。
> - 版本号：CMDB `20260807-V4 → 20260808-V5`。
>
> **数通配置卫士（20260808-V4）**：
> - 设备管理工具栏横向滚动（批量按钮可拖动滑出），「添加设备/批量导入」固定最右。
> - **SNMP v3 timed out 真根因修复**：`_parse_v3_response` 未跳过 USM SEQUENCE 头致 engine_id/boots 错位、密钥派生错误；已修复并经严格 mock（RFC 3826/7860 校验 HMAC+AES 全链路）验证 PASS。
> - 「无认证/无加密」用 sentinel `NONE` 正常显示；SNMP v3 表单一行全显示。
> - 拓扑发现提示增强（认证失败带 auth_method、未配置 SNMP 引导到编辑设备保存）。
> - 版本号：数通配置卫士 `20260807-V3 → 20260808-V4`。
>
> **运维常用工具箱（20260808-V4）**：
> - SSH 设备终端输入可用性根治（双根因：xterm 5.3 字母输入失效 + `_pending=[]` truthy 输出永不显示），Chrome CDP 真实浏览器自动化验证 PASS。
> - 批量执行输出 `
` 与空格 100% 原样保留（与 SSH 工具逐字节一致）。
> - FTP STOR/APPE/MKD 兜底 + 失败日志增强（path/root/err）。
> - 网络测试上传修复（消费响应体，32MB 零失败）；下载修复（移除 Content-Length 改 chunked，正常结束）。
> - 版本号：运维常用工具箱 `20260807-V3 → 20260808-V4`。

---


> **CMDB（20260807-V4）**：
> - 编辑资产「系统信息 / 端口信息」按钮截断 + 操作栏冻结**彻底修复**：弹窗 960→1180px；移除上一轮误加的 `fixed="right"` 冻结列（操作栏随表横向滚动）；端口表列宽瘦身 860→810px，整表完整显示。
> - 版本号：CMDB `20260807-V3 → 20260807-V4`。
>
> **数通配置卫士（20260807-V3）**：
> - 设备管理工具栏：批量操作按钮多选才出现；「添加设备/批量导入」固定最右；搜索框移到设备列表标题右侧。
> - 设备详情抽屉 60%→75%（SNMP v3 查询扩宽）。
> - 修复点「用户报文认证/加密方式」下拉时抽屉被误关（handleOutsideClick 排除 el-popper 浮层）。
> - **SNMP v3 AES 加密 timed out 修复（RFC 3826）**：privParameters salt 4 字节 → 8 字节（boots+counter），华为设备不再丢弃报文。
> - 拓扑发现 CLI "Nonce must be between 8 and 128 bytes" 修复：enable_password 解密统一走 `_safe_decrypt` 兜底。
> - 版本号：数通配置卫士 `20260807-V2 → 20260807-V3`。
>
> **运维常用工具箱（20260807-V3）**：
> - 浏览服务器目录名称列取消 `[目录]/[文件]` 前缀。
> - SSH 批量执行「设备终端」输入可用性根治：弹窗 `trap-focus=false` 放行 xterm 获焦 + 渐进多次聚焦 + 点击终端区聚焦；已用 192.168.12.100 实测双向输入输出。
> - 批量执行 CLI 输出原封不动（裸 `
` 归正为 `
`、保留缩进空格，修复成员端口排版错乱）。
> - FTP 服务端 STOR/APPE/MKD 异常兜底 + 被动端口固定 50000-50100（Windows 资源管理器 550 修复）。
> - 版本号：运维常用工具箱 `20260807-V2 → 20260807-V3`。

---


> **CMDB（20260807-V3）**：
> - **编辑资产「系统信息 / 端口信息」表尾按钮截断修复**：两表最后一列「删」按钮列 `fixed="right"` 固定贴右；「系统信息」登录方式列宽 145→160、端口「状态」列宽 90→110，下拉完整显示。IT 资产与办公/实物资产共用组件同步生效。
> - **维保管理剔除已报废资产**：维保查询增加 `status <> '报废'`，报废资产不再出现在「已过保 / 即将到期 (<30天)」与「正常在保」列表（报废后仅保留台账信息）。
> - 版本号：CMDB `20260807-V2 → 20260807-V3`；框架未改动。
>
> **数通配置卫士（20260807-V2）**：
> - 仪表盘「异常（红）」剔除禁用设备（禁用=退出管理，非异常）。
> - SNMP 查询 v3 新增自定义「用户名/用户报文认证方式/认证密钥/用户报文加密方式/加密密钥」输入（有自定义用自定义，否则回退设备已配置）。
> - SNMP v3 认证协议扩展（无认证/MD5/SHA/SHA-224/SHA-256/SHA-384/SHA-512，默认 SHA-256）、加密协议扩展（无加密/DES/3DES/AES-128/AES-192/AES-256，默认 AES-128）。
> - 网络拓扑「开始发现」后渲染崩溃修复（Vue3 插槽语法 + 空值保护）。
> - 版本号：数通配置卫士 `20260807-V1 → 20260807-V2`；框架未改动。
>
> **运维常用工具箱（20260807-V2）**：
> - 全量删除代码内 emoji（✅❌⚠📁📄🌐🖼 等 15 个文件；wiki 文档按用户要求保留）。
> - SSH 批量执行「设备终端」可用性增强（点击设备名进入交互 CLI，立即聚焦 + 挂载重试 5s）。
> - FTP 服务端显式 UTF-8 编码（Windows 资源管理器可正常操作文件）。
> - 浏览服务器目录支持任意绝对路径 / Windows 盘符下钻（修复盘内目录空白），可任选目录作为服务端根目录。
> - WebDAV 目录页美化（表格/面包屑/人类可读大小，1024 B → 1.0 KB）。
> - 客户端连接信息弹窗加宽（1500px）+ 分页条始终显示（默认 10/页，5/10/20/50 可选）。
> - 版本号：运维常用工具箱 `20260807-V1 → 20260807-V2`；框架未改动。

---

## 本期修复（20260810-V5 / 运维常用工具箱 20260810-V9 / 数通配置卫士 20260810-V8）

> 本期集中修复数通配置卫士与运维常用工具箱的浏览器全功能实测问题（12 项，全部实测通过），并根治插件前端缓存失效。

| # | 模块 | 现象 | 处理 |
| --- | --- | --- | --- |
| ① | SNMP v2c/v3 查询 | Community 留空时 v2c 设备查询失败；v3 默认不应回显明文凭据；v3 自定义（SHA-256/AES-128）凭据不生效 | 统一 SNMP 查询入口：Community 留空自动回退设备已存配置或 `public`；v3 默认不显示明文凭据；自定义 v3（User1 / SHA-256 / Cindy@921 / AES-128 / Cindy@221）查询成功并打印 NCDBG 请求/响应 |
| ② | 拓扑发现 | 快照时间比真实时间慢 8 小时（直接展示库内 UTC 值） | 统一走框架全局时间格式化（后端 UTC → 系统设置时区换算展示） |
| ③ | 网络测试 | 下载测试长时间转圈不返回 | 下载/上传按传输大小秒级完成（10MB / 100MB 均秒级返回，无无限转圈） |
| ④ | SSH 批量执行 | 批量执行后无法在结果区直接操作终端 | 批量执行后每台设备结果区内嵌可交互终端（xterm + WebSocket），多终端互不串扰，可直接输入命令并回显 |
| ⑤ | 交互终端长命令 | 连续相同字符被吞（如 `current` 双 r 变 `curent`、160 个 A 只剩十几个）；大写/空格双输出 | 终端输入去重由「内容 + 120ms 时间窗」改为「按键事件级互斥」（xterm onData 与 helper textarea 兜底共用同一按键 token），连续相同字符不再丢字，长命令输入与回显完全一致 |
| ⑥ | 任务时间 | 「上次执行」列显示 ISO 带毫秒、与真实时刻不符 | 统一展示 `YYYY-MM-DD HH:MM:SS`，与点击执行时刻一致（误差 ≤ 3s） |
| ⑦ | DEBUG 控制台 | 调为 DEBUG 后控制台无请求/响应打印 | 持久化日志级别，DEBUG 时在控制台打印请求体 / 错误响应（刷新后仍生效） |
| ⑧ | 插件前端缓存 | 插件 JS 改动后浏览器仍加载旧缓存 | 前端清单接口按文件 mtime 自动追加 `?v=`，插件 JS 一改动即失效缓存，不再依赖手工同步的全局版本号 |

> - 版本号：框架 `20260810-V4 → 20260810-V5`；运维常用工具箱 `20260810-V8 → 20260810-V9`；数通配置卫士 `20260810-V8`（本期未改动，沿用）、CMDB `20260809-V8`、Wiki `20260804-V1` 版本不变。

---

## 本期修复（20260810-V9 / 数通配置卫士 20260810-V9）

> 本期集中修复数通配置卫士网络拓扑与通知中心的 7 项用户反馈（①~⑦，浏览器全功能实测通过）。

| # | 模块 | 现象 | 处理 |
| --- | --- | --- | --- |
| ① | 网络拓扑 | 点击「开始发现」后旧拓扑整体消失 | 改为**增量合并**（discover `merge=true` 默认）：只更新所选设备及其关联链路，未涉及设备完整保留；发现失败的设备清除其旧链路（节点保留）。批量/定时任务「更新拓扑」同步改为合并语义，不再覆盖整体拓扑 |
| ② | 网络拓扑-链路明细 | 缺对端名称/对端端口名称/对端端口描述/IP 等 SNMP 可获取信息；未纳管设备被拆成多个节点 | 链路明细补齐 A/B 端名称、IP、接口、端口描述；未纳管设备按设备身份（sys_name/chassis_id/管理地址）聚合为单节点并标注「未纳管设备」+IP，同一设备经不同端口连接均汇于同一节点；CLI 邻居输出结构统一为 SNMP 同构（修复 CLI 链路对端信息丢失） |
| ③ | 网络拓扑-链路明细 | 纳管设备间链路信息不全 | 链路明细完整展示 A 端设备名称/IP、B 端设备名称/IP、A/B 端各自连接端口；拓扑图上连线双向标注「设备名:端口 ↔ 设备名:端口」 |
| ④ | 网络拓扑-发现明细 | 无法查看 SNMP 查询原始信息 | 发现明细新增「详情」按钮：SNMP 方式展示查询到的全部原始记录（**OID / 类型 / 值**，支持 10/20/50 分页）；CLI 方式展示实际下发命令 |
| ⑤ | 网络拓扑 | 明明配置了 SNMP 却仍用 CLI 查询 | 根因①：`snmp_lldp_discover` OID 解析边界错位（前缀 10 段误判 11 段），LLDP 记录被全部拒绝导致 SNMP 发现永远为空→永远降级 CLI，已修复；根因②：SNMP 查询失败/未开 LLDP 时自动降级 CLI 属设计兜底，现通过发现明细「SNMP 未生效原因」醒目提示（如「SNMP LLDP 未发现邻居（可能未开启 LLDP）」） |
| ⑥ | 网络拓扑-导出 HTML | 导出后拓扑图不能缩放/拖动 | 导出文件内嵌原生 JS 交互脚本（无外部依赖）：滚轮缩放、空白平移、节点拖拽 |
| ⑦ | 通知中心 | 低分辨率下「内容」列无法查看 | 内容列加宽（min-width 360）支持横向滚动，新增「查看」按钮弹窗展示完整内容（渠道/级别/状态/时间 + 全文） |

> - 版本号：数通配置卫士 `20260810-V8 → 20260810-V9`（仅本插件）；框架 `20260810-V5`、运维常用工具箱 `20260810-V9`、CMDB `20260809-V8`、Wiki `20260804-V1` 版本不变。

---

## 本期修复（20260810-V10 / 系统框架 20260810-V6 / 运维常用工具箱 20260810-V10 / CMDB 20260810-V9）

> 本期集中修复 25 项用户反馈（①~㉕，浏览器全功能实测 + 真实设备验证通过）。

| # | 模块 | 问题/需求 | 修复说明 |
|---|------|----------|---------|
| ① | 网络拓扑 | 拖动空白界面变成复制文字 | 拖拽 `preventDefault` + 画布 `user-select:none` |
| ② | 网络拓扑 | 选择设备/点击已纳管节点 → 发现明细联动 + 可查看详情 | 前端 watch 联动（seedIds/selectedNode → activeDeviceId 过滤发现明细）；详情弹窗展示邻居明细 + SNMP 原始记录；**发现明细 results 随快照持久化**（表加 results_json 列，刷新页面后仍可查看） |
| ③ | 网络拓扑 | 「拓扑图」与「设备详细信息」分区 | 画布区加「拓扑图」标题，tabs 区（链路明细/消失链路/发现明细）加「设备详细信息」标题 |
| ④ | 网络拓扑 | 端口名称/描述难分辨 | A 端端口标注靠近 A 端（18%）、B 端靠近 B 端（82%），白底描边（paint-order:stroke）嵌入物理链路 |
| ⑤ | 网络拓扑 | 200.5 与 203.15 直连却标未纳管 | 根因：LLDP 管理地址与设备库 ip 不一致 + CLI 无管理地址。修复：CLI 增加 verbose 邻居详情（华为 `display lldp neighbor-information verbose`、华三同构），采集本机 sysName 建立 sysName↔设备映射参与匹配；华三 list 表格按 header 字符位置定位列（原 2+ 空格切列错位导致设备名/端口错乱）；management address 子项（type/interface/oid）排除。实测 5↔6 双向纳管直连 |
| ⑥ | 网络拓扑 | 一台设备不止连 5 台却只显示 5 台 | 根因：CLI 解析器 `if local and dev:` 丢行 + 同一对端设备多端口被边去重合并成 1 条。修复：解析放宽（保留无设备名行）、边按端口粒度保留（key 加端口后缀）。实测设备5 显示 30 条链路（26 台 DS-3E1526P-S 独立节点） |
| ⑦ | 日志中心 | 没开 debug 却狂输出 debug | 根因：`core/logger.py` `setLevel(logging.DEBUG)` **硬编码 DEBUG**，忽略 core.yaml 配置 → 前端 NCDBG 联动狂输出。修复：日志级别跟随 core.yaml `logging.level`（默认 INFO） |
| ⑧ | 网络拓扑-发现明细 | 详情弹窗展示完整查询信息 | 弹窗新增「查询明细（邻居）」表格：本端端口/描述、对端设备名/端口/描述/IP；SNMP 显示原始记录（OID/类型/值，10/20/50 分页），CLI 显示命令 |
| ⑨ | 网络拓扑 | SNMP 正确仍走 CLI + 提示矛盾 | 修复 OID 解析边界错位（同⑤ 相关）；LLDP 表空时先探测 sysDescr 区分「SNMP 不可达/Community 错」与「LLDP 表空」，发现明细醒目提示（如「SNMP 可达但 LLDP-MIB 无邻居条目」） |
| ⑩ | 网络拓扑-导出 HTML | 导出后不能缩放/拖动 | 根因①：SVG 已有 id 时后端不再强制加 `id="ncTopo"`，脚本按 id 查找失败；根因②：`tagName === 'G'` 大小写不匹配（SVG tagName 为小写）导致脚本早退。修复：统一强制 SVG id + 脚本多 id 兜底 + tagName 转小写比较。实测缩放/平移/拖拽全部生效 |
| ⑪ | 系统设置-基础设置 | HTTPS 功能 | core.yaml 加 `https.enabled`（默认 true）；未配置证书自动生成自签名证书（data/certs/）；支持上传自定义证书（.crt/.pem 证书 + .key 私钥，仅限对应扩展名）；uvicorn 加 ssl 参数；无证书/失败自动回退 HTTP 并提示 |
| ⑫ | 系统设置-基础设置 | 时区开关不在配置文件 | `user_config.yaml` 模板加 `system.timezone`（默认 Asia/Shanghai）+ `system.auto_update_timezone`（默认 true），GET 兜底读取 |
| ⑬ | 网络测试 | 下载默认变 10M | 默认改回 **100MB**，上限 2048 → **10240（10GB）**，超限禁用提示同步更新 |
| ⑭ | SSH 批量执行 | 等待 10 秒 + 命令不显示 | 根因：`_read_full_output` 默认 `idle_limit=0.3`——华为/华三设备输出分批到达（批次间隙 0.5~1s）被误判静默结束，只抓到命令回显、结果全丢。修复：idle_limit 0.3 → 1.0。实测 4.8s 返回完整输出（version + lldp 邻居） |
| ⑮ | CMDB | 编辑资产-系统信息取消「密码」列 | 编辑表格删除密码列（既有密码仍加密保存）；详情查看保留掩码显示（显示/隐藏切换） |
| ⑯ | 网络拓扑 | 界面美化 | 节点卡片化（渐变/阴影/圆角）、连线按两端类型着色（双纳管蓝色实线、涉未纳管琥珀虚线）、hover 高亮（节点描边加粗、连线加亮加粗）、图例完善 |
| ⑰ | 路由追踪 | MTR 收/发恒 0/0 + 缺表头 | 后端解析实际收/发/丢计数（received/probes_sent/probes_lost，正常/超时/部分丢失三场景单测通过）；结果区加「MTR 信息」表头 |
| ⑱ | DNS 探测 | 支持 DoT/DoH/IPv4/IPv6 + 提示 | 后端支持 plain / DoT（853，TLS）/ DoH（443，dns-message POST，跳过证书验证便于内网）；前端服务器方式选择 + 常用公共 DNS 提示（阿里 223.5.5.5 / 腾讯 119.29.29.29 / Google 8.8.8.8 / Cloudflare 1.1.1.1 + IPv6 等） |
| ⑲ | FTP/SFTP 客户端 | 匿名登录勾选 | 勾选后用户名/密码禁用 |
| ⑳ | FTP/SFTP 客户端 | 用户名为空 = 匿名 | 提交时用户名空/勾选匿名统一按 anonymous 处理 |
| ㉑ | 文件服务端 | 连接信息用户名/密码点击复制 | 展开行用户名/密码点击复制（clipboard + 降级 textarea） |
| ㉒ | 文件服务端 | 匿名登录勾选 | 创建表单加匿名勾选，勾选后用户名/密码禁用（后端密码空即匿名） |
| ㉓ | FTP 服务端 | Windows 资源管理器 550 Invalid argument | 根因：wininet 对含空格路径用双引号包裹（`STOR "a b.txt"`），pyftpdlib 不解析引号 → 创建含 `"` 路径 → OSError(22)。修复：`abstracted_fs` 子类重写 `ftp2fs` 剥离首尾引号。实测引号 MKD/STOR/NLST/DELE/RMD 全通过、中文无引号无回归 |
| ㉔ | TOTP | 二维码图片是 gif | `qrcode_lib.js` 输出优先 canvas webp（浏览器不支持回退 gif） |
| ㉕ | TOTP | parse 解析 build 的 URI 失败 | parse 增加 `urllib.parse.unquote` 解码（build 用 quote 编码，中文 issuer/特殊字符 URI 可正确往返），容忍粘贴换行 |

> - 版本号：系统/框架 `20260810-V5 → 20260810-V6`（HTTPS、时区配置、日志级别根因修复）；数通配置卫士 `20260810-V9 → 20260810-V10`；运维常用工具箱 `20260810-V9 → 20260810-V10`；CMDB `20260809-V8 → 20260810-V9`；Wiki `20260804-V1` 不变。
> - 新增可调 API：`POST /api/system/https/cert`（上传证书/私钥）、`POST /api/system/https/switch`（HTTPS 开关）；`GET /api/system/basic-settings` 返回 `https.{enabled, custom_uploaded}`。

---

## 上期模块化（20260805-V2 / 数通配置卫士 20260805-V1）

> 本轮仅做代码结构重组，**功能与对外接口完全不变**；下列为拆分说明，便于后续维护定位。

- **运维常用工具箱前端 `tools.js`（1813 行）→ 7 个模块**：`tools_00_common.js`…`tools_06_misc.js`（数字前缀保证经 `/api/plugins/frontend-manifest` 注入顺序与原单文件一致），共享函数经 `window.OT` 命名空间复用。
- **运维常用工具箱 `ipcalc.py`（880 行）→ `ipcalc/` 包（10 模块）**：`stddb / helpers / v4_* / v6_* / stdlib` 按功能域拆分，逐字节保留原函数体；对外契约 `TOOL_ID` / `run(params)` / `_FUNCS` 分发表不变（29 功能键、handler 名、函数体经 AST 校验零差异）。
- **数通配置卫士 `db.py` / `engine.py` / `routes.py` → `db/` / `engine/` / `routes/` 三个包（共 40 模块）**：路由 43 条、工具分发表与 API 表面零变化，`register_routes` 按原顺序逐域注册。
- 版本号随之提升：运维常用工具箱 `20260805-V1 → V2`、CMDB `20260805-V1 → V2`、数通配置卫士 `20260804-V1 → 20260805-V1`；框架 / Wiki 版本不变。

---

## 五、常见问题

- **登录后页面狂刷新：在 旧版本中，前端对 401 响应执行整页 `location.reload()`，与轮询受保护接口的组件叠加会形成刷新死循环。：401 时清除本地令牌并派发 `nc-unauthorized` 事件，由主应用 SPA 内部切回登录视图，不再整页重载。
- **版本号显示异常（如显示旧编号）：程序右下角显示的是 `GET /api/system/info` 的 `version` 字段，来自 `core/config_loader.py` 的 `SYSTEM_VERSION`（可被 `user_config.yaml` 的 `system.version` 覆盖）。若显示旧值，请确认运行的是最新构建的程序。
- **端口被占用：程序会自动顺延端口，请查看控制台实际地址；或在 `config/core.yaml` 的 `server.port` 中固定端口。
- **程序体积约 100MB / UPX 压缩说明：EXE 为 PyInstaller 单文件，体积主要来自原生依赖——OpenCV（二维码识别，约 40MB）、numpy 运行库、Python 标准库与 FastAPI/uvicorn 等。PyInstaller 已对内置 CArchive 做 zlib 压缩（成品约 101MB）。本项目已在 `build.py` 启用 UPX（`upx=True` 且内置 `tools/upx.exe`），但 UPX 4.2.4 **不压缩 PE 的 overlay 区**（PyInstaller 把全部 payload 放在 overlay），故对本程序 UPX 实测仅 ~99.9%、几乎无效；有效压缩来自 PyInstaller 的 zlib。若要更小体积只能精简所收集的依赖（如改用 pyzbar 单独解码以去掉 OpenCV），但按需求未裁剪模块，故维持现状。
- **批量更新配置报 `TCP 连接设备失败` / 设备不可达：若报错为「TCP 连接失败」且为固定某台/某几台设备，通常是目标设备网络不可达（IP 错误、链路中断、ACL 拦截、设备已下线），**属于环境/配置问题而非程序 Bug**；请先 `ping`/Telnet 该设备 IP:22 确认可达性，再核对「设备管理」中该设备的 IP/端口/凭据。真正的程序 Bug 表现为 `SSH 协议握手失败 / Incompatible ssh peer`（见上方主机密钥修复）。
- **`/api/system/menus` 偶发 401：仅在浏览器残留旧令牌（`NC_TOKEN`）未清理、又以已登出状态访问时出现；框架拦截器会自动清除无效令牌并跳回登录页，重新登录即恢复正常，非程序缺陷。

---

## 六、开发模式运行与测试

```bash
# 安装依赖
pip install -r requirements.txt

# 开发运行
python main.py

# 端到端冒烟测试（需先启动服务）
python tests/smoke_ops.py # 运维工具箱冒烟
python tests/qa_ops_full.py # 全量 QA
```

更多构建与交付说明见 `wiki/06-构建与交付.md`。
