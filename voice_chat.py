import speech_recognition as sr
import pyttsx3
import openai
import os
from dotenv import load_dotenv
import time

# 加载环境变量
load_dotenv()

# 配置OpenAI API
openai.api_key = os.getenv('OPENAI_API_KEY')

class VoiceChat:
    def __init__(self):
        # 初始化语音识别器
        self.recognizer = sr.Recognizer()
        # 初始化语音合成器
        self.engine = pyttsx3.init()
        # 设置语音参数
        self.engine.setProperty('rate', 150)  # 语速
        self.engine.setProperty('volume', 1.0)  # 音量
        
    def listen(self):
        """监听麦克风输入"""
        with sr.Microphone(device_index=2) as source:  # 使用USB摄像头的麦克风
            print("正在听...")
            # 调整环境噪声
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                print("正在识别...")
                text = self.recognizer.recognize_google(audio, language='zh-CN')
                print(f"识别结果: {text}")
                return text
            except sr.WaitTimeoutError:
                print("没有检测到语音")
                return None
            except sr.UnknownValueError:
                print("无法识别语音")
                return None
            except sr.RequestError as e:
                print(f"无法连接到Google语音识别服务: {e}")
                return None

    def speak(self, text):
        """语音输出"""
        print(f"机器人: {text}")
        self.engine.say(text)
        self.engine.runAndWait()

    def get_chatgpt_response(self, text):
        """获取ChatGPT回复"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "你是一个友好的AI助手，请用简短的语言回答问题。"},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"ChatGPT API错误: {e}")
            return "抱歉，我现在无法回答。"

    def run(self):
        """运行语音对话"""
        print("语音对话程序已启动，按Ctrl+C退出")
        try:
            while True:
                # 监听用户输入
                user_input = self.listen()
                if user_input:
                    # 获取ChatGPT回复
                    response = self.get_chatgpt_response(user_input)
                    # 语音输出回复
                    self.speak(response)
                time.sleep(0.1)  # 短暂延迟，避免CPU占用过高
        except KeyboardInterrupt:
            print("\n程序已退出")

if __name__ == "__main__":
    # 创建.env文件（如果不存在）
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write('OPENAI_API_KEY=你的OpenAI API密钥\n')
        print("请在.env文件中设置你的OpenAI API密钥")
    else:
        chat = VoiceChat()
        chat.run() 