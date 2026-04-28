import sqlite3
import paho.mqtt.client as mqtt
from datetime import datetime
import requests
import base64

# -----------------------------------变量准备-----------------------------------------
# 3. AI大模型配置（硅基流动，和你之前项目一致）
AI_API_KEY = "sk-qmujjbzwilkmjdmdjtwvlfivvplphusauoudjvrckojyybvt"  # 替换成你的真实KEY
AI_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
AI_MODEL_NAME = "Pro/moonshotai/Kimi-K2.5"  # 或 deepseek-ai/deepseek-vl-7b-chat
# -------------------------------------变量准备---------------------------------------
# 初始化数据库（安全建表）
def init_db():
    conn = sqlite3.connect("nano.db")
    conn.execute('''
                 CREATE TABLE IF NOT EXISTS record
                 (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     时间 TEXT,
                     图片位置信息 TEXT,
                     空气温度 TEXT,
                     空气湿度 TEXT,
                     土壤状态 TEXT,
                     Ai内容 TEXT
                 )
                 ''')
    conn.commit()
    conn.close()


init_db()
print("数据库已准备完成")


# 查询并打印数据库里所有记录
def print_all_records():
    try:
        conn = sqlite3.connect("nano.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM record")
        records = cursor.fetchall()

        print("\n====== 📋 数据库所有记录 ======")
        if not records:
            print("暂无数据")
        else:
            for row in records:
                print(f"ID: {row[0]}")
                print(f"时间: {row[1]}")
                print(f"图片位置: {row[2]}")
                print(f"空气温度: {row[3]}")
                print(f"空气湿度: {row[4]}")
                print(f"土壤状态: {row[5]}")
                print("-" * 40)
        print("==============================\n")
        conn.close()
    except Exception as e:
        print("打印数据库失败：", e)

# ======================== ai函数体=========================
def send_to_ai(image_base64,data1,data2,data3):
    """将最新图片+最新传感器数据发送给AI，获取番茄生长综合分析"""
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }

    # 构造专业提示词，完全贴合你的番茄种植项目
    prompt = f"""
【最新传感器环境数据】
- 土壤状态：{data1}
- 空气温度：{data2}℃
- 空气湿度：{data3}%

请分析：
1.  植株健康状态：是否健康，有无徒长、黄叶、萎蔫等问题
2.  病虫害识别：是否存在病虫害，若有请说明具体类型和特征
3.  环境适宜性：结合温湿度、土壤状态，判断当前环境是否适合番茄生长
4.  只要:actionable建议：给出具体可执行的养护调整建议（浇水、通风、施肥等）
5.  回答不要换行，一句答完
"""

    # 构造AI请求体（标准多模态格式）
    payload = {
        "model": AI_MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.3,  # 低温度，保证分析客观稳定
        "max_tokens": 50  # 足够长的回复，覆盖完整分析
    }

    try:
        # 调用AI接口
        response = requests.post(AI_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        # 提取AI回复
        ai_answer = result["choices"][0]["message"]["content"]
        return ai_answer

    except Exception as e:
        print(f"❌ 调用AI接口失败：{str(e)}")
        return None


# ========================ai函数体=======================


# ==================== 订阅端核心代码 ====================
def on_message(client, userdata, msg):
    try:
        # 1. 收到消息
        data = msg.payload.decode().strip()
        print("收到消息：", data)

        # 2. 安全拆分
        parts = data.split(",")
        Tupian = parts[0].split(":")[1] if len(parts) > 0 else "无"
        wendu = parts[1].split(":")[1] if len(parts) > 1 else "无"
        shidu = parts[2].split(":")[1] if len(parts) > 2 else "无"
        turang = parts[3].split(":")[1] if len(parts) > 3 else "无"

        # 3. 自动生成时间
        shijian = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # --------------------ai专场--------------------------------
        ai = f"http://39.106.159.23/{Tupian}"
        resp = requests.get(ai, timeout=30)
        resp.raise_for_status()
        image_base64 = base64.b64encode(resp.content).decode("utf-8")
        neirong = send_to_ai(image_base64,turang,wendu,shidu)
        # -------------------ai专场--------------------------------
        # 4. 写入数据库
        conn = sqlite3.connect("nano.db")
        conn.execute('''
                     INSERT INTO record (时间, 图片位置信息, 空气温度, 空气湿度, 土壤状态, Ai内容)
                     VALUES (?, ?, ?, ?, ?, ?)
                     ''', (shijian, Tupian, wendu, shidu, turang,neirong))
        conn.commit()
        conn.close()
        print("✅ 已保存到数据库")

        # 打印刚保存的这条数据
        print("\n====-- 刚存入的数据 --====")
        print(f"时间：{shijian}")
        print(f"图片位置：{Tupian}")
        print(f"温度：{wendu}")
        print(f"湿度：{shidu}")
        print(f"土壤：{turang}")
        print(f"ai内容：{neirong}")
        print("------------------------\n")

        # 可选：打印数据库所有记录（想看全部就打开）
        # print_all_records()

    except Exception as e:
        print("⚠️  消息格式异常，已安全跳过：", e)


# ==================== MQTT 监听 ====================
client = mqtt.Client()
client.on_message = on_message
client.connect("broker.emqx.io", 1883, 60)
client.subscribe("test/longge")

print("正在监听消息...\n")
client.loop_forever()
