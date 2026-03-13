# 管道机器人软件系统使用说明 (User Manual)

## 1. 项目简介
本项目包含两部分：
1.  **Host App (上位机)**: 基于 Electron 开发的控制端软件，运行在 Windows/Linux/macOS。
2.  **Slave Simulator (下位机模拟器)**: 基于 Python 开发的设备模拟器，用于测试通信与控制逻辑。

## 2. 环境准备
*   **Node.js**: v16.0.0 或更高版本 (用于运行上位机)
*   **Python**: 3.8 或更高版本 (用于运行模拟器)

## 3. 安装步骤

### 3.1 上位机 (Host App)
1.  进入目录:
    ```bash
    cd host-app
    ```
2.  安装依赖 (如果尚未安装):
    ```bash
    npm install
    ```

### 3.2 模拟器 (Slave Simulator)
1.  进入目录:
    ```bash
    cd slave-sim
    ```
2.  (可选) 创建虚拟环境:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```
3.  无需额外依赖 (仅使用标准库 `asyncio`, `json`, `struct`, `zlib`)。

## 4. 运行说明

### 第一步：启动模拟器
在终端中运行：
```bash
python slave-sim/simulator.py
```
*输出示例*: `Simulator serving on 127.0.0.1:8888`

### 第二步：启动上位机
在另一个终端中运行：
```bash
cd host-app
npm start
```
*   程序启动后，点击左侧边栏的 **"Connect to Simulator"** 按钮。
*   状态应变为绿色 **"Connected"**。
*   仪表盘数据 (Battery, Pressure) 应开始跳动。
*   拖动 **Speed** 或 **Turn** 滑块，观察模拟器终端的日志输出 (e.g., `Received Cmd: 2, Payload: {'speed': 0.5...}`).

## 5. 功能特性
*   **通信协议**: 自定义二进制头 + JSON 负载，集成 CRC32 校验。
*   **断线重连**: 上位机具备自动检测断开并提示功能。
*   **实时遥测**: 模拟器以 20Hz 频率发送电池、气压、姿态数据。
*   **控制指令**: 支持速度与转向的实时调节。

## 6. 文件结构
*   `host-app/`: Electron 项目源码
    *   `main.js`: 主进程 (TCP 通信核心)
    *   `renderer.js`: 渲染进程 (UI 逻辑)
*   `slave-sim/`: Python 模拟器源码
    *   `simulator.py`: 模拟器核心逻辑
*   `docs/`: 设计文档
    *   `requirements_traceability_matrix.md`: 需求追踪矩阵
    *   `system_architecture.md`: 系统架构设计
