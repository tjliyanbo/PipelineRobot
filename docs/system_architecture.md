# 系统架构设计 (System Architecture Design)

## 1. 总体架构
系统采用 C/S (Client-Server) 架构，结合独立双链路通信设计。
*   **Client (Host)**: Electron (UI) + Node.js (Logic/Driver)。跨平台，使用 HTML5/CSS3 构建现代化高对比度工业风界面。
*   **Server (Simulator)**: Python (3D Simulator)。使用 `PyOpenGL` 和 `OpenCV` 实现高保真管道内部环境实时渲染与物理状态模拟。

## 2. 上位机控制端 (Host Control Software) - Electron

### 2.1 架构分层
*   **表现层 (Presentation Layer)**:
    *   **技术栈**: 原生 HTML/CSS/JS (Vanilla JS)，无额外框架依赖，保证极致性能与加载速度。
    *   **视觉风格**: 高对比度工业风 (Dark Theme, Cyber Cyan / Industrial Orange)。
    *   **功能**: 
        *   `VideoPanel`: UDP 视频流接收与 Canvas 渲染，支持拉伸/等比缩放切换，悬浮控制工具栏。
        *   `Dashboard`: 传感器数据仪表盘 (温度、湿度、气压、电池)。
        *   `ControlPanel`: 运动控制 (D-Pad 方向键, 复位键)，照明控制，连接状态指示。
        *   `LogConsole`: 底部结构化彩色日志输出。
    *   **通信**: 通过 `preload.js` (ContextBridge) / `IPC` 与主进程通信。

*   **业务层 & 驱动层 (Business/Driver Layer) - Main Process**:
    *   **TcpClient**: Node.js `net.Socket`。负责低延迟发送控制指令 (运动、照明、视频开关、截图等) 与接收传感器遥测数据。
    *   **UdpServer**: Node.js `dgram`。绑定 `8889` 端口，独立接收来自模拟器的 JPEG 视频帧，解除视频流与控制流的耦合。
    *   **ProtocolParser**: 协议编码/解码 (Binary/JSON)，处理包头校验与数据解包。

### 2.2 数据流
1.  **控制流 (UI -> Simulator)**: 用户点击 -> IPC Invoke -> Main Process -> 组装二进制包 (0xAA55头 + Payload) -> TCP Socket (8888) -> Simulator。
2.  **遥测流 (Simulator -> UI)**: Simulator -> TCP Socket -> Main Process (Parser) -> IPC Send -> Renderer (Update DOM)。
3.  **视频流 (Simulator -> UI)**: Simulator -> OpenCV Encode -> UDP Socket (8889) -> Main Process -> IPC Send (Base64) -> Renderer (Image Source)。

## 3. 下位机模拟器 (Slave Execution Simulator) - Python

### 3.1 架构模块
*   **Network Interface**: 
    *   `asyncio` TCP Server (8888) 接收控制指令。
    *   `socket` UDP Client 发送视频流到 `8889`。
*   **State Machine**: 维护机器人位姿 (x, y, z, yaw, pitch)、传感器状态、视频/照明开关、录制状态。
*   **3D Render Engine (`render_engine.py`)**:
    *   **技术栈**: `PyOpenGL`, `pygame` (Context), `cv2` (Texture Processing)。
    *   **渲染管线**: 圆柱体几何生成 -> 纹理映射 (支持 procedural PBR 或 真实照片极坐标展开) -> 光照计算 (双面材质，衰减光) -> 摄像机变换。
*   **Media Pipeline**:
    *   **帧处理**: OpenGL Buffer -> OpenCV (BGR) -> 智能缩放保持比例 (Letterboxing) -> 叠加 OSD 文本 -> JPEG 压缩。
    *   **输出**: UDP 实时流、本地高清 MP4 录制、JPG 截图。

## 4. 接口定义

### 4.1 通信协议 (TCP Packet Structure)
| Field | Size (Bytes) | Description |
| :--- | :--- | :--- |
| Header | 2 | Magic Number (0xAA 0x55) |
| Length | 4 | Payload Length (uint32) |
| CommandID | 1 | Instruction Type (uint8) |
| Payload | N | JSON Encoded String |
| CRC32 | 4 | Checksum (uint32) |

### 4.2 主要指令 (Command IDs)
*   `0x01`: 遥测数据上报 (Telemetry)
*   `0x02`: 运动控制 (Speed, Turn)
*   `0x03`: 重置位姿 (Reset Yaw)
*   `0x10`: 视频流开关 (Video Toggle)
*   `0x11`: 渲染模式切换 (CG / 真实照片)
*   `0x12`: 截图请求 (Snapshot)
*   `0x13`: 录像开关 (Toggle Recording)
*   `0x14`: 照明开关 (Light Toggle)
