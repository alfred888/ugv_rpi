import cv2
import subprocess
import tempfile
import os

# FastVLM 模型路径
MODEL_PATH = "checkpoints/llava-fastvithd_0.5b_stage3"
PROMPT = "用给小朋友讲卡片的语气，简短的描述图片内容，用30个字"

def capture_image():
    """拍摄一帧图像，保存为临时文件"""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError("无法打开摄像头")
    ret, frame = cap.read()
    cap.release()

    if not ret:
        raise RuntimeError("无法读取摄像头画面")

    temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    cv2.imwrite(temp_file.name, frame)
    return temp_file.name

def describe_image(image_path):
    """调用 FastVLM 模型描述图像内容"""
    cmd = [
        "python", "predict.py",
        "--model-path", MODEL_PATH,
        "--image-file", image_path,
        "--prompt", PROMPT
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("\n📋 识别结果：\n")
    print(result.stdout)

if __name__ == "__main__":
    print("🎥 正在拍摄图像...")
    img_path = capture_image()
    try:
        describe_image(img_path)
    finally:
        os.remove(img_path)