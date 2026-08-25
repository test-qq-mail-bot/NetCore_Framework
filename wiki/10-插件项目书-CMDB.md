# CMDB 资产配置管理插件开发项目书

> 版本：**20260809-V8** ｜ 适用框架：**NetCore Framework 20260805-V1**
> 作者：NetCore Team
>

## 一、概述

CMDB 插件用于统一管理企业 IT 资产与实物资产，覆盖：资产台账、机柜 U 位可视化、
端口连接拓扑、维保到期预警与报表导出。灵感来自用户提供的 EAM 统一资产管理 Demo
（`deepseek_html_20260723_520b3f.html`），按其 6 个视图重写为框架原生 **Vue 3 +
Element Plus** 插件，复用框架登录态、左侧菜单、主题与错误隔离，数据持久化于 SQLite。

## 二、功能模块（6 个二级页面）

| 页面 | 路径 | 说明 |
| --- | --- | --- |
| 资产仪表盘 | `/cmdb/dashboard` | 资产总数/总原值、IT 资产数、机柜 U 位占用、即将过保（<30天）；最近资产表 |
| IT 资产 | `/cmdb/it-assets` | IT 设备台账（**资产列表 + 机柜视图**双标签，机柜视图从办公/实物资产迁入），支持搜索/分页、新建/编辑/删除、资产详情与端口编辑，机柜详情中占用设备可直接查看/编辑 |
| 办公/实物资产 | `/cmdb/physical` | 非 IT 资产（办公家具/生产设备）列表（机柜视图已迁至 IT 资产页） |
| 维保管理 | `/cmdb/maintenance` | 已过保/即将到期清单 + 正常维保清单，支持续保（模拟） |
| 报表中心 | `/cmdb/reports` | 资产盘点报表 / 部门资产汇总 / 维保到期预警，支持 HTML 与 CSV 导出 |

## 三、数据模型（SQLite，库文件 `plugins/cmdb/data/cmdb.db`）

- **assets**（机柜以外的所有资产）：`asset_no`（唯一，自动生成 IT-/OF-/PE- 前缀）、
  `name`、`category`（IT设备/办公家具/生产设备）、`subtype`、`user`、`dept`、`location`、
  `status`、`brand`、`model`、`sn`、`contract_no`、`supplier`、`purchase_date`、`price`、
  `warranty_months`、`warranty_expire`、`note`、`rack_id`、`u_start`、`u_height`、
  `is_network_device`、`config`（JSON）。
- **racks**：`rack_id`（唯一）、`name`、`location`、`total_u`、`status`、采购/保修字段。
- **ports**：`asset_id`（FK）、`port_num`、`name`、`speed`、`remote_device`、
  `remote_port`、`note`、`status`（connected/disconnected/disabled）。

首次加载（`on_load`）调用 `seed_if_empty()` 写入 5 台机柜与 11 项资产种子数据（含
端口连接），与 Demo 一致。

## 四、后端 API（前缀 `/api/cmdb`，均需登录）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/dashboard` | 仪表盘统计 |
| GET | `/assets` | 列表 `?page&size&search&category&exclude_category` |
| POST | `/assets` | 新建（自动编号，接受 `ports`） |
| GET/PUT/DELETE | `/assets/{id}` | 详情 / 更新（接受 `ports`）/ 删除 |
| POST | `/assets/batch-update` | **批量更新盘点时间**：body `{ids:[int], inventory_time:"YYYY-MM-DD"}`；事务内更新 `inventory_time` 与 `updated_at`，跳过不存在的 id，返回 `{success, updated}`；`inventory_time` 非法或 `ids` 为空返回 400 |
| GET/PUT | `/assets/{id}/ports` | 端口读取 / 覆盖更新 |
| GET/POST | `/racks` `(/{rack_id})` | 机柜列表 / 新建 / 详情 |
| DELETE | `/racks/{rack_id}` | 删除机柜（`?force=1` 先解绑下架内部设备再删，资产台账保留；机柜内有设备默认返回 400 含 `devices` 数） |
| POST | `/assets/{id}/unbind-rack` | 单台资产移出机柜（仅解绑 U 位，资产台账保留） |
| GET | `/topology` | 端口连接拓扑 |
| GET | `/maintenance` | 维保列表 |
| GET | `/reports/export` | 报表导出 `?type=inventory\|dept\|warranty&format=html\|csv` |
| GET | `/backup/export` | **全量备份导出**：返回含全部机柜/资产/端口的 JSON 附件 `cmdb_backup_YYYYMMDD_HHMMSS.json` |
| POST | `/backup/import` | **备份导入/恢复**：body `{content, mode}`；`mode=merge`（默认）或 `overwrite` |
| POST | `/demo-data/restore` | **手动恢复演示数据（20260806-V1 新增）**：把内置示例机柜/资产/端口重新写入数据库。**仅在用户主动调用时执行，程序启动不会自动播种** |

### 4.1 备份导出/导入

**后端实现（`plugins/cmdb/common.py` + `plugins/cmdb/modules/backup.py`）**：

- `BACKUP_VERSION = "20260804-V4"`（备份文件格式版本，独立于插件版本号）；`EXPORT_ASSET_FIELDS`(23) / `EXPORT_RACK_FIELDS`(12) / `EXPORT_PORT_FIELDS`(7) 定义导出字段白名单（位于 `modules/backup.py`）。
- `export_all()` → `{"meta": {...}, "racks": [...], "assets": [{...,"ports":[...]}]}`，资产内嵌端口，机柜/端口配置经 `_serialize_config()` 序列化。
- `import_all(data, mode="merge")` → `{success, mode, added, updated, skipped, racks_added, racks_updated, errors, total_after}`：
  - `merge`：按 `asset_no` 优先、其次 `sn` 匹配，命中更新（`_update_asset_full`）否则新增（`_insert_asset_full`）；机柜按名称/编号 `_upsert_rack`。
  - `overwrite`：先 `DELETE FROM ports/assets/racks` 再全量导入。
  - 逐条 `try/except` 累积 `errors`，单条失败不中断整体导入。

**前端入口**：
- `cmdb_reports.js`「数据备份与恢复」卡片：全量导出按钮 + 文件选择 + 模式单选（合并/覆盖）+ 结果提示。
- `cmdb_it.js` / `cmdb_physical.js` 列表页头部「导出备份 / 导入备份」按钮（导入默认合并模式并即时刷新列表）。
- 上传遵循框架惯例：`FileReader.readAsText()` 读取后以 `{content, mode}` JSON body 提交（非 multipart）；覆盖模式前端 `$confirm` 二次确认。

## 五、前端结构

- `plugins/cmdb/frontend/cmdb_common.js`：一次性注入插件样式；注册两个**共享组件**
  `CmdbAssetForm`（新建/编辑 + 端口编辑）与 `CmdbAssetDetail`（只读详情 + 端口表 + 操作）。
  二者通过 `window.NC.registerPage(...)` 注册为全局 Vue 组件，供各页面复用。
- `cmdb_dashboard.js` / `cmdb_it.js` / `cmdb_physical.js` / `cmdb_topology.js` /
  `cmdb_maintenance.js` / `cmdb_reports.js`：6 个页面，分别 `registerPage` 为
  `cmdb_dashboard` 等页面 id。
- 框架启动后由 `/api/plugins/frontend-manifest` 动态注入这些 JS；页面通过
  `window.NC.PAGES` 注册，由 `frontend/app.js` 的 `resolvePageId()` 映射路径到页面 id
  （已在 `app.js` 中新增 6 条 `/cmdb/*` 映射，沿用 guardian/opstoolbox 既有惯例）。
- 报表下载沿用框架既有鉴权下载模式：`http.get(url, { responseType: 'blob' })` +
  `URL.createObjectURL` + `<a>` 触发，自动携带 Bearer 令牌。

## 六、与框架集成要点

- 继承 `core.plugins.base_plugin.BasePlugin`，实现 `get_metadata / on_load /
  get_routes / get_menus`。
- `get_routes()` 返回 `APIRouter(prefix="/api/cmdb")`，接口用 `core.auth.get_current_user`
  鉴权；写操作接 `core.audit.audit_log`。
- `get_menus()` 返回含 6 个子项的 CMDB 菜单，经 `/api/system/menus` 自动聚合。
- 存储沿用 `core.config_loader.PLUGINS_DIR` 下的 `data/` 子目录（打包时 `_EXTRACT_SKIP_SUBDIRS`
  确保运行时数据不被覆盖）。

## 七、测试

- `tests/smoke_cmdb.py`：隔离冒烟（仅挂载 CMDB 路由，绕过鉴权），覆盖 6 模块 API 与菜单结构；
  隔离 `DB_PATH` 至临时库，额外验证备份导出/导入往返（merge 空操作、merge +1、overwrite 恢复、
  空内容 400、非法 JSON 400）。
- `tests/smoke_cmdb_full.py`：完整框架端到端（`with TestClient(app)` 触发生命周期启动，
  验证 manifest 含 7 个前端文件、菜单聚合 CMDB、路由挂载），并含备份导出（200/JSON/资产>0）
  与 merge 重导入安全性（总数不变）校验。

## 八、依赖

仅依赖 Python 标准库（sqlite3 / json / csv / datetime），无需第三方依赖。

## 附录：源码体检修复

- `cmdb.common` 开 WAL + `busy_timeout=5000`，缓解多标签页/多用户并发写偶发 `database is locked` → HTTP 500。
- 资产表单补「资产子类」字段，与后端 `subtype` 列、列表/详情/报表展示对齐（此前表单无该输入项、子类永远为空且无法编辑）。
- 清空某网络设备全部端口时复位 `is_network_device=0`，避免无端口却仍被当网络设备的拓扑/统计口径不一致。

## 附录：功能清单

1. **添加资产按页面限定分类**：IT 资产页新建/编辑只允许「IT设备」；办公/实物资产页只允许「办公家具/生产设备」（默认办公家具），共享表单组件 `CmdbAssetForm.open(asset, {categories, defaultCategory})` 按页面注入分类白名单。
2. **子类随分类联动**：`CMDB_SUBTYPE_OPTIONS` 按分类给出常用子类下拉（IT设备：交换机/路由器/服务器/防火墙…；办公家具：办公桌/办公椅/文件柜…；生产设备：机床/产线设备/检测仪器…），支持搜索与自定义输入（allow-create），切换分类自动清空子类与机柜关联。
3. **新建表单 UI 美化**：「常用信息」卡片默认展开 6 项（资产分类/名称/子类/品牌/型号/序列号SN + 备注），「采购信息 / 归属与位置 / 端口配置」以 el-collapse 折叠收纳。
4. **打印标签离线二维码**：标签左信息右二维码布局，二维码内容封装资产编号/名称/分类/品牌型号/SN/使用人/位置；由内嵌 `qrcode_lib.js`（qrcode-generator 1.4.4，MIT）经 `CMDB_QR_DATAURL()` 本地生成，纯离线不调后端；删除「NetCore 资产标签」标题文字。
5. **机柜视图迁移 + 可编辑**：机柜视图从办公/实物资产页迁至 IT 资产页（双标签），机柜详情弹窗 U 位占用行新增「详情/编辑」按钮直接打开该设备的详情/编辑窗口。
6. **取消端口拓扑**：删除菜单项、前端 `cmdb_topology.js`、后端 `modules/topology.py` 与 `GET /api/cmdb/topology` 路由，子菜单 6 → 5 项。
7. **盘点时间**：`assets` 表新增 `inventory_time TEXT` 列（老库启动自动 `ALTER TABLE` 迁移）；新建/编辑表单「归属与位置」区及资产详情页均含「盘点时间」日期控件（可选/可改/可清除），详情页显示「已盘点/未盘点」标签，用于资产盘点核对。

## 九、变更记录



### 20260809-V8（本期，需求①）

- 版本号：CMDB 插件 `20260809-V7 → 20260809-V8`；框架未改动。
- ① **编辑资产「系统信息 / 端口信息」操作列按钮文本**：`删` 改为 `删除`（两处，语义更清晰，避免单字误触）。
- 验收（测试环境 8099 实机）：前端资源断言（两处按钮文本为「删除」、无残留单字「删」）通过；服务日志零报错。



- 版本号：CMDB 插件 `20260809-V6 → 20260809-V7`；框架未改动。
- ① **编辑资产「系统信息 / 端口信息」高分辨率自适应铺满**：列由固定宽度改为 **min-width 自适应**——
  高分辨率下 el-table 自动拉伸填满弹窗宽度（不再右侧空白），窄屏压缩到最小宽后出现横向滚动条可拖拽；
  操作列保留 min-width 且有表头「操作」、无 fixed 冻结（随表滚动）。弹窗维持 96vw。
- **验收（测试环境 8099 实机）**：前端资源断言（系统表/端口表 min-width 列、操作列表头、无 fixed）全部通过；服务日志零报错。



- 版本号：CMDB 插件 `20260808-V5 → 20260809-V6`；框架未改动。
- ① **编辑资产「系统信息 / 端口信息」内容完整显示 + 横向滚动**：两表列由 min-width 自适应改为**固定宽度**（内容完整显示，不压缩输入框）；列总宽超出弹窗容器时 el-table 自动出现**左右横向滚动条可拖拽**；「操作」列**增加表头**（原为空表头）。
- ② **操作列不冻结**：两表操作列确认无 `fixed`，随表格横向滚动（不固定不动）。
- **验收（测试环境 8099 实机）**：登录 200；前端资源断言（操作列表头 ×2、固定宽度列、无 fixed、横向滚动）全部通过；服务日志零报错。



- 版本号：CMDB 插件 `20260807-V4 → 20260808-V5`；框架未改动。
- ① **编辑资产「系统信息 / 端口信息」全分辨率适配（响应式）**：
  - 弹窗改 `width=90vw + max-width:1280px`（替代固定 1180px），电脑不挤压、手机不溢出；
  - 两表列由固定 width 改为 **min-width 自适应**——表头按容器宽度全分辨率显示，不再固定宽度；
  - 新增媒体查询：`@media(max-width:768px)` 手机端 label 100→84px、按钮全宽；`@media(max-width:480px)` label 70px、字号缩小——常用手机/电脑分辨率适配。
- ② **操作栏不冻结**：两表删除列确认**无 `fixed`**（随表横向滚动，不固定）。
- **验收（测试环境 8099 实机）**：前端资源断言 `90vw/max-width:1280px/min-width 列/媒体查询/无 fixed` 全部通过；服务日志零报错。



- 版本号：CMDB 插件 `20260807-V3 → 20260807-V4`；框架未改动。
- ①⑫ **编辑资产「系统信息 / 端口信息」按钮截断 + 操作栏冻结修复（彻底解决）**：
  - 弹窗 `960px → 1180px`，内容区约 1030px，两张内嵌表格（系统信息 650px / 端口信息 810px）全部列完整显示，不再被压缩/裁剪；
  - **移除上一轮误加的 `fixed="right"` 冻结列**——操作栏（「删」按钮）恢复随表格横向滚动，不再固定冻结（需求②）；
  - 端口表列宽整体瘦身（端口号 65→60、名称 90→85、速率 75→70、MAC 115→110、IP 115→110、对端设备 95→90、对端端口 80→75、备注 70→65、状态 110→100），总宽 860→810px；
  - IT 资产与办公/实物资产共用该组件，同步生效。
- **验收（测试环境 8099 实机）**：登录 200；前端资源断言 `width="1180px"`、无 `fixed="right"`、端口表列宽生效全部通过；服务日志零报错。



- 版本号：CMDB 插件 `20260807-V2 → 20260807-V3`；框架未改动。
- ① **编辑资产「系统信息 / 端口信息」表尾按钮截断修复**：`cmdb_common.js` 两表最后一列（「删」按钮列）加 `fixed="right"` 固定贴右，窄窗口下不再被压缩截断；「系统信息」登录方式列宽 145→160、端口「状态」列宽 90→110，下拉选项显示完整。IT 资产与办公/实物资产共用该组件，同步生效。
- ⑪ **维保管理剔除已报废资产**：`maintenance.py / common.py` 的维保查询条件增加 `AND status <> '报废'`——报废资产不再出现在「已过保 / 即将到期 (<30天)」与「正常在保」列表（报废后仅保留台账信息，不参与维保到期提醒）。
- **验收（测试环境 8099 实机）**：登录 200；`POST /api/cmdb/assets` 造「报废+已过保」资产后 `GET /api/cmdb/maintenance` 确认不在 expiring/normal，同时在保资产仍在 normal；前端资源断言 `fixed="right"`、列宽 160 生效；服务日志零报错。

### 20260807-V2（本期，需求①②）

- 版本号：CMDB 插件 `20260807-V1 → 20260807-V2`；框架未改动。
- ① **IT 资产 / 办公实物资产列表每页条数可切换**：默认每页 **10 条**，新增下拉可选 **5 / 10 / 20 / 50** 条/页（`el-pagination` 增加 `:page-sizes` 与 `sizes` 布局，切换时回到第 1 页重载）。注：翻页能力此前已存在，本项主要补齐「默认 10 条 + 条数切换器」。
- ② **IT 资产 / 办公实物资产列表多选 + 批量更新盘点时间**：
  - 表格新增多选列（`row-key="id"` + `reserve-selection`，支持跨页累计勾选）；
  - 搜索栏新增「批量更新盘点时间」按钮（未勾选时禁用并显示已选数量）；
  - 点击弹出日期选择框（`el-date-picker` YYYY-MM-DD），选定后二次确认「确认将选中的 N 台设备盘点时间更新为 YYYY-MM-DD？」；
  - 确认后调用新增后端接口 `POST /api/cmdb/assets/batch-update` 批量写入，成功后清空选择并刷新列表。
  - 两列表均新增只读「盘点时间」列，便于核对批量结果。
- 后端新增 `modules/assets.py: batch_update_inventory_time(ids, inventory_time)`（单事务内更新 `inventory_time`+`updated_at`，跳过不存在 id，校验 YYYY-MM-DD）与路由 `POST /assets/batch-update`（含日期/空 ids 校验与审计日志）。

**接口变化**：

- `POST /api/cmdb/assets/batch-update`：请求 `{ids:[int], inventory_time:"YYYY-MM-DD"}`；成功 `{success:true, updated:N}`，非法日期/`ids` 空返回 400。
- `GET /api/cmdb/assets`：分页参数 `size` 现支持 5/10/20/50，前端默认 10。

**验收（客户身份实测，测试文件夹实机）**：默认账号登录 ✅；分页切换 5/10/20/50 返回条数与 total 正确 ✅；多选跨页累计 + 批量更新 3 台盘点时间为 2026-08-07 ✅；列表「盘点时间」列回显 ✅；边界（非法日期/空 ids/未授权）正确拦截 ✅；服务运行期日志零报错 ✅。

### 20260807-V1（本期，需求①②）

- 版本号：CMDB 插件 `20260806-V2 → 20260807-V1`；框架未改动。
- ① **办公/实物资产取消「存储大小」「内存大小」**：编辑表单与资产详情均改为仅 IT 设备（`category === 'IT设备'`）展示；办公家具/生产设备不再显示这两个 IT 专有字段。
- ② **编辑资产「系统信息」「端口信息」按钮区 UI 修复**：按钮行改弹性布局（flex + 自动换行），窄屏不再挤压/功能显示不全。

### 20260806-V2（本期，需求①②⑩⑪）

**变更内容**：

1. **编辑资产 UI 修复（需求①）**：「系统信息」「端口信息」表格列宽压缩并强制 100% 宽、弹窗加宽至 960px，全部列完整显示不再错乱/截断；登录方式选「其他」时出现**自定义方式输入框**（字段 `custom_method`），保存后详情页显示「其他(自定义值)」。
2. **添加端口按钮符号修复（需求②）**：移除 `<i class="el-icon">＋</i>` 错误写法（渲染为乱码字符），改为纯文本「＋ 添加端口」。
3. **端口信息新增 MAC/IP（需求⑩）**：`ports` 表新增 `mac`/`ip` 列（建表 + 老库自动迁移），表单端口表新增「MAC 地址」「IP 地址」输入列，资产详情页端口表同步显示。
4. **常用信息新增颜色/存储/内存（需求⑪）**：`assets` 表新增 `color`/`storage`/`memory` 列（建表 + 老库自动迁移）；表单「常用信息」新增 3 个字段；资产列表页新增对应列并支持**搜索查询**（`GET /api/cmdb/assets?search=` 扩展匹配 color/storage/memory）；详情页「基础信息」区展示。

**接口变化**：

- `POST/PUT /api/cmdb/assets`：支持 `color` / `storage` / `memory` 字段；端口条目支持 `mac` / `ip` 字段。
- `GET /api/cmdb/assets?search=`：搜索范围扩展至 `name/asset_no/user/dept/location/sn/color/storage/memory`。
- `GET /api/cmdb/assets/{id}`：返回 `color/storage/memory` 与端口 `mac/ip`。

**验收**：客户身份实测——创建/更新带新字段资产 ✅、端口 MAC/IP 存取 ✅、登录方式「其他」自定义存取 ✅、按颜色/存储/内存搜索 ✅、列表/详情新列展示 ✅；老库迁移（ALTER TABLE ADD COLUMN）在全新库与升级库均验证 ✅。

版本号：CMDB 插件 `20260806-V1 → 20260806-V2`；框架未改动，保持 `20260805-V1`。

### 20260806-V1（历史，需求①）



**问题**：客户反馈「CMDB 资产管理里删除了所有数据后，重启软件又会被添加回来」。



**根因**：演示数据播种逻辑写在启动流程里，判定条件是「表为空则写入示例数据」。客户把资产删光后，表恰好为空，下次启动即被判定为「首次初始化」而重新播种。



**修复（`plugins/cmdb/common.py`）**：



1. `seed_if_empty()` 改为**一次性播种**——首次写入示例数据后，在 `meta` 表落一个 `demo_seeded=1` 标记；此后每次启动先读该标记，**已标记则直接返回，完全跳过播种逻辑**。判定依据由「表是否为空」改为「是否播种过」，与数据量彻底解耦。

2. **老库迁移兜底**：从 20260806-V1 之前的版本升级上来的数据库没有该标记，若检测到「无标记但已有数据」，则**只补写标记、不重新播种**，避免升级后出现一次「删了又回来」。

3. 新增 `restore_demo_data()` 与 `POST /api/cmdb/demo-data/restore`，把恢复演示数据变成**用户主动触发**的动作，用于演示或培训场景。



**验收（客户身份实测）**：



| 场景 | 操作 | 重启后结果 |

| --- | --- | --- |

| 删除部分资产 | 删若干条 | 保持删除后的数量，无回灌 |

| 删光全部资产 | 资产 11 → 0 | `assets=0`，无回灌 |

| 资产 + 机柜全清空 | 资产 0、机柜 5 → 0 | `assets=0`、`rack_count=0`，无回灌 |

| 手动恢复 | 调 `/demo-data/restore` | 示例数据完整回来，可再次删光且仍不回灌 |



版本号：CMDB 插件 `20260805-V2 → 20260806-V1`；框架未改动，保持 `20260805-V1`。



---



### 20260805-V1（历史）

- **框架版本升至 20260805-V1**：因 `frontend/app.js` 登录逻辑修复（见下），框架版本号同步提升。
- **Bug 修复 · 机柜视图删除能力缺失**：新增 `DELETE /api/cmdb/racks/{rack_id}`（支持 `?force=1` 解绑下架后删除，资产台账保留）与 `POST /api/cmdb/assets/{id}/unbind-rack`（单台资产移出机柜，仅解绑 U 位）。前端机柜卡片、U 位详情弹窗、设备行分别新增「删除」「移出」入口，机柜含设备时二次确认防护。
- **Bug 修复 · 登录字段解密告警**：`frontend/app.js` 登录提交补上对 `username` 的 AES-256-GCM 加密，消除控制台「字段解密失败，已按明文处理」WARNING（根因为此前 username 明文提交、后端统一按密文解密失败回退）。后端 `core.api` 保留明文兼容。

### 20260805-V2（历史）

- **版本对齐**：本轮 CMDB 无功能性代码变更；版本由 `20260805-V1` 提升至 `20260805-V2`，仅随本次交付批次（运维工具箱与数通配置卫士模块化）对齐，便于统一追踪。**功能与接口不变**。
