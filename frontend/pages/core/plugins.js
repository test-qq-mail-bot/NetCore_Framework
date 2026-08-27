// 路径: /system/plugins
// 插件管理（原 PluginsPage）
// 主要功能：列出已加载插件、启用/禁用插件、热重启单个或全部插件。
// 关键接口：GET /api/plugins/、POST /api/plugins/{name}/toggle、POST /api/system/plugins/reload(-all)。
window.NC.registerPage('core_plugins', {
    mixins: [window.NC.SF_MIXIN],
template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">插件列表</h2>
        <div class="nc-table-card">
          <el-alert v-if="loadError" type="error" :closable="false" :title="'数据加载失败：' + loadError" style="margin-bottom:12px;"></el-alert>
          <div class="nc-toolbar">
            <el-button type="primary" @click="reloadAll">热重启全部</el-button>
            <el-button @click="reloadFailed">重启失败插件</el-button>
          </div>
          <nc-table :data="plugins" :columns="cols" client-paged :page-size="pageSize" :page-sizes="[5,10,20,50]"
                    @page-change="(p)=>{page=p;}" @size-change="(s)=>{pageSize=s;page=1;}">
            <template #col-status="{row}"><el-tag :type="row.status==='success'?'success':(row.status==='failed'?'danger':'info')">{{row.status}}</el-tag></template>
            <template #col-enabled="{row}"><el-switch v-model="row.enabled" @change="(val) => toggle(row.name, val)"></el-switch></template>
            <template #col-ops="{row}"><el-button size="small" type="warning" @click="reload(row.name)">热重启</el-button></template>
          </nc-table>
        </div>
      </div>
    </div>`,
    data() { return { plugins: [], loadError: '', saving: '', page: 1, pageSize: (window.NC && window.NC.defaultPageSize) || 10 }; },
    computed: {
        cols() {
            return [
                { label: '名称', prop: 'name', sortable: true, filterable: true },
                { label: '路径', prop: 'path', width: 200, sortable: true, filterable: true },
                { label: '状态', prop: 'status', width: 120, sortable: true, filterable: true, slotName: 'col-status' },
                { label: '版本', prop: 'metadata.version', width: 110, sortable: true, filterable: true },
                { label: '描述', prop: 'metadata.description', sortable: true, filterable: true },
                { label: '错误信息', prop: 'error', sortable: true, filterable: true },
                { label: '启用', width: 90, slotName: 'col-enabled' },
                { label: '操作', width: 120, slotName: 'col-ops' },
            ];
        },
    },
    methods: {
        async load() {
            try { const r = await http.get('/api/plugins/'); this.plugins = r.data.plugins; this.loadError = ''; }
            catch (e) { this.loadError = (e && e.message) || '无法连接到服务器'; }
        },
        async reload(name) { const r = await http.post('/api/system/plugins/reload', { name }); this.$message.info(r.data.message); this.load(); },
        async reloadAll() { await http.post('/api/system/plugins/reload-all'); this.$message.success('已触发'); this.load(); },
        async reloadFailed() { await http.post('/api/system/plugins/reload-failed'); this.$message.success('已触发'); this.load(); },
        async toggle(name, val) {
            this.saving = name;
            try {
                const r = await http.post('/api/plugins/' + encodeURIComponent(name) + '/toggle', { enabled: !!val });
                this.$message.success(r.data.success ? (val ? '已启用：' + name : '已禁用：' + name) : '操作失败');
                await this.load();
                try { await this.$root.fetchMenus(); } catch (e) {}
            } catch (e) {
                this.$message.error('切换失败');
                await this.load();
            } finally {
                this.saving = '';
            }
        }
    },
    mounted() { this.load(); }
}, '插件列表');
