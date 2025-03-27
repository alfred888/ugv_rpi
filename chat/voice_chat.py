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
        # 设置语音合成参数
        self.engine.setProperty('rate', 150)    # 语速
        self.engine.setProperty('volume', 0.9)  # 音量
        # 设置唤醒词
        self.wake_word = "你好小助手"
        # 对话状态
        self.is_active = False
        
    def listen(self):
        """监听用户语音输入"""
        with sr.Microphone() as source:
            print("正在听..." if self.is_active else "等待唤醒词...")
            # 调整环境噪声
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio, language='zh-CN')
                print(f"您说: {text}")
                return text
            except sr.WaitTimeoutError:
                return None
            except sr.UnknownValueError:
                return None
            except sr.RequestError as e:
                print(f"无法连接到Google Speech Recognition服务: {e}")
                return None

    def speak(self, text):
        """将文本转换为语音输出"""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"语音输出错误: {e}")

    def get_chatgpt_response(self, user_input):
        """获取ChatGPT的回复"""
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "你是一个友好的AI助手，请用简洁的中文回答。"},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.7,
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"获取ChatGPT回复时出错: {e}")
            return "抱歉，我现在无法回答。"

    def check_wake_word(self, text):
        """检查是否包含唤醒词"""
        return self.wake_word in text

    def run(self):
        """运行语音对话程序"""
        print("语音聊天机器人已启动！")
        print(f'请说"{self.wake_word}"来唤醒我')
        print('说"退出"结束对话')
        
        while True:
            user_input = self.listen()
            
            if user_input is None:
                continue
            
            # 检查唤醒词
            if not self.is_active:
                if self.check_wake_word(user_input):
                    self.is_active = True
                    self.speak("你好！我在听")
                    print("已唤醒，请说话")
                continue
            
            # 检查退出命令
            if user_input.lower() in ['退出', '再见', '拜拜']:
                self.speak("再见！")
                self.is_active = False
                print("已退出对话模式")
                continue
                
            # 获取ChatGPT回复
            response = self.get_chatgpt_response(user_input)
            print(f"AI: {response}")
            
            # 语音输出回复
            self.speak(response)
            
            # 短暂暂停，避免语音重叠
            time.sleep(0.5)

if __name__ == "__main__":
    # 检查环境变量
    if not os.getenv('OPENAI_API_KEY'):
        print("错误：未设置OPENAI_API_KEY环境变量")
        print("请在.env文件中设置您的OpenAI API密钥")
        exit(1)
        
    chat = VoiceChat()
    chat.run() 