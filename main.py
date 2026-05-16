import os
import re
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = FastAPI()

# 從環境變數取得 LINE 的金鑰
# 注意：Messaging API 需要 Channel Secret 來驗證訊息安全性
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 全局變數：用來暫存你設定的倒數目標（Render 免費版重啟時會恢復預設值）
current_target = {
    "title": "暑假",
    "date": "2026-07-01"
}

def get_countdown_message():
    """計算倒數計時並組合文字"""
    tz_taiwan = timezone(timedelta(hours=8))
    today = datetime.now(tz_taiwan).date()
    
    try:
        target_date = datetime.strptime(current_target["date"], "%Y-%m-%d").replace(tzinfo=tz_taiwan).date()
    except ValueError:
        return "❌ 系統內的日期格式錯誤。"
        
    days_left = (target_date - today).days
    
    if days_left > 0:
        return f"距離 【{current_target['title']}】 還有 🔥 {days_left} 天 🔥"
    elif days_left == 0:
        return f"🎉🎉 哇！今天就是 【{current_target['title']}】 的日子囉！祝你一切順利！ 🎉🎉"
    else:
        return f"【{current_target['title']}】 已經過去 {-days_left} 天囉！期待下一個目標吧！"

@app.post("/callback")
async def callback(request: Request):
    """LINE Webhook 的主要接收端點"""
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Signature")
        
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid Signature")
        
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """當使用者傳送文字訊息時會觸發這個函式"""
    global current_target
    user_text = event.message.text.strip()
    reply_text = ""
    
    # 檢查是否為修改指令。格式：設定 [名稱] [YYYY-MM-DD]
    # 範例：設定 跨年 2026-12-31
    match = re.match(r"^設定\s+(.+)\s+(\d{4}-\d{2}-\d{2})$", user_text)
    
    if match:
        new_title = match.group(1)
        new_date_str = match.group(2)
        
        try:
            # 測試日期格式是否正確
            datetime.strptime(new_date_str, "%Y-%m-%d")
            current_target["title"] = new_title
            current_target["date"] = new_date_str
            reply_text = f"✅ 設定成功！已將目標更新為：\n【{new_title}】\n日期：{new_date_str}"
        except ValueError:
            reply_text = "❌ 日期格式錯誤！請使用 YYYY-MM-DD 格式（例如：2026-07-01）。"
            
    elif user_text == "查詢" or user_text == "倒數":
        countdown_content = get_countdown_message()
        reply_text = f"📌 目前倒數狀態：\n\n{countdown_content}"
        
    else:
        # 如果輸入其他東西，自動回應提示與目前的倒數狀態
        countdown_content = get_countdown_message()
        reply_text = (
            f"🤖 你好！使用者。\n\n"
            f"📌 目前目標：{countdown_content}\n\n"
            f"💡 想要修改目標嗎？請輸入：\n"
            f"`設定 名稱 YYYY-MM-DD`\n"
            f"(例如：設定 畢業 2026-06-20)"
        )

    # 透過 LINE API 回覆訊息給使用者
    with ApiClient(configuration) as api_client:
        messaging_api = MessagingApi(api_client)
        messaging_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

if __name__ == "__main__":
    import uvicorn
    # 本地測試時執行
    uvicorn.run(app, host="0.0.0.0", port=8000)
