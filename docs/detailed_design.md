# 详细设计文档 (Detailed Design Document)

## 1. 前端实现 (Host App - Electron)

### 1.1 目录结构
*   `main.js`: Electron 主进程入口。负责管理窗口生命周期、TCP 控制连接 (8888)、UDP 视频接收 (8889) 以及 IPC 路由。
*   `preload.js`: Context Bridge，安全地将 Node.js API 暴露给渲染进程。定义了 `window.api` 接口。
*   `index.html`: 渲染进程 UI 结构。采用原生 HTML5 和 CSS Grid/Flexbox 布局，无需构建工具。
*   `renderer.js`: 渲染进程逻辑。负责 DOM 操作、事件绑定、接收 IPC 消息更新 UI。

### 1.2 核心模块设计

#### 1.2.1 视频渲染模块 (Video Renderer)
*   **接收机制**: 主进程通过 UDP 监听 8889 端口，收到 JPEG 数据后，转换为 Base64 字符串，通过 IPC `video-frame` 事件发送给渲染进程。
*   **显示机制**: 渲染进程监听 `video-frame`，将 Base64 字符串直接赋值给 `<img>` 标签的 `src` 属性。
*   **长宽比控制**: 通过切换 `<img>` 元素的 CSS `object-fit` 属性 (`contain` 为保持比例/Letterbox，`fill` 为拉伸铺满)。

#### 1.2.2 控制指令下发模块
*   **摇杆/方向键**: 在 `renderer.js` 中通过 `setInterval` 实现持续按压检测。按下时以一定频率 (如 50ms) 发送速度指令，松开时发送停止指令。
*   **IPC 桥接**: 调用 `window.api.sendControl(speed, turn)`。
*   **协议打包**: 在 `main.js` 的 `sendPacket` 函数中，将 JSON Payload 编码为二进制流，附带 `0xAA55` 包头、长度、命令 ID 和 CRC32 校验码，通过 TCP Socket 发送。

---

## 2. 后端实现 (Slave Simulator - Python)

### 2.1 目录结构
*   `simulator.py`: 核心网络与状态机逻辑。包含 `asyncio` TCP Server 和 UDP 推流循环。
*   `render_engine.py`: 3D 渲染引擎，封装了 PyOpenGL 的复杂调用。

### 2.2 核心模块设计

#### 2.2.1 3D 渲染引擎 (`render_engine.py`)
*   **上下文管理**: 使用 `pygame` 创建不可见的 OpenGL 上下文 (`HIDDEN` 模式)。
*   **几何生成**: 使用 `gluCylinder` 生成空心圆柱体代表管道。为实现无限延伸效果，不移动相机 Z 轴，而是通过修改纹理坐标的 V 值来实现纹理滚动。
*   **真实照片映射**: 
    *   读取 `assets/real_sewer.jpg`。
    *   使用 OpenCV (`cv2.linearPolar` 或降级方案) 将同心圆视角的照片展开为长方形贴图。
    *   将展开后的贴图绑定到 OpenGL 的 2D 纹理对象上。
*   **光照模型**: 启用 `GL_LIGHTING` 和 `GL_LIGHT0`，设置环境光(Ambient)、漫反射(Diffuse)和镜面反射(Specular)，模拟手电筒照明效果。

#### 2.2.2 视频管线与优化 (`simulator.py`)
*   **渲染提取**: 从 OpenGL 颜色缓冲区读取像素 `glReadPixels`，转换为 NumPy 数组。
*   **智能缩放**: 为了满足 UDP 传输限制且不让画面变形，先计算 1:1 照片到 4:3 视频框的缩放比，使用 `cv2.resize` 进行 `INTER_AREA` 降采样，然后将其居中放置在 320x240 的黑色画布上 (Letterbox)。
*   **OSD 叠加**: 在缩放后的 320x240 画布上，使用 `cv2.putText` 叠加电池、速度等遥测数据，并使用 `cv2.LINE_AA` 保证文字边缘平滑锐利。
*   **本地录像**: 如果开启了录像功能，使用 `cv2.VideoWriter` (`mp4v` 编码器) 将高分辨率的原始渲染帧写入本地磁盘。