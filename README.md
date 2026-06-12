# 🥘 点菜吧 · 家庭菜单管理

> 一家人吃什么，不用再问了。

打开手机就能点菜。想吃的点一下，系统自动汇成采购清单。多人实时同步，各点各的互不干扰。

---

## 架构

```
┌─────────────────────────────────────────────────────┐
│                   用户浏览器                          │
│  dcnc.xizer.cloud  ┆  dc.xizer.cloud                 │
│  (营销落地页)        ┆  (登录/注册/点菜/管理)          │
└────────┬────────────┆────────┬───────────────────────┘
         │            ┆        │
         ▼            ┆        ▼
┌────────────────┐   ┆   ┌──────────────────────┐
│ Landing Server  │   ┆   │   Flask App + API    │
│ (纯静态WSGI)    │   ┆   │   Gunicorn + gevent  │
│ :5001           │   ┆   │   :5000              │
└────────────────┘   ┆   └──────┬───────────────┘
         │            ┆        │
         └───── Cloudflare Tunnel ─────┘
                    │
                    ▼
               Cloudflare Edge
           (HTTPS / CDN / DDoS)
```

### 组件

| 组件 | 技术栈 |
|------|--------|
| **Web 框架** | Flask 3.x + SQLAlchemy |
| **实时推送** | Flask-SocketIO + gevent |
| **认证** | Flask-Login + Werkzeug 密码哈希 |
| **数据库** | SQLite（可替换 PostgreSQL）|
| **前端** | 原生 HTML/CSS/JS（无框架）|
| **部署** | Gunicorn + Cloudflare Tunnel |
| **营销页** | 独立 WSGI 服务器（:5001）|

---

## 功能

### 核心功能

- **每日点菜** — 家庭成员各自打开网页，点选想吃的菜
- **自动采购清单** — 点完菜自动汇总食材和用量，标注来源菜名
- **多人实时同步** — 基于 WebSocket，一个人点了其他人自动看到
- **自家菜单管理** — 每个家庭独立维护自己的菜单
- **分类管理** — 自定义菜品分类（荤菜、素菜、汤、主食、凉菜…）
- **做饭笔记** — 每天记一句经验，下次不会忘
- **统计排行** — 自动统计哪些菜最受欢迎
- **周历总览** — 一周菜单一眼看完
- **随机推荐** — 不知道吃什么时系统帮你挑

### 多家庭隔离

每个注册用户创建一个独立家庭空间：

```
用户A 注册 → 家庭A（独立菜单、订单、笔记）
用户B 注册 → 家庭B（独立菜单、订单、笔记）
```

数据完全隔离，WebSocket 推送也按家庭路由。

### 账户安全

- 邮箱 + 密码注册登录
- 密码用 `scrypt` 哈希存储
- 支持修改密码
- 支持忘记密码（页面直接生成新密码）

---

## 快速部署

### 1. 克隆

```bash
git clone https://github.com/AnShengFather/family-menu.git
cd family-menu
```

### 2. 安装依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动

```bash
# 主应用（点菜系统）
venv/bin/gunicorn -k gevent -w 1 -b 127.0.0.1:5000 app:app

# 营销页（可选）
venv/bin/python3 landing_server.py 5001
```

### 4. 使用 systemd（推荐）

```ini
# /etc/systemd/system/family-menu.service
[Unit]
Description=Family Menu
After=network.target

[Service]
User=www-data
WorkingDirectory=/opt/family-menu
ExecStart=/opt/family-menu/venv/bin/gunicorn -k gevent -w 1 -b 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now family-menu
```

### 5. 域名暴露（Cloudflare Tunnel）

```bash
cloudflared tunnel create family-menu
# 在 Cloudflare Dashboard 加 DNS CNAME 记录
# 配置 /etc/cloudflared/config.yml
```

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 首页（已登录跳转点菜，未登录跳转登录）|
| GET/POST | `/login` | 登录 |
| GET/POST | `/register` | 注册 |
| GET | `/logout` | 退出 |
| GET/POST | `/forgot` | 忘记密码 |
| GET | `/admin` | 管理后台 |
| GET | `/api/dishes` | 获取在售菜品 |
| GET | `/api/dishes/all` | 获取全部菜品 |
| POST | `/api/dishes` | 添加菜品 |
| PUT | `/api/dishes/:id` | 修改菜品 |
| DELETE | `/api/dishes/:id` | 删除菜品 |
| GET | `/api/categories` | 获取分类 |
| POST | `/api/categories` | 添加分类 |
| PUT | `/api/categories/:id` | 修改分类 |
| DELETE | `/api/categories/:id` | 删除分类 |
| GET | `/api/orders` | 获取订单 |
| POST | `/api/orders/toggle` | 切换选菜 |
| POST | `/api/orders/batch` | 批量提交 |
| GET | `/api/shopping` | 采购清单 |
| GET | `/api/stats` | 统计数据 |
| GET/POST | `/api/notes` | 做饭笔记 |
| POST | `/api/settings/password` | 修改密码 |

---

## 项目结构

```
family-menu/
├── app.py                  # 主应用（Flask API + WebSocket）
├── landing_server.py       # 独立营销页服务
├── reset_password.py       # 密码重置工具（CLI）
├── requirements.txt        # Python 依赖
├── static/                 # 静态资源
│   ├── favicon.svg
│   ├── icon-192.svg
│   ├── manifest.json
│   ├── sw.js               # Service Worker (PWA)
│   └── socket.io.min.js
└── templates/              # HTML 模板
    ├── index.html           # 点菜首页
    ├── admin.html           # 管理后台
    ├── login.html           # 登录
    ├── register.html        # 注册
    ├── forgot.html          # 忘记密码
    └── landing.html         # 营销落地页
```

---

## 技术说明

- **为什么用 SQLite？** — 家庭场景并发低，SQLite 足够。用户量大了换成 PostgreSQL 只需改一行连接字符串
- **为什么不用前端框架？** — 保持零构建、零依赖。一个页面就是一个 HTML 文件，改了直接刷新看效果
- **为什么营销页独立部署？** — 跟主应用解耦，不影响点菜系统的稳定性

---

MIT License
