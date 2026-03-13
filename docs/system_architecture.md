# 系统架构设计 (System Architecture Design)

## 1. 总体架构
系统采用 C/S (Client-Server) 架构。
*   **Client (Host)**: Electron (UI) + Node.js (Logic/Driver). 跨平台，适合富交互界面。
*   **Server (Simulator/Device)**: Python (Simulator) / Embedded C (Real Device). 模拟器使用 Python 实现快速开发与脚本支持。

## 2. 上位机控制端 (Host Control Software) - Electron

### 2.1 架构分层
*   **表现层 (Presentation Layer)**:
    *   **技术栈**: React, Material-UI/AntD, Recharts (图表).
    *   **功能**: 
        *   `VideoPanel`: 视频流显示 (Canvas/HTML5 Video).
        *   `Dashboard`: 传感器数据仪表盘.
        *   `ControlPanel`: 运动控制 (Joystick, Slider).
        *   `Settings`: 参数配置.
    *   **通信**: 通过 `ContextBridge` / `IPC` 与主进程通信.

*   **业务层 (Business Layer) - Main Process**:
    *   **ModuleManager**: 模块生命周期管理.
    *   **DataStore**: 内存数据缓存 (Redux/MobX state equivalent in Main).
    *   **LogService**: 结构化日志记录与审计 (winston/electron-log).
    *   **SecurityService**: AES-256 加密/解密.

*   **驱动层 (Driver Layer) - Main Process**:
    *   **TcpClient**: Node.js `net.Socket`. 处理粘包/拆包.
    *   **UdpClient**: Node.js `dgram`. 处理视频流/高频数据.
    *   **ProtocolParser**: 协议编码/解码 (Binary/Protobuf/JSON).
    *   **HealthMonitor**: 心跳保活与重连逻辑.

### 2.2 数据流
1.  **UI -> Device**: 用户点击 -> React Component -> IPC Invoke -> Main Process -> Protocol Encode -> TCP Socket -> Device.
2.  **Device -> UI**: Device -> TCP Socket -> Main Process (Parser) -> IPC Send -> React Component (Update State).

## 3. 下位机模拟器 (Slave Execution Simulator) - Python

### 3.1 架构模块
*   **Network Interface**: `asyncio` (TCP/UDP Server).
*   **Protocol Handler**: 解析指令，封装响应.
*   **Virtual Device Model**:
    *   `StateMachine`: Idle, Running, Error.
    *   `Sensors`: Battery, IMU, Pressure (Generators).
    *   `Motor`: Position, Velocity (Simulation).
*   **Scenario Engine**:
    *   加载 JSON/XML 脚本.
    *   按时间轴触发事件 (e.g., `at 5s: disconnect`, `at 10s: battery=10%`).
*   **Fault Injector**: 中间件层，拦截发送/接收数据包，人为引入延迟或错误.

## 4. 接口定义 (简略)

### 4.1 通信协议 (TCP Packet Structure)
| Field | Size (Bytes) | Description |
| :--- | :--- | :--- |
| Header | 2 | Magic Number (e.g., 0xA5 0x5A) |
| Length | 2 | Payload Length |
| CommandID | 1 | Instruction Type |
| Sequence | 2 | Packet Sequence ID |
| Payload | N | Data (Protobuf/JSON/Binary) |
| CRC32 | 4 | Checksum |

### 4.2 主要指令 (Command IDs)
*   `0x01`: Heartbeat
*   `0x02`: Motion Control (Speed, Direction)
*   `0x03`: Get Status
*   `0x10`: Video Control (Start/Stop)
*   `0xFF`: Error Report
