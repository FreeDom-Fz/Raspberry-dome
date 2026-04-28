from flask import Flask, jsonify
import sqlite3
from datetime import datetime, timedelta  # 只新增这个导入
import threading
import paho.mqtt.client as mqtt


app = Flask(__name__)
app.json.ensure_ascii = False  # 现代 Flask 2.x / 3.x 唯一正确写法
# 原有接口 —— 获取最新一条数据（完全不动）
@app.route('/api/hello', methods=["GET"])
def hello():
   try:
       conn = sqlite3.connect("nano.db")
       cursor = conn.execute("SELECT * FROM record ORDER BY id DESC LIMIT 1")
       row = cursor.fetchone()
       conn.close()

       if row is None:
           return jsonify({
               "code": 404,
               "msg": "暂无数据",
               "data": None
           })

       shijian = row[1]
       tupian = row[2]
       wendu = row[3]
       shidu = row[4]
       zhuangtai = row[5]
       ai = row[6]

       return jsonify({
           "code": 200,
           "msg": "成功",
           "data": {
               "时间": shijian,
               "图片位置": tupian,
               "空气温度": wendu,
               "空气湿度": shidu,
               "土壤状态": zhuangtai,
               "ai内容" : ai
           }
       })

   except Exception as e:
       return jsonify({"code": 500, "msg": f"错误：{str(e)}"})
# ==================== 新增接口：获取7天内所有传感器信息 ====================
@app.route('/api/Sensor/last7days', methods=["GET"])
def get_last7days_Sensor():
   try:
       # 7天前的时间
       seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

       conn = sqlite3.connect("nano.db")
       cursor = conn.cursor()

       # 查询：时间 + 温度 + 湿度 + 土壤状态
       cursor.execute('''
           SELECT 时间, 空气温度, 空气湿度, 土壤状态
           FROM record
           WHERE 时间 >= ?
           ORDER BY 时间 DESC
       ''', (seven_days_ago,))

       # 获取所有数据
       cnoc = cursor.fetchall()
       conn.close()

       # 组装正确的数据
       data_list = []
       for row in cnoc:
           data_list.append({
               "时间": row[0],       # 正确
               "空气温度": row[1],   # 正确
               "空气湿度": row[2],   # 正确
               "土壤状态": row[3]    # 正确
           })

       return jsonify({
           "code": 200,
           "msg": "成功",
           "count": len(data_list),
           "data": data_list
       })

   except Exception as e:
       return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"})

# ==================== 新增接口：获取7天内所有图片信息 ====================

@app.route('/api/images/last7days', methods=["GET"])
def get_last7days_images():
   try:
       # 计算7天前的时间
       seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

       conn = sqlite3.connect("nano.db")
       cursor = conn.cursor()

       # 查询 7 天内的所有记录（只需要时间 + 图片路径）
       cursor.execute('''
           SELECT 时间, 图片位置信息, ai内容
           FROM record
           WHERE 时间 >= ?
           ORDER BY 时间 DESC
       ''', (seven_days_ago,))

       rows = cursor.fetchall() #把刚才查到的全部结果 → 放进 rows 里存起来
       conn.close() #关闭游标实例对象
       # 组装返回格式
       data_list = []
       for row in rows:
           data_list.append({
               "时间": row[0],
               "图片路径": row[1],
               "ai内容" : row[2]
           })

       return jsonify({
           "code": 200,
           "msg": "成功",
           "count": len(data_list),  # 条数
           "data": data_list
       })

   except Exception as e:
       return jsonify({"code": 500, "msg": f"服务器错误：{str(e)}"})


# ==================== 新增接口：网页按钮控制树莓派硬件工作 ====================


mqtt_client = mqtt.Client()
response_event = threading.Event()
response_data = None
lock = threading.Lock()  # 解决多线程安全问题

# MQTT 收到消息回调
def on_message(client, userdata, msg):
    global response_data
    topic = msg.topic
    payload = msg.payload.decode().strip()

    # 只处理树莓派回复的主题
    if topic == "test/abc":
        with lock:
            response_data = payload
        response_event.set()  # 解锁 Flask

# 绑定回调
mqtt_client.on_message = on_message

# 连接 + 订阅
mqtt_client.connect("broker.emqx.io", 1883, 60)
mqtt_client.subscribe("test/abc")
mqtt_client.loop_start()  # 后台保持连接，不阻塞！

# ==================== Flask 接口 ====================
@app.route('/api/andout')
def zhiling():
    global response_data

    # 重置状态
    response_event.clear()
    with lock:
        response_data = None

    # 发送指令
    mqtt_client.publish("test/cheshi", "拍照")

    # 等待回复（最多30秒）
    success_wait = response_event.wait(timeout=30)

    # 获取结果
    with lock:
        result = response_data

    # 返回
    if success_wait and result is not None:
        return jsonify({"success": True, "msg": result})
    else:
        return jsonify({"success": False, "msg": "等待树莓派回复超时"}), 504

# ==================
# 测试接口
# ==================

@app.route('/api/cheshi', methods=['GET'])
def gongneng():
    # 只发消息，不连接！
    client.publish("test/cheshi", "我发消息啦！")
    print("发送成功")
    
    # 必须 return！
    return {"success": True, "msg": "发送成功"}



if __name__ == '__main__':
   app.run(debug=True, host='0.0.0.0',port=8000)
