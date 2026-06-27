# 智能门禁IoT管理平台(IoT Management Platform for Intelligent Access Control)

一个基于 FastAPI + Vue 3 + STM32 的全栈智能化门禁管理系统，支持 Web 管理后台、微信小程序、uni-app 手机应用三端共用同一后端。系统具备 RBAC 权限管理、设备在线监控、MQTT 硬件通信（密码/指纹/刷卡/远程四种开门方式）、AI 智能开门、短信/邮箱验证码等功能。

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg?logo=fastapi)
![Vue](https://img.shields.io/badge/Vue-3.5-brightgreen.svg?logo=vue.js&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-blue.svg?logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-6-red.svg?logo=redis&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-orange.svg)
![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg?logo=docker&logoColor=white)
![STM32](https://img.shields.io/badge/STM32-F103-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 目录

- [功能特性](#功能特性)
- [系统架构](#系统架构)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [多端说明](#多端说明)
- [技术栈](#技术栈)
- [文档](#文档)
- [开发指南](#开发指南)
- [常见问题](#常见问题)
- [License](#license)

## 功能特性

### 用户与权限
- **用户管理**：注册、登录、密码修改、用户增删改查
- **RBAC 权限系统**：角色管理、权限分配、细粒度权限控制（如 `user.manage`、`device.manage`、`door.open`、`alert.view`）
- **多角色支持**：管理员（admin）、普通用户（user）及自定义角色
- **JWT 认证**：Redis 支撑的 Token 验证 + 黑名单注销机制

### 设备与门禁
- **设备管理**：设备增删改查、用户-设备绑定/解绑
- **设备在线监控**：MQTT 心跳检测 + 后台定时巡检，自动识别设备上下线
- **门禁控制**：远程开门、权限校验、实时状态反馈
- **MQTT 通信**：支持密码/指纹/刷卡/远程四种开门方式，QoS 1 保证消息可靠送达
- **开门记录**：分页查询、多维度筛选（时间、用户、设备、状态）
- **设备自动锁定**：密码/指纹/刷卡连续错误 5 次自动锁定设备 5 分钟，防止暴力破解

### 异常事件监控
- **设备锁定检测**：密码/指纹/刷卡连续验证错误 5 次，设备自动锁定 5 分钟
- **异常事件列表**：分页查询所有异常事件（设备锁定、开门失败），支持设备名称、事件类型、时间范围筛选
- **异常事件统计**：按时间范围统计异常总数、锁定次数、失败次数、各设备异常分布
- **设备锁定列表**：实时展示当前处于锁定状态的设备及剩余锁定时间（TTL 倒计时）
- **解除设备锁定**：管理员可手动解除设备锁定（清除 Redis 锁定键 + 发送 UNLOCK 命令）
- **权限控制**：`alert.view` 查看异常事件，`alert.unlock` 解除设备锁定
- **Redis 缓存**：异常事件列表 30 秒缓存，新增异常时自动清除缓存
- **实时推送**：设备锁定/解锁事件通过 WebSocket 实时通知管理员

### 通信与通知
- **WebSocket 实时通知**：管理员实时接收开门事件推送和设备状态变更
- **短信验证码**：阿里云短信服务集成，支持手机号登录验证
- **邮箱验证码**：SMTP 邮件服务集成，支持邮箱登录验证

### AI 与智能化
- **AI 智能助手**：自然语言控制门禁（DeepSeek 集成），支持语音指令开门和数据查询
- **AI 对话上下文**：Redis 缓存 15 分钟对话历史，支持多轮对话

### 多端支持
- **Web 管理后台**：Vue 3 + Element Plus，完整管理功能
- **微信小程序**：原生开发，开门 + 记录 + 个人中心
- **uni-app 手机应用**：跨平台（iOS/Android/H5），完整功能

## 系统架构

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Web 管理后台 │   │  微信小程序   │   │  手机 APP    │
│  Vue 3 + EP  │   │  原生开发     │   │  uni-app     │
└──────┬───────┘   └──────┬──────┘   └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │ HTTP / WebSocket
                   ┌──────┴──────┐
                   │   Nginx     │
                   │  (反向代理)  │
                   └──────┬──────┘
                          │
                   ┌──────┴──────┐
                   │   FastAPI   │  ← 后端核心（三端共用）
                   │  API + WS   │
                   └──┬───┬───┬──┘
                      │   │   │
            ┌─────────┘   │   └─────────┐
            ▼             ▼             ▼
       ┌────────┐   ┌─────────┐   ┌─────────┐
       │ MySQL  │   │  Redis  │   │Mosquitto│
       │ 数据库  │   │  缓存   │   │MQTT 代理│
       └────────┘   └─────────┘   └────┬────┘
                                       │ MQTT
                                ┌──────┴──────┐
                                │  STM32 门禁  │
                                │  ESP32-S3    │
                                │  (密码/指纹/  │
                                │   刷卡/远程)  │
                                └─────────────┘
```

### 异常事件 API 接口

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| `GET` | `/alerts?page=&size=&device_name=&alert_type=&start_time=&end_time=` | `alert.view` | 获取异常事件列表（分页、多维度筛选） |
| `GET` | `/alerts/stats?hours=24` | `alert.view` | 获取异常事件统计（锁定次数、失败次数、设备分布） |
| `POST` | `/alerts/unlock/{device_name}` | `alert.unlock` | 解除设备锁定（清除 Redis 锁定 + 发送 UNLOCK 命令） |

**异常事件类型**：
- `lock` — 设备锁定（密码/指纹/刷卡连续错误 5 次触发）
- `offline` — 设备离线（心跳超时）
- `error` — 开门失败（权限不足、验证错误等）

## 项目结构

```
all_door_access_system/
├── backend/                    # FastAPI 后端（三端共用）
│   ├── main.py                 # 应用入口（lifespan、CORS、中间件）
│   ├── serial_mqtt_bridge.py   # STM32 串口-MQTT 桥接脚本
│   ├── requirements.txt        # Python 依赖
│   ├── Dockerfile.backend      # Docker 构建文件
│   ├── .env.example            # 环境变量模板
│   ├── .env.docker             # Docker 环境变量模板
│   ├── api/                    # API 层（路由定义）
│   │   ├── routers.py          # 路由聚合器
│   │   ├── auth_api.py         # 认证接口（登录/注册/退出/改密）
│   │   ├── wx_auth_api.py      # 微信小程序认证
│   │   ├── admin_user_api.py   # 用户管理（管理员）
│   │   ├── device_api.py       # 设备管理
│   │   ├── door_api.py         # 门禁控制 + 开门日志
│   │   ├── alert_api.py        # 异常事件（设备锁定/开门失败）
│   │   ├── permission_api.py   # 权限管理（角色/权限 CRUD）
│   │   ├── stat_api.py         # 数据统计
│   │   ├── ai_agent.py         # AI 助手接口
│   │   └── websocket_api.py    # WebSocket 实时通知
│   ├── services/               # 服务层（业务逻辑）
│   │   ├── admin_user_service.py    # 用户业务
│   │   ├── device_service.py        # 设备业务（含 Redis 缓存）
│   │   ├── device_monitor_service.py # 设备在线状态监控
│   │   ├── door_service.py          # 门禁业务 + 日志查询
│   │   ├── mqtt_service.py          # MQTT 通信管理
│   │   ├── alert_service.py         # 异常事件业务（设备锁定/解锁/统计）
│   │   ├── websocket_service.py     # WebSocket 连接管理 + 认证
│   │   ├── permission_service.py    # RBAC 权限业务
│   │   ├── stat_service.py          # 统计业务
│   │   ├── ai_agent_service.py      # AI 助手业务（DeepSeek）
│   │   ├── verify_code_service.py   # 短信/邮箱验证码服务
│   │   └── wx_auth_service.py       # 微信登录业务
│   ├── database/               # 数据层
│   │   ├── db.py               # SQLAlchemy 引擎 + 初始化
│   │   ├── redis.py            # Redis 连接管理（单例 + 自动重连）
│   │   └── models/             # ORM 模型
│   │       ├── user.py         # 用户表
│   │       ├── device.py       # 设备表
│   │       ├── door_log.py     # 开门日志表
│   │       ├── user_device.py  # 用户-设备绑定表
│   │       ├── role.py         # 角色表
│   │       ├── permission.py   # 权限表
│   │       └── role_permission.py # 角色-权限关联表
│   ├── core/                   # 核心配置
│   │   ├── config.py           # 环境变量加载
│   │   ├── exceptions.py       # 自定义异常
│   │   ├── response_schema.py  # 统一响应格式定义
│   │   └── ai_system_prompt.py # AI 系统提示词
│   ├── utils/                  # 工具层
│   │   ├── auth.py             # JWT 认证 + 密码哈希 + 权限校验
│   │   ├── logger.py           # 日志管理（30天轮转）
│   │   ├── rate_limiter.py     # 请求频率限制
│   │   ├── api_exception_handler.py  # API 异常处理装饰器
│   │   └── service_exception_handler.py # 服务层异常装饰器
│   ├── schemas/                # Pydantic 校验
│   │   ├── user_schema.py
│   │   ├── device_schema.py
│   │   ├── door_schema.py
│   │   └── permission_schema.py
│   ├── tests/                  # 测试用例（9 个测试模块）
│   └── logs/                   # 运行日志（30天轮转）
│
├── web/                        # Vue 3 + Element Plus Web 管理后台
│   ├── src/
│   │   ├── views/              # 页面视图
│   │   │   ├── Login.vue       # 登录/注册
│   │   │   ├── Layout.vue      # 主布局（侧边栏 + 头部）
│   │   │   ├── NotFound.vue    # 404 页面
│   │   │   ├── admin/          # 管理员页面
│   │   │   │   ├── Device.vue  # 设备管理
│   │   │   │   ├── Users.vue   # 用户管理
│   │   │   │   ├── Log.vue     # 开门日志
│   │   │   │   ├── Alert.vue   # 异常事件（设备锁定/开门失败）
│   │   │   │   └── RoleManage.vue # 角色权限管理
│   │   │   └── shared/         # 共享页面
│   │   │       ├── Dashboard.vue    # 数据看板
│   │   │       ├── Door.vue         # 门禁控制
│   │   │       ├── Profile.vue      # 个人中心
│   │   │       └── Statistics.vue   # 统计详情
│   │   ├── components/         # 组件（Dashboard/Device/Door/Layout/User/Log）
│   │   ├── composables/        # 组合式函数（useDeviceStatus/useDoorEventStream/useListFetch）
│   │   ├── services/           # WebSocket 服务
│   │   ├── utils/              # 工具（request/permission/formatTime/format）
│   │   ├── router/             # 路由配置
│   │   └── styles/             # 全局样式
│   └── nginx.conf              # Nginx 配置（反向代理 + SSL）
│
├── app/                        # uni-app 跨平台手机应用（iOS/Android/H5）
│   ├── pages/                  # 页面
│   │   ├── login/login.vue     # 登录
│   │   ├── index/index.vue     # 首页
│   │   ├── doors/doors.vue     # 开门
│   │   ├── device/device.vue   # 设备管理
│   │   ├── logs/logs.vue       # 开门记录
│   │   ├── users/users.vue     # 用户管理
│   │   └── profile/profile.vue # 个人中心
│   ├── api/                    # API 封装（request/auth/device/door/stat/user）
│   ├── stores/                 # Pinia 状态管理
│   ├── utils/                  # 工具（config.js）
│   └── static/                 # 静态资源（logo、tabbar 图标）
│
├── miniprogram/                # 微信小程序（原生开发）
│   └── miniprogram/
│       ├── pages/              # 页面
│       │   ├── login/          # 登录（微信一键 + 账号密码）
│       │   ├── doors/          # 设备列表 + 开门
│       │   ├── logs/           # 开门记录
│       │   └── profile/        # 个人中心
│       ├── utils/              # 工具（api/auth/config）
│       └── images/             # 图片资源
│
├── stm32/                      # STM32 固件 + ESP32-S3 WiFi 模块
│   ├── User/                   # 用户应用代码（main.c、menu、password）
│   ├── AS608/                  # 指纹传感器驱动
│   ├── AT24CXX/                # EEPROM 存储驱动
│   ├── RC522/                  # RFID 读卡器驱动
│   ├── LCD12864/               # LCD 显示屏驱动
│   ├── Martix_KEY/             # 矩阵键盘驱动
│   ├── General_Module/         # 继电器控制
│   ├── W5500/                  # 以太网/MQTT 驱动
│   ├── IIC/                    # I2C 总线驱动
│   ├── System/                 # 系统库（delay/sys/timer/usart）
│   ├── Libraries/              # STM32 标准外设库 + CMSIS
│   └── ESP8266/                # ESP32-S3 固件（PlatformIO，MQTT 客户端）
│
├── deploy/                     # Docker 部署配置
│   ├── docker-compose.yml      # 5 服务编排（MySQL/Redis/Mosquitto/FastAPI/Nginx）
│   ├── .env.example            # 环境变量模板
│   ├── .env.docker             # Docker 环境变量模板
│   ├── mosquitto.conf          # Mosquitto MQTT 配置
│   ├── deploy.sh               # Linux 部署脚本
│   └── deploy.bat              # Windows 部署脚本
│
├── SSL/                        # SSL 证书（doorlink.top）
├── CLAUDE.md                   # Claude Code 项目指引
├── LICENSE                     # MIT License
└── README.md
```

## 快速开始

### 环境要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 18+ | 前端构建 |
| MySQL | 8.0 | 数据库 |
| Redis | 6+ | 缓存 + Token 管理 |
| Mosquitto | 2.0 | MQTT Broker（硬件通信） |
| Docker | 24+ | 容器化部署（可选） |

### Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone <repository-url>
cd all_door_access_system

# 2. 进入部署目录
cd deploy

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，至少配置以下必填项：
#   SECRET_KEY=your-strong-secret-key
#   MYSQL_PASSWORD=your-mysql-password
#   MYSQL_DB=door_access_system

# 4. 启动所有服务（首次会自动构建镜像）
docker compose up -d

# 5. 等待服务就绪（约 30 秒），检查状态
docker compose ps

# 6. 访问系统
#    Web 管理后台：http://localhost
#    API 文档：    http://localhost:8000/docs
#    默认管理员：  admin / 123456
```

### 一键部署脚本

```bash
# Linux / macOS
cd deploy && bash deploy.sh

# Windows
cd deploy && deploy.bat
```

脚本自动完成：检查 Docker 环境 → 创建 `.env` → 创建必要目录 → 停止旧容器 → 构建并启动全部服务。

### 本地开发

```bash
# ============ 后端 ============
cd backend

# 创建虚拟环境（推荐）
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（从模板复制并修改）
cp .env.example .env
# 编辑 .env，本地开发使用：
#   MYSQL_HOST=localhost
#   REDIS_HOST=127.0.0.1
#   MQTT_BROKER_HOST=127.0.0.1

# 启动开发服务器（热重载）
python main.py
# 访问 API 文档：http://localhost:8000/docs

# ============ Web 前端 ============
cd web
npm install
npm run dev
# 访问：http://localhost:5173

# ============ 手机 APP（H5 模式） ============
cd app
npm install
npm run dev:h5
# 访问：http://localhost:5174

# ============ 微信小程序 ============
# 使用微信开发者工具打开 miniprogram/ 目录
# 配置 miniprogram/utils/config.js 中的 API 地址
```

### 运行测试

```bash
cd backend

# 运行全部测试
pytest tests/ -v

# 运行指定模块
pytest tests/test_auth.py -v

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

## 多端说明

| 端 | 目录 | 技术栈 | 功能范围 | 认证方式 |
|----|------|--------|----------|----------|
| Web 管理后台 | `web/` | Vue 3 + Element Plus + Vite | 完整管理功能（用户/设备/日志/权限/统计/AI） | JWT Token (localStorage) |
| 手机 APP | `app/` | uni-app + Vue 3 Composition API | 完整功能（iOS/Android/H5 跨平台） | JWT Token (X-Token header) |
| 微信小程序 | `miniprogram/` | 原生微信开发 | 开门 + 记录 + 个人中心 | wx.login() → JWT |

### Web 管理后台页面

| 页面 | 路径 | 权限 | 说明 |
|------|------|------|------|
| 登录/注册 | `/login` | 公开 | 支持账号密码登录 |
| 数据看板 | `/dashboard` | 已登录 | 统计数据 + AI 助手入口 |
| 门禁控制 | `/door` | 已登录 | 远程开门 + 个人记录 |
| 统计详情 | `/statistics` | 已登录 | 详细统计图表 |
| 个人中心 | `/profile` | 已登录 | 个人信息 + 密码修改 |
| 用户管理 | `/users` | `user.manage` | 用户增删改查 + 设备绑定 |
| 设备管理 | `/device` | `device.manage` | 设备增删改查 |
| 开门日志 | `/log` | `door.log` | 全局日志 + 高级筛选 |
| 异常事件 | `/alert` | `alert.view` | 设备锁定列表 + 异常统计 + 解除锁定 |
| 角色管理 | `/roles` | `user.manage` | 角色 CRUD + 权限分配 |

## 技术栈

### 后端
- **框架**：FastAPI + Uvicorn（ASGI）
- **ORM**：SQLAlchemy（MySQL 8.0）
- **缓存**：Redis 6（Token 管理 + 数据缓存 + 设备状态）
- **认证**：JWT（python-jose） + bcrypt 密码哈希
- **MQTT**：paho-mqtt（Mosquitto Broker）
- **AI**：DeepSeek API 集成
- **验证**：阿里云短信 + SMTP 邮件
- **序列化**：Pydantic v2

### 前端
- **Web**：Vue 3 + Element Plus + Vite + Vue Router + Axios
- **手机 APP**：uni-app + Vue 3 Composition API + Pinia
- **小程序**：原生微信开发（WXML/WXSS/JS）

### 嵌入式
- **主控**：STM32F103C8T6（ARM Cortex-M3, 72MHz）
- **WiFi**：ESP32-S3（MQTT 客户端）
- **传感器**：AS608 指纹 / MFRC522 RFID / 4x4 矩阵键盘
- **存储**：AT24C02 EEPROM
- **显示**：LCD12864（ST7920）

### 基础设施
- **容器化**：Docker + Docker Compose（5 服务编排）
- **反向代理**：Nginx（SSL + API 代理 + 静态资源）
- **数据库**：MySQL 8.0（utf8mb4）
- **消息队列**：Eclipse Mosquitto 2.0

## 文档

| 文档 | 说明 |
|------|------|
| [后端详细说明](docs/backend.md) | 三层架构、数据库模型、Redis 缓存、MQTT 通信、异常处理 |
| [API 文档](docs/api.md) | 完整接口列表、请求参数、权限说明、WebSocket 协议 |
| [硬件说明](docs/hardware.md) | STM32 模块、引脚连接、通信协议、串口桥接 |
| [部署与配置](docs/deployment.md) | 环境变量详解、Docker 部署、常见问题排查 |

> 💡 运行后端后，还可访问交互式 API 文档：`http://localhost:8000/docs`（Swagger UI）或 `http://localhost:8000/redoc`（ReDoc）

## 开发指南

### 后端开发规范

**三层架构**：API 层（路由）→ 服务层（业务逻辑）→ 数据层（ORM）

```python
# API 层 - 保持轻薄，只做请求接收和响应返回
@router.post("/devices")
@handle_api_exception
def create_device(body: DeviceCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(require_admin)):
    device = create_device_service(db, body)
    return success({"id": device.id}, msg="创建成功")

# 服务层 - 所有业务逻辑在此实现
@service_exception_handler
def create_device_service(db: Session, body: DeviceCreate):
    # 业务逻辑、数据校验、缓存失效...
    pass
```

**关键约定**：
- 所有 API 响应使用 `success()` / `error()` 返回统一 `{"code", "msg", "data"}` 格式
- API 路由使用 `@handle_api_exception` 装饰器自动捕获异常
- 服务层使用 `@service_exception_handler` 装饰器自动回滚事务
- DB 会话通过 `Depends(get_db)` 注入
- 权限控制通过 `Depends(require_admin)` 或 `Depends(require_permission("code"))` 实现
- 缓存失效：设备 CRUD 操作后清除 `cache:device:list:user:*`

### 添加新功能流程

1. 在 `schemas/` 定义 Pydantic 请求/响应模型
2. 在 `services/` 实现业务逻辑
3. 在 `api/` 创建路由端点（使用 `@handle_api_exception`）
4. 在 `api/routers.py` 注册路由
5. 更新前端页面（Web/小程序/APP）
6. 编写测试用例

### 数据库迁移（Alembic）

项目使用 Alembic 管理数据库表结构变更，支持版本化迁移和安全回滚。

**常用命令：**

```bash
cd backend

# 查看当前数据库版本
python manage_db.py current

# 查看迁移历史
python manage_db.py history

# 创建新迁移脚本（修改模型后执行）
python manage_db.py create -m "add_user_phone_field"

# 升级到最新版本
python manage_db.py upgrade

# 回滚一个版本
python manage_db.py downgrade -1
```

**典型工作流程：**

```bash
# 1. 修改 SQLAlchemy 模型（如 database/models/user.py 添加 phone 字段）

# 2. 生成迁移脚本
python manage_db.py create -m "add_user_phone_field"

# 3. 检查生成的脚本（在 alembic/versions/ 目录下）

# 4. 执行迁移
python manage_db.py upgrade

# 5. 如果需要回滚
python manage_db.py downgrade -1
```

**直接使用 Alembic 命令：**

```bash
# 也可以直接使用 alembic 命令
alembic current                    # 查看当前版本
alembic history                    # 查看迁移历史
alembic revision --autogenerate -m "描述"  # 创建迁移
alembic upgrade head               # 升级到最新
alembic downgrade -1               # 回滚一个版本
```

### 环境变量速查

| 分类 | 必填变量 | 可选变量 |
|------|----------|----------|
| 核心 | `SECRET_KEY`, `MYSQL_HOST`, `MYSQL_PASSWORD`, `MYSQL_DB` | `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |
| Redis | - | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` |
| MQTT | - | `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` |
| AI | - | `DEEPSEEK_API_KEY`, `AI_API_URL`, `AI_MODEL` |
| 微信 | - | `WX_APPID`, `WX_SECRET` |
| 短信 | - | `ALIYUN_ACCESS_KEY_ID`, `ALIYUN_ACCESS_KEY_SECRET`, `ALIYUN_SMS_SIGN`, `ALIYUN_SMS_TEMPLATE` |
| 邮件 | - | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` |
| 管理员 | - | `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `AUTO_CREATE_ADMIN` |
| 日志 | - | `LOG_FORMAT` |

> 完整模板见 [`deploy/.env.example`](deploy/.env.example)

### 结构化日志

项目支持结构化 JSON 日志，便于生产环境日志收集和分析。

**配置方式：**

在 `.env` 中设置 `LOG_FORMAT`：
```bash
# 开发环境（默认）- 纯文本格式
LOG_FORMAT=text

# 生产环境推荐 - JSON 格式
LOG_FORMAT=json
```

**日志格式对比：**

```bash
# 纯文本格式（开发环境）
2026-06-11 18:30:15 | INFO     | door_service.py:42 | 用户 admin 开门成功

# JSON 格式（生产环境）
{
  "timestamp": "2026-06-11 18:30:15,123",
  "level": "INFO",
  "message": "用户 admin 开门成功",
  "user_id": 1,
  "device_id": "001",
  "logger": "app",
  "module": "door_service",
  "function": "open_door",
  "line": 42,
  "pid": 1234
}
```

**在代码中添加上下文信息：**

```python
from utils.logger import AppLogger
logger = AppLogger.get_logger()

# 基础日志
logger.info("用户登录成功")

# 带上下文的日志（会自动添加到 JSON 字段）
logger.info("开门成功", extra={
    "user_id": 1,
    "device_id": "001",
    "action": "door_open",
    "status": "success"
})
```

**生产环境日志收集：**

JSON 格式日志可以轻松集成到：
- **ELK Stack**（Elasticsearch + Logstash + Kibana）
- **Loki + Grafana**
- **阿里云 SLS**（日志服务）
- **AWS CloudWatch**

只需配置日志收集器按行读取 `logs/app.log` 文件即可。

## 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Redis 连接失败 | Redis 未启动 | 启动 Redis：`redis-server`；Docker 环境检查 `docker compose ps redis` |
| 数据库连接失败 | `.env` 配置错误 | Docker 环境用 `MYSQL_HOST=mysql`，本地用 `MYSQL_HOST=localhost` |
| 前端页面空白 | 前端未构建 | 执行 `cd web && npm run build`，然后 `docker compose up -d --build frontend` |
| AI 功能不可用 | 未配置 API Key | 在 `.env` 中配置 `DEEPSEEK_API_KEY` |
| MQTT 连接失败 | Broker 未启动 | Docker：`docker compose ps mosquitto`；本地：`mosquitto -v` |
| 设备离线 | 心跳超时 | 设备在线状态 Redis 缓存 70 秒过期，等待自动恢复或检查设备固件 |
| 用户/设备删除失败 | 存在关联数据 | 先解绑所有关联：删除用户前解绑设备，删除设备前解绑用户 |
| Token 过期 | 默认 3600 分钟 | 调整 `ACCESS_TOKEN_EXPIRE_MINUTES` 或重新登录 |
| 密码过长报错 | bcrypt 72 字节限制 | 密码不超过 72 字节（约 24 个中文字符或 72 个英文字符） |
| WebSocket 断连 | 网络不稳定 | 前端自动重连机制，检查浏览器控制台日志 |
| 设备锁定无法开门 | 密码/指纹/刷卡连续错误 5 次 | 等待 5 分钟自动解锁，或管理员在异常事件页面手动解除锁定 |
| 异常事件页面无数据 | 未发生异常或权限不足 | 确认拥有 `alert.view` 权限，检查是否有开门失败记录 |

## License

[MIT](LICENSE)
