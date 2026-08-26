// 路径: /system/log-center
// 日志中心（原 LogCenterPage，日志级别 + 登录/审计日志合并）
// 主要功能：调整运行时日志级别、查询/导出审计日志、清理审计日志。
// 关键接口：PUT /api/system/log-level、GET /api/logs/audit、GET /api/logs/audit/export、DELETE /api/logs/audit/clean。
window.NC.registerPage('core_logs', {
    template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">日志级别</h2>
        <div class="nc-form-card">
          <el-alert v-if="loadError" type="error" :closable="false" :title="'数据加载失败：' + loadError" style="margin-bottom:12px;"></el-alert>
          <div class="nc-toolbar">
            <el-select v-model="level" style="width:200px;">
              <el-option v-for="l in levels" :key="l" :label="l" :value="l"></el-option>
            </el-select>
            <el-button type="primary" @click="applyLevel">应用</el-button>
          </div>
        </div>
      </div>
      <div class="nc-section">
        <h2 class="nc-section-title">登录 / 审计日志</h2>
        <div class="nc-table-card">
          <nc-table :data="allRows" :columns="cols" client-paged :page-size="size" :page="page"
                    :page-sizes="[5,10,20,50]" @page-change="(p)=>{page=p;}"
                    @size-change="(s)=>{size=s;page=1;}">
            <template #col-timestamp_utc="{row}">{{ fmtTime(row, null, row.timestamp_utc) }}</template>
            <template #col-result="{row}"><el-tag :type="row.result==='success'?'success':'danger'">{{row.result}}</el-tag></template>
            <template #pager-extra><el-button @click="exportCsv">导出CSV</el-button></template>
          </nc-table>
        </div>
      </div>
    </div>`,
    mixins: [window.NC.SF_MIXIN],
    data() { return { level: 'INFO', levels: ['DEBUG', 'INFO', 'WARNING', 'ERROR'], allRows: [], page: 1, size: 10, loadError: '', levelLoading: false }; },
    computed: {
        cols() {
            return [
                { label: '时间', prop: 'timestamp_utc', width: 220, sortable: true, filterable: true, slotName: 'col-timestamp_utc',
                  // 筛选下拉框选项标签同步格式化（换算时区、去 T/Z/毫秒），
                  // 否则选项列表会显示原始 UTC 串（如 2026-08-26T07:36:57.569Z）
                  valueFormatter: function (v) { return (window.NC && window.NC.fmtTime) ? window.NC.fmtTime(v) : String(v); } },
                { label: 'IP', prop: 'ip', width: 140, sortable: true, filterable: true },
                { label: '操作', prop: 'action', width: 180, sortable: true, filterable: true },
                { label: '结果', prop: 'result', width: 100, sortable: true, filterable: true, slotName: 'col-result' },
                { label: '详情', prop: 'detail', sortable: true, filterable: true },
            ];
        },
    },
    methods: {
        fmtTime(row, column, value) {
            if (!value) return '';
            if (window.NC && window.NC.fmtTime) return window.NC.fmtTime(value);
            const d = new Date(value);
            if (isNaN(d.getTime())) return value;
            return d.toLocaleString();
        },
        // 'INFO' 且 mounted 只 load 审计日志，导致在 user_config.yaml 或其它标签页改了
        async loadLevel() {
            this.levelLoading = true;
            try {
                const r = await http.get('/api/system/log-level');
                const lv = (r.data && r.data.level) || 'INFO';
                this.level = lv;
                if (window.NC_LOG_LEVEL !== lv) window.NC_LOG_LEVEL = lv;
            } catch (e) { /* 保持默认 */ }
            finally { this.levelLoading = false; }
        },
        async load() {
            try {
                const r = await http.get('/api/logs/audit', { params: { page: 1, size: 10000 } });
                this.allRows = r.data.records || []; this.page = 1;
                this.loadError = '';
            } catch (e) { this.loadError = (e && e.message) || '无法连接到服务器'; }
        },
        onSfSort(p) { if (!p || !p.key) return; this.sfOnSort(p); this.page = 1; },
        onSfFilter(p) { if (!p || !p.key) return; this.sfOnFilter(p); this.page = 1; },
        async applyLevel() {
            await http.put('/api/system/log-level', { level: this.level });
            window.NC_LOG_LEVEL = this.level;
            this.$message.success('日志级别已调整为 ' + this.level + '（当前会话控制台将' + (this.level === 'DEBUG' ? '输出请求详情' : '停止输出请求详情') + '）');
        },
        async exportCsv() {
            // 携带认证令牌下载，避免新标签页打开时 401 "未提供认证凭证"
            try {
                const r = await http.get('/api/logs/audit/export?fmt=csv', { responseType: 'blob' });
                const url = URL.createObjectURL(r.data);
                const a = document.createElement('a');
                a.href = url; a.download = 'audit.csv';
                document.body.appendChild(a); a.click(); a.remove();
                URL.revokeObjectURL(url);
                this.$message.success('已导出 CSV');
            } catch (e) {
                this.$message.error('导出失败');
            }
        },
    },
    mounted() { this.loadLevel(); this.load(); }
}, '日志中心');
