from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from typing import List, Dict
import json
import asyncio
import cv2
import os
from datetime import datetime
import threading
import queue
import logging
from logging.handlers import RotatingFileHandler
import sys
import websockets
import base64

app = FastAPI()

# 图片处理配置
IMAGE_WIDTH = 640  # 压缩后的图片宽度
IMAGE_QUALITY = 85  # JPEG压缩质量（0-100）
JPEG_EXTENSION = '.jpg'

# 服务器配置
SERVER_WS_URL = "ws://192.168.0.69:5000/ws"  # 服务器WebSocket地址

# 日志配置
LOG_DIR = os.path.expanduser("~/ml-fastvlm-logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "client.log")

# 配置日志
logger = logging.getLogger("ml-fastvlm-client")
logger.setLevel(logging.INFO)

# 文件处理器（按大小轮转）
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

# 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 设置日志格式
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# 添加处理器
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 全局变量
camera = None
capture_lock = threading.Lock()
active_connections: List[WebSocket] = []
web_connections: Dict[WebSocket, bool] = {}  # 网页WebSocket连接
frame_queue = queue.Queue(maxsize=2)  # 用于存储最新的帧

# 创建图片保存目录
IMAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

def print_progress(message):
    """打印带时间戳的进度信息"""
    logger.info(message)

def get_camera():
    """获取摄像头对象"""
    global camera
    if camera is None:
        try:
            # 尝试不同的摄像头索引
            for i in range(2):  # 尝试前两个摄像头索引
                camera = cv2.VideoCapture(i)
                if camera.isOpened():
                    ret, frame = camera.read()
                    if ret and frame is not None:
                        logger.info(f"📹 成功打开摄像头 {i}")
                        # 设置摄像头参数
                        camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
                        camera.set(cv2.CAP_PROP_EXPOSURE, -4)
                        camera.set(cv2.CAP_PROP_GAIN, 100)
                        camera.set(cv2.CAP_PROP_BRIGHTNESS, 150)
                        return camera
                    else:
                        camera.release()
                        logger.warning(f"摄像头 {i} 无法读取画面")
                else:
                    logger.warning(f"无法打开摄像头 {i}")
            
            # 如果所有尝试都失败，使用默认摄像头
            camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                raise Exception("无法打开任何摄像头")
            
            logger.info("📹 摄像头初始化完成")
        except Exception as e:
            logger.error(f"❌ 摄像头初始化失败: {e}")
            raise
    return camera

def compress_image(frame):
    """压缩图片到指定尺寸和质量"""
    # 计算压缩后的高度，保持宽高比
    height = int(frame.shape[0] * (IMAGE_WIDTH / frame.shape[1]))
    
    # 调整图片大小
    resized = cv2.resize(frame, (IMAGE_WIDTH, height), interpolation=cv2.INTER_AREA)
    
    return resized

def save_image(frame, filepath):
    """保存压缩后的图片"""
    # 压缩图片
    compressed = compress_image(frame)
    
    # 保存为JPEG格式，指定压缩质量
    cv2.imwrite(filepath, compressed, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_QUALITY])
    
    # 获取压缩后的文件大小
    file_size = os.path.getsize(filepath) / 1024  # 转换为KB
    logger.info(f"📊 图片大小: {file_size:.1f}KB")
    
    return compressed

async def capture_frames():
    """持续捕获摄像头画面"""
    global camera
    while True:
        try:
            camera = get_camera()
            if camera is None:
                logger.error("❌ 摄像头未初始化")
                await asyncio.sleep(1)
                continue

            ret, frame = camera.read()
            if not ret or frame is None:
                logger.error("❌ 无法读取摄像头画面")
                camera = None
                await asyncio.sleep(1)
                continue

            # 压缩图片
            compressed = compress_image(frame)
            
            # 将图片转换为JPEG格式
            _, buffer = cv2.imencode('.jpg', compressed, [cv2.IMWRITE_JPEG_QUALITY, IMAGE_QUALITY])
            jpeg_data = buffer.tobytes()
            
            # 更新帧队列
            if not frame_queue.full():
                frame_queue.put(jpeg_data)
            else:
                try:
                    frame_queue.get_nowait()  # 移除旧帧
                    frame_queue.put(jpeg_data)  # 添加新帧
                except queue.Empty:
                    pass

        except Exception as e:
            logger.error(f"❌ 捕获画面时出错: {e}")
            camera = None
        
        await asyncio.sleep(1)  # 每秒捕获一次

async def broadcast_frames():
    """向所有网页连接广播最新的帧"""
    while True:
        try:
            if not frame_queue.empty():
                frame_data = frame_queue.get()
                # 将二进制数据转换为base64字符串
                frame_base64 = base64.b64encode(frame_data).decode('utf-8')
                
                # 向所有网页连接发送帧
                for websocket in list(web_connections.keys()):
                    try:
                        await websocket.send_json({
                            "type": "frame",
                            "data": frame_base64
                        })
                    except:
                        # 如果发送失败，移除连接
                        web_connections.pop(websocket, None)
        except Exception as e:
            logger.error(f"❌ 广播画面时出错: {e}")
        
        await asyncio.sleep(0.1)  # 每100ms检查一次

async def send_to_server():
    """将捕获的画面发送到服务器"""
    while True:
        try:
            async with websockets.connect(SERVER_WS_URL) as websocket:
                logger.info("🔌 已连接到服务器")
                
                while True:
                    try:
                        if not frame_queue.empty():
                            frame_data = frame_queue.get()
                            await websocket.send(frame_data)
                            logger.info("📤 图片数据已发送到服务器")
                            
                            # 等待服务器返回的描述结果
                            data = await websocket.recv()
                            try:
                                result = json.loads(data)
                                if result.get("type") == "description":
                                    logger.info(f"📥 收到服务器描述结果: {result.get('content')}")
                                    # 广播描述结果给所有网页连接
                                    for ws in list(web_connections.keys()):
                                        try:
                                            await ws.send_json(result)
                                        except:
                                            web_connections.pop(ws, None)
                            except json.JSONDecodeError:
                                logger.error("❌ 收到无效的JSON数据")
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("🔌 与服务器的连接已断开")
                        break
                    except Exception as e:
                        logger.error(f"❌ 处理服务器通信时出错: {e}")
                        break
                
        except Exception as e:
            logger.error(f"❌ 连接服务器时出错: {e}")
        
        await asyncio.sleep(5)  # 等待一段时间后重试连接

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """处理网页WebSocket连接"""
    await websocket.accept()
    web_connections[websocket] = True
    logger.info("🔌 新的网页连接已建立")
    
    try:
        while True:
            # 保持连接活跃
            await websocket.receive_text()
    except WebSocketDisconnect:
        web_connections.pop(websocket, None)
        logger.info("🔌 网页连接已断开")

# 挂载静态文件
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

@app.get("/", response_class=HTMLResponse)
async def get():
    """返回主页"""
    try:
        template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
        if not os.path.exists(template_path):
            logger.error(f"❌ 模板文件不存在: {template_path}")
            return HTMLResponse(content="<h1>错误：找不到模板文件</h1>", status_code=500)
        
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"❌ 读取模板文件时出错: {e}")
        return HTMLResponse(content="<h1>错误：无法读取模板文件</h1>", status_code=500)

if __name__ == "__main__":
    logger.info("🚀 启动树莓派客户端...")
    logger.info(f"📁 日志文件位置: {LOG_FILE}")
    
    # 检查必要的目录和文件
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    
    if not os.path.exists(template_dir):
        logger.error(f"❌ 模板目录不存在: {template_dir}")
        sys.exit(1)
    
    if not os.path.exists(static_dir):
        logger.error(f"❌ 静态文件目录不存在: {static_dir}")
        sys.exit(1)
    
    template_file = os.path.join(template_dir, "index.html")
    if not os.path.exists(template_file):
        logger.error(f"❌ 模板文件不存在: {template_file}")
        sys.exit(1)
    
    logger.info("✅ 所有必要的文件和目录检查通过")
    
    # 创建事件循环
    loop = asyncio.get_event_loop()
    
    # 启动所有任务
    tasks = [
        loop.create_task(capture_frames()),
        loop.create_task(broadcast_frames()),
        loop.create_task(send_to_server())
    ]
    
    # 启动FastAPI服务器
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, loop=loop)
    server = uvicorn.Server(config)
    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在关闭...")
    finally:
        for task in tasks:
            task.cancel()
        loop.stop()
        loop.close()
        logger.info("服务已关闭。") 