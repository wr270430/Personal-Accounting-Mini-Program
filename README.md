# 💰 个人记账系统

纯前端 + Python 标准库实现的个人记账应用，支持多设备云同步。

## 功能

- 📝 **收支记录** — 支持多种分类（餐饮、交通、购物、工资等）和支付方式
- 🧠 **智能记忆** — 自动学习记账习惯，输入金额时推荐常用分类
- 📊 **统计分析** — 自动生成周报/月报，饼图、柱状图、趋势图
- 🧾 **发票管理** — 发票类型/号码记录，票据照片附件，待报销统计
- 📦 **7天备份** — 删除记录保留 7 天可恢复，过期自动清理
- 💳 **支付方式管理** — 自定义支付方式（微信/支付宝/银行卡/现金等）
- 📂 **自定义分类** — 支持自定义收入和支出分类
- ☁️ **多设备同步** — 自建 Python 同步服务，手机电脑数据互通
- 🌓 **深色/浅色主题** — 自动跟随系统主题切换
- 📱 **PWA 友好** — 移动端适配，可添加到主屏幕

## 快速开始

### 本地使用（单机）

直接浏览器打开 `index.html`，数据保存在浏览器 localStorage 中。

### 启用多设备同步

1. 启动同步服务端：

```bash
python sync_server.py
# 默认端口 8520，可设置环境变量
# SYNC_PORT=8520  SYNC_TOKEN=你的密码
```

2. 打开 `index.html` → 点击 ⚙️ 设置 → 配置云服务地址为 `http://服务器IP:8520`

3. 在其他设备上打开同一地址即可自动同步

### 云部署

**阿里云 ECS / 任意 VPS：**

```bash
# 上传 sync_server.py 和 index.html 到服务器
scp sync_server.py index.html root@你的服务器:/root/

# SSH 登录后创建 systemd 服务
cat > /etc/systemd/system/accounting-sync.service << 'EOF'
[Unit]
Description=Accounting Sync Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /root/sync_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now accounting-sync

# 开放端口（以 iptables 为例）
iptables -I INPUT -p tcp --dport 8520 -j ACCEPT
```

**Render.com 免费部署：**

GitHub 仓库已包含 `render.yaml`，在 [render.com](https://render.com) 连接仓库即可一键部署。

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 应用 |
| GET | `/api/status` | 服务状态 |
| GET | `/api/data` | 获取数据（带 X-Device-Id 头获取指定设备） |
| POST | `/api/sync` | 同步数据 |
| GET | `/api/devices` | 设备列表 |
| GET | `/api/all` | 全部数据（含合并结果） |
| POST | `/api/device/delete` | 删除设备 |

## 文件结构

```
.
├── index.html          # 前端应用（纯 HTML/CSS/JS，约 4200+ 行）
├── sync_server.py      # 同步服务端（Python 标准库，无依赖）
├── render.yaml         # Render.com 部署配置
└── .gitignore
```

## 技术栈

- **前端**：原生 HTML/CSS/JS，Canvas 图表，localStorage 持久化
- **后端**：Python `http.server` + `json`（标准库），JSON 文件存储
- **部署**：systemd 守护进程，Render.com 一键部署
