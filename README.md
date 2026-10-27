<div align="center">
  <h1>Raspberry Dome · 树莓派农作物监测系统</h1>
  <p>基于树莓派的农业环境监测与数据采集系统，支持温湿度、土壤湿度监测与远程控制。</p>
  <p>
    <img src="https://img.shields.io/badge/Raspberry%20Pi-Zero%20W-E31B23?logo=raspberrypi&logoColor=white" alt="Raspberry Pi Zero W">
    <img src="https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white" alt="Python 3.9+">
    <img src="https://img.shields.io/badge/MQTT-EMQX-660066" alt="MQTT EMQX">
    <img src="https://img.shields.io/badge/Flask-2.x-000000?logo=flask&logoColor=white" alt="Flask 2.x">
  </p>
</div>

## 项目介绍

**Raspberry Dome** 是一套完整的农业环境监测系统，由树莓派端和服务器端两部分组成：

- **树莓派端**：部署在田间，负责采集环境数据（空气温湿度、土壤湿度）、拍摄作物照片，并通过 MQTT 上报数据。
- **服务器端**：部署在云服务器上，负责存储数据、提供 API 接口、接收远程命令并转发给树莓派。

支持定时自动采集与远程手动采集两种模式，数据可通过 Web 界面查看。

## 系统架构

```
┌─────────────────┐         MQTT          ┌─────────────────┐
│   树莓派端        │ ◄──────────────────► │   服务器端        │
│  (采集+拍照)      │                       │  (存储+API+控制)  │
└─────────────────┘                       └─────────────────┘
        │                                           │
        ▼                                           ▼
   DHT11 温湿度传感器                          SQLite 数据库
   土壤湿度传感器                               Flask Web API
   Raspberry Pi 摄像头                         MQTT 消息中转
```

## 功能特性

### 树莓派端
- **DHT11 温湿度采集**：读取空气温度与湿度数据
- **土壤湿度监测**：检测土壤干湿状态
- **摄像头拍照**：1080P 拍摄作物照片
- **定时自动采集**：每小时自动采集一次数据并上报
- **MQTT 远程控制**：接收服务器命令，执行采集任务并返回结果
- **SFTP 上传**：将照片上传到服务器指定目录
- **线程安全**：传感器访问加锁，避免并发冲突
- **日志记录**：定时任务与 MQTT 任务分开记录日志

### 服务器端
- **数据存储**：SQLite 数据库存储历史数据
- **REST API**：
  - `/api/hello`：获取最新一条数据
  - `/api/Sensor/last7days`：获取 7 天内传感器数据
  - `/api/images/last7days`：获取 7 天内图片记录
- **远程控制**：通过 MQTT 发送命令，远程触发树莓派采集任务
- **MQTT 消息中转**：接收树莓派上报的数据，转发给前端

## 项目结构

```
Raspberry-dome/
├── Raspberry/                    # 树莓派端代码
│   ├── Raspberry_Pi_0.1/         # v0.1 初版
│   ├── Raspberry_pi_0.2/         # v0.2 增加主控制器
│   └── Raspberry_Pi_0.3/         # v0.3 稳定版（推荐）
│       ├── config.py             # 配置文件（MQTT、传感器、SFTP）
│       ├── logger.py             # 日志模块
│       └── main_controller.py    # 主程序（传感器采集+MQTT+定时任务）
└── 服务器/                       # 服务器端代码
    └── 服务器_0.1/
        ├── app.py                # Flask 主程序（API+MQTT）
        └── CheShi.py             # 测试脚本
```

## 硬件清单

### 树莓派端
| 组件 | 型号 | 说明 |
|------|------|------|
| 开发板 | Raspberry Pi Zero W | 带 WiFi，体积小适合部署 |
| 温湿度传感器 | DHT11 | 单总线数字传感器 |
| 土壤湿度传感器 | 电阻式土壤湿度传感器 | 数字输出（湿=0，干=1） |
| 摄像头 | Raspberry Pi Camera Module | 1080P 拍照 |
| 电源 | 5V Micro USB | 稳定供电 |

### 接线说明
| 传感器 | 树莓派 GPIO 引脚 |
|--------|------------------|
| DHT11 数据引脚 | GPIO4 (物理引脚 7) |
| 土壤湿度 DO 引脚 | GPIO17 (物理引脚 11) |

## 部署指南

### 树莓派端部署

1. **安装依赖**
```bash
pip install adafruit-circuitpython-dht board RPi.GPIO paramiko paho-mqtt
```

2. **配置参数**
编辑 `config.py`，修改以下配置：
- `MQTT_BROKER` / `MQTT_PORT`：MQTT 服务器地址
- `SOIL_PIN`：土壤湿度传感器 GPIO 引脚
- `SERVER_IP` / `SERVER_PORT` / `USERNAME` / `PASSWORD`：SFTP 服务器配置
- `REMOTE_DIR`：照片上传目录

3. **创建工作目录**
```bash
mkdir -p /home/pi/Raspberry_Pi/logs
mkdir -p /home/pi/Raspberry_Pi/Local_image
```

4. **运行程序**
```bash
python main_controller.py
```

5. **设置开机自启（可选）**
编辑 `/etc/rc.local`，添加：
```bash
python /home/pi/Raspberry_Pi/main_controller.py &
```

### 服务器端部署

1. **安装依赖**
```bash
pip install flask paho-mqtt
```

2. **创建数据库**
```bash
sqlite3 nano.db
CREATE TABLE record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    时间 TEXT,
    图片位置 TEXT,
    空气温度 REAL,
    空气湿度 REAL,
    土壤状态 TEXT,
    ai内容 TEXT
);
```

3. **运行服务**
```bash
python app.py
```

服务默认运行在 `http://0.0.0.0:8000`

## API 接口文档

### 获取最新数据
```
GET /api/hello
```
**返回示例：**
```json
{
  "code": 200,
  "msg": "成功",
  "data": {
    "时间": "2026-10-27 12:00:00",
    "图片位置": "/ShujuTp/Gctp_Element-20261027_120000.jpg",
    "空气温度": 25.6,
    "空气湿度": 65.2,
    "土壤状态": "Wet",
    "ai内容": ""
  }
}
```

### 获取 7 天传感器数据
```
GET /api/Sensor/last7days
```

### 获取 7 天图片记录
```
GET /api/images/last7days
```

### 远程触发采集
```
GET /api/andout
```
通过 MQTT 发送命令给树莓派，等待树莓派采集完成并返回结果。

## 技术栈

- **树莓派端**：Python 3.9+、RPi.GPIO、Adafruit DHT、paho-mqtt、paramiko (SFTP)
- **服务器端**：Flask 2.x、SQLite、paho-mqtt
- **通信协议**：MQTT（broker.emqx.io 公共服务器）
- **文件传输**：SFTP

## 版本历史

- **v0.3**：稳定版，统一传感器管理，线程安全，日志分离
- **v0.2**：增加主控制器，集成定时任务与 MQTT 响应
- **v0.1**：初版，基础传感器采集

## 许可证

本项目仅供学习与参考使用。
