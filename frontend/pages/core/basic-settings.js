// 路径: /system/basic-settings
// 基础设置（原 BasicSettingsPage）
// 主要功能：修改软件名称、版本显示名、TOTP 双因素开关、自动退出时间(分钟，0=关闭)。
// 关键接口：GET/PUT /api/system/basic-settings（保存实时写回 user_config.yaml）。
window.NC.registerPage('core_basic', {
    template: `
    <div class="nc-page">
      <div class="nc-section">
        <h2 class="nc-section-title">基础设置</h2>
        <div class="nc-form-card">
          <el-form :model="form" label-width="170px">
            <el-form-item label="软件名称">
              <el-input v-model="form.name" placeholder="留空则使用默认值 NetCore Framework"></el-input>
              <div class="nc-form-hint">自定义显示在登录页和标题栏的软件名称</div>
            </el-form-item>
            <el-form-item label="版本号">
              <el-input v-model="form.version" placeholder="留空则使用内置版本号"></el-input>
              <div class="nc-form-hint">覆盖系统概览中显示的版本号文字</div>
            </el-form-item>
            <el-form-item label="自动退出时间（分钟）">
              <el-input v-model.number="form.auto_logout_minutes" type="number" :min="0" style="max-width:200px;"></el-input>
              <div class="nc-form-hint">无操作超过该时长后自动退出登录；设为 <b>0</b> 表示关闭自动退出（默认 5 分钟）。点击、在输入框内键盘输入、切换页面会刷新计时；鼠标移动与页面滚动不计入。</div>
            </el-form-item>
            <el-form-item label="时区">
              <el-select v-model="form.timezone" style="width:260px;" filterable>
                <el-option v-for="t in timezones" :key="t" :label="t" :value="t"></el-option>
              </el-select>
              <div class="nc-form-hint">程序所有时间按此显示。默认 Asia/Shanghai（东八区）</div>
            </el-form-item>
            <el-form-item label="登录自动更新时区">
              <el-switch v-model="form.auto_update_timezone"></el-switch>
              <div class="nc-form-hint">勾选后，每次管理员登录自动把时区更新为<b>浏览器所在时区</b></div>
            </el-form-item>
            <el-form-item label="表单默认翻页数据">
              <div style="display:flex;gap:8px;align-items:center;">
                <el-input-number v-model="form.default_page_size" :min="1" :max="100" controls-position="right" style="width:120px;"></el-input-number>
                <el-button v-for="s in [5,10,20,50]" :key="s" size="small" @click="form.default_page_size=s">{{s}}</el-button>
              </div>
              <div class="nc-form-hint">表格组件每页默认显示条数，可在输入框内填入 1~100 的任意数字</div>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="nc-section">
        <h2 class="nc-section-title">TOTP 双因素认证</h2>
        <div class="nc-form-card">
          <el-form :model="form" label-width="170px">
            <el-form-item label="TOTP 设置">
              <el-switch v-model="form.totp_enabled"></el-switch>
              <div class="nc-form-hint">启用后，管理员登录时需要输入 TOTP 验证码（需先绑定 TOTP 密钥）</div>
            </el-form-item>
          </el-form>
          <p class="nc-form-hint" style="margin:4px 0 16px;">启用前请先用身份验证器（如 Google Authenticator / 微软验证器）扫描下方二维码绑定密钥，输入验证码完成绑定。绑定后管理员登录需输入动态验证码。</p>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px;">
            <el-button type="primary" @click="bindTotp" :loading="binding">生成密钥与二维码</el-button>
            <el-button v-if="totp.show" @click="copySecret">复制 Base32 密钥</el-button>
          </div>
          <div v-if="totp.show" style="display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start;">
            <div>
              <div style="font-weight:600;margin-bottom:8px;">二维码（请使用身份验证器扫描）</div>
              <img :src="'data:image/svg+xml;base64,' + totp.qrcode" style="width:200px;height:200px;background:#fff;padding:8px;border:1px solid var(--nc-border-light);border-radius:6px;" />
            </div>
            <div style="flex:1;min-width:260px;">
              <div style="font-weight:600;margin-bottom:8px;">Base32 密钥（手动输入用）</div>
              <el-input :value="totp.secret" readonly></el-input>
              <div style="margin-top:16px;font-weight:600;">otpauth 链接</div>
              <el-input type="textarea" :rows="3" :value="totp.otpauth_uri" readonly></el-input>
              <div style="margin-top:16px;font-weight:600;">输入验证码完成绑定</div>
              <div style="display:flex;gap:8px;margin-top:8px;">
                <el-input v-model="totp.code" placeholder="6 位动态码" style="width:160px;"></el-input>
                <el-button type="success" :loading="verifying" @click="verifyTotp">验证并启用</el-button>
              </div>
            </div>
          </div>
          <el-alert v-if="form.totp_enabled" type="success" :closable="false" style="margin-top:16px;" title="TOTP 已启用，登录时需要输入动态验证码"></el-alert>
        </div>
      </div>

      <div class="nc-section">
        <h2 class="nc-section-title">HTTPS 安全访问</h2>
        <div class="nc-form-card">
          <p class="nc-form-hint" style="margin:0 0 16px;">启用后程序以 HTTPS 提供服务（对应配置文件 core.yaml 的 <code>https.enabled</code>，默认开启）。未上传自定义证书时自动使用自签名证书，浏览器会提示“不安全”，属正常现象，可上传正式证书消除提示。</p>
          <el-form label-width="170px">
            <el-form-item label="启用 HTTPS">
              <el-switch v-model="httpsEnabled"></el-switch>
              <div class="nc-form-hint">开启/关闭需<b>重启服务</b>后生效</div>
            </el-form-item>
            <el-form-item label="自动转跳">
              <el-switch v-model="autoRedirect"></el-switch>
              <div class="nc-form-hint">开启后，误用另一协议访问会自动跳转到正确协议（如启用 HTTPS 后用 http 访问会自动转跳 https；需<b>重启服务</b>后生效）</div>
            </el-form-item>
            <el-form-item label="证书 SAN 地址">
              <el-input v-model="form.domain" placeholder="留空=本机所有网卡IP；可填IP或域名，多个用逗号分隔"></el-input>
              <div class="nc-form-hint">写入 HTTPS 证书 SAN 的访问地址。留空=自动包含所有本机网卡 IP（推荐）；若用固定 IP/域名访问（如 192.168.1.100 或 example.com），请在此填写，多个用逗号分隔。修改后点击页面底部「保存设置」并<b>重启服务</b>生效。</div>
            </el-form-item>
            <el-form-item label="自定义证书">
              <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <input type="file" ref="certInput" accept=".crt,.pem" style="display:none;" @change="onCertPick">
                <input type="file" ref="keyInput" accept=".key,.pem" style="display:none;" @change="onKeyPick">
                <el-button size="small" @click="$refs.certInput.click()">{{ certName || '选择证书文件 (.crt/.pem)' }}</el-button>
                <el-button size="small" @click="$refs.keyInput.click()">{{ keyName || '选择私钥文件 (.key)' }}</el-button>
                <el-button type="primary" size="small" :disabled="!certName || !keyName" :loading="uploading" @click="uploadCert">上传证书</el-button>
              </div>
              <div class="nc-form-hint" style="margin-top:4px;">证书仅支持 <b>.crt/.pem</b>，私钥仅支持 <b>.key/.pem</b>，其他文件无法选择/上传；上传后<b>重启服务生效</b></div>
              <el-alert v-if="httpsStatus" :closable="false" type="info" style="margin-top:8px;" :title="httpsStatus"></el-alert>
            </el-form-item>
          </el-form>
        </div>
      </div>

      <div class="nc-toolbar">
        <el-button type="primary" @click="save" :loading="saving">保存设置</el-button>
      </div>
    </div>`,
    data() {
        const tzs = ['Asia/Shanghai', 'Asia/Hong_Kong', 'Asia/Taipei', 'Asia/Tokyo', 'Asia/Seoul', 'Asia/Singapore',
                     'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'America/New_York', 'America/Chicago',
                     'America/Los_Angeles', 'Australia/Sydney', 'UTC', 'Etc/GMT-8', 'Etc/GMT+0'];
        return {
            form: { name: '', version: '', totp_enabled: false, auto_logout_minutes: 5,
                    timezone: 'Asia/Shanghai', auto_update_timezone: true, domain: '', default_page_size: 10 },
            timezones: tzs,
            saving: false, binding: false, verifying: false,
            totp: { show: false, secret: '', qrcode: '', otpauth_uri: '', code: '' },
            httpsEnabled: true, autoRedirect: true, certName: '', keyName: '', certFile: null, keyFile: null,
            uploading: false, httpsStatus: '',
        };
    },
    methods: {
        onCertPick(e) {
            const f = e.target && e.target.files && e.target.files[0];
            if (!f) return;
            const n = (f.name || '').toLowerCase();
            if (!(n.endsWith('.crt') || n.endsWith('.pem'))) {
                this.$message.error('证书仅支持 .crt/.pem 文件');
                e.target.value = ''; return;
            }
            this.certName = f.name; this.certFile = f;
        },
        onKeyPick(e) {
            const f = e.target && e.target.files && e.target.files[0];
            if (!f) return;
            const n = (f.name || '').toLowerCase();
            if (!(n.endsWith('.key') || n.endsWith('.pem'))) {
                this.$message.error('私钥仅支持 .key/.pem 文件');
                e.target.value = ''; return;
            }
            this.keyName = f.name; this.keyFile = f;
        },
        async uploadCert() {
            if (!this.certFile || !this.keyFile) { this.$message.warning('请先选择证书与私钥文件'); return; }
            this.uploading = true;
            try {
                const fd = new FormData();
                fd.append('cert_file', this.certFile);
                fd.append('key_file', this.keyFile);
                const r = await http.post('/api/system/https/cert', fd);
                if (r.data && r.data.success) {
                    this.$message.success((r.data.message) || '证书与私钥已上传，重启服务后生效');
                    this.httpsStatus = '自定义证书已上传，内容（PEM 文本）已写入配置文件，重启服务后生效。';
                } else {
                    this.$message.error((r.data && r.data.message) || '上传失败');
                }
            } catch (e) {
                this.$message.error('上传失败：' + ((e && e.message) || ''));
            } finally {
                this.uploading = false;
            }
        },
        async saveHttpsSwitch(v) {
            try {
                const r = await http.post('/api/system/https/switch', { enabled: !!v, auto_redirect: this.autoRedirect });
                this.$message.success((r.data && r.data.message) || '已更新');
            } catch (e) {
                this.$message.error('保存失败：' + ((e && e.message) || ''));
            }
        },
        async saveAutoRedirect(v) {
            try {
                const r = await http.post('/api/system/https/switch', { enabled: this.httpsEnabled, auto_redirect: !!v });
                this.$message.success((r.data && r.data.message) || '已更新');
            } catch (e) {
                this.$message.error('保存失败：' + ((e && e.message) || ''));
            }
        },
        async load() {
            try {
                const r = await http.get('/api/system/basic-settings');
                this.form = r.data;
                try {
                    const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
                    if (browserTz) this.form.timezone = browserTz;
                } catch (e) {}
                if (!this.form.timezone) this.form.timezone = 'Asia/Shanghai';
                if (this.form.timezone && this.timezones.indexOf(this.form.timezone) < 0) {
                    this.timezones.push(this.form.timezone);
                }
                if (r.data && r.data.https) {
                    this.httpsEnabled = !!r.data.https.enabled;
                    this.autoRedirect = !!r.data.https.auto_redirect;
                    this.httpsStatus = '当前生效方式：' + (window.location.protocol === 'https:' ? 'HTTPS' : 'HTTP') +
                        (r.data.https.custom_uploaded ? '（已上传自定义证书）' : '');
                }
            } catch (e) {}
        },
        async save() {
            this.saving = true;
            try {
                await http.put('/api/system/basic-settings', this.form);
                await http.post('/api/system/https/switch', { enabled: this.httpsEnabled, auto_redirect: this.autoRedirect });
                this.$message.success('基础设置已保存并生效（HTTPS 开关需重启服务后生效）');
                // 同步刷新菜单栏的软件名称 / 版本号
                if (this.$root && this.$root.fetchCoreConfig) this.$root.fetchCoreConfig();
                // 广播设置变更，让根组件重新读取自动退出阈值
                window.dispatchEvent(new Event('nc-settings-changed'));
            } catch (e) {
                this.$message.error('保存失败');
            } finally {
                this.saving = false;
            }
        },
        async bindTotp() {
            this.binding = true;
            try {
                const r = await http.post('/api/auth/totp/setup');
                this.totp.secret = r.data.secret;
                this.totp.qrcode = r.data.qrcode;
                this.totp.otpauth_uri = r.data.otpauth_uri;
                this.totp.code = '';
                this.totp.show = true;
            } catch (e) {
                this.$message.error('生成密钥失败');
            } finally {
                this.binding = false;
            }
        },
        async verifyTotp() {
            if (!this.totp.code) { this.$message.warning('请输入验证码'); return; }
            this.verifying = true;
            try {
                const r = await http.post('/api/auth/totp/verify', { code: this.totp.code, secret: this.totp.secret });
                if (r.data && r.data.success) {
                    this.form.totp_enabled = true;
                    this.save();
                    this.totp.show = false;
                    this.$message.success('TOTP 绑定成功并已启用');
                } else {
                    this.$message.error((r.data && r.data.message) || '验证失败');
                }
            } catch (e) {
                this.$message.error('验证失败');
            } finally {
                this.verifying = false;
            }
        },
        copySecret() {
            if (navigator.clipboard) navigator.clipboard.writeText(this.totp.secret);
            this.$message.success('密钥已复制：' + this.totp.secret);
        }
    },
    mounted() { this.load(); }
}, '基础设置');
