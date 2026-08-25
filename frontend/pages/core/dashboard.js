// 路径: /dashboard
// 系统概览（原 DashboardPage）
// 主要功能：展示系统名称、版本、运行时长、Python 版本、插件数量、服务器时间等。
// 关键接口：GET /api/system/info。
window.NC.registerPage('core_dashboard', {
    template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">系统概览</h2>
        <el-alert v-if="loadError" type="error" :closable="false" :title="'数据加载失败：' + loadError" style="margin-bottom:12px;"></el-alert>
        <div class="nc-stat-grid" v-if="info">
          <div class="nc-stat-card accent-primary"><div class="nc-stat-label">系统名称</div><div class="nc-stat-value">{{info.name}}</div></div>
          <div class="nc-stat-card accent-primary"><div class="nc-stat-label">版本</div><div class="nc-stat-value">{{info.version}}</div></div>
          <div class="nc-stat-card accent-success"><div class="nc-stat-label">运行时长</div><div class="nc-stat-value" style="font-size:20px;">{{fmtUptime(info.uptime_seconds)}}</div></div>
          <div class="nc-stat-card accent-warning"><div class="nc-stat-label">已加载插件</div><div class="nc-stat-value">{{info.plugin_count}}</div></div>
        </div>
      </div>
      <div class="nc-section">
        <h3 class="nc-section-title">运行环境</h3>
        <div class="nc-table-card">
          <el-descriptions :column="2" border v-if="info">
            <el-descriptions-item label="服务器时间">{{fmtTime(info.server_time)}}</el-descriptions-item>
            <el-descriptions-item label="主机名">{{info.hostname || '-'}}</el-descriptions-item>
            <el-descriptions-item label="操作系统">{{info.platform}}</el-descriptions-item>
            <el-descriptions-item label="架构">{{info.machine || '-'}}</el-descriptions-item>
            <el-descriptions-item label="CPU 核数">{{info.cpu_count || '-'}}</el-descriptions-item>
            <el-descriptions-item label="Python">{{info.python_version}}</el-descriptions-item>
            <el-descriptions-item label="进程 PID">{{info.pid || '-'}}</el-descriptions-item>
            <el-descriptions-item label="启动时间">{{fmtTime(info.started_at)}}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </div>`,
    data() { return { info: null, loadError: '' }; },
    methods: {
        fmtUptime(seconds) {
            if (seconds == null || isNaN(seconds)) return '-';
            let s = Math.max(0, Math.floor(seconds));
            const d = Math.floor(s / 86400); s -= d * 86400;
            const h = Math.floor(s / 3600); s -= h * 3600;
            const m = Math.floor(s / 60); s -= m * 60;
            const parts = [];
            if (d > 0) parts.push(d + ' 天');
            if (h > 0) parts.push(h + ' 小时');
            if (m > 0) parts.push(m + ' 分');
            parts.push(s + ' 秒');
            return parts.join('');
        },
        fmtTime(v) {
            if (!v) return '-';
            if (window.NC && window.NC.fmtTime) return window.NC.fmtTime(v);
            return v;
        },
        async load() {
            try { const r = await http.get('/api/system/info'); this.info = r.data; this.loadError = ''; }
            catch (e) { this.loadError = (e && e.message) || '无法连接到服务器'; }
        }
    },
    mounted() { this.load(); }
}, '系统概览');
