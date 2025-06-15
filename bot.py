# main.py
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from openai import OpenAI
from keep_alive import keep_alive
import base64
import json
import os

# ========== CONFIG ==========
TELEGRAM_TOKEN = "6367532329:AAGJh1RnIa-UZGBUdzKHTy3lyKnB81NdqjM"
OPENAI_API_KEY = "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"
client = OpenAI(api_key=OPENAI_API_KEY)

# ========== GIẢI MÃ ==========
def is_base64(s):
    try:
        return base64.b64encode(base64.b64decode(s)).decode() == s
    except:
        return False

def is_hex(s):
    try:
        bytes.fromhex(s)
        return True
    except:
        return False

def try_json(s):
    try:
        return json.loads(s)
    except:
        return None

def decode_languagemap(encoded_str):
    decoded_str = ""
    parsed_data = None

    if is_base64(encoded_str):
        try:
            decoded_str = base64.b64decode(encoded_str).decode('utf-8')
        except Exception:
            return "❌ Lỗi giải mã Base64.", None
    elif is_hex(encoded_str):
        try:
            decoded_str = bytes.fromhex(encoded_str).decode('utf-8')
        except Exception:
            return "❌ Lỗi giải mã Hex.", None
    else:
        decoded_str = encoded_str

    if decoded_str.startswith("languagemap:"):
        decoded_str = decoded_str[len("languagemap:"):].strip()

    parsed_data = try_json(decoded_str)
    if parsed_data:
        return (
            f"✅ Giải mã thành công!\n\n<pre>{json.dumps(parsed_data, indent=2, ensure_ascii=False)}</pre>",
            parsed_data
        )
    else:
        return f"📄 Chuỗi giải mã:\n<pre>{decoded_str}</pre>", None

# ========== CHATGPT ==========
async def ask_chatgpt(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"❌ Lỗi ChatGPT: {str(e)}"

# ========== TỰ ĐỘNG TRẢ LỜI ==========
PREDEFINED_RESPONSES = {
    "xin chào": "Chào bạn! Tôi là bot trợ lý. Hãy gửi chuỗi mã hoá hoặc câu hỏi cần giải đáp.",
    "help": "Bạn có thể gửi chuỗi mã hoá để giải mã, hoặc đặt câu hỏi để hỏi AI (ChatGPT).",
    "ai là gì": "AI là trí tuệ nhân tạo (Artificial Intelligence). Tôi sử dụng AI để giúp bạn!"
}

def check_predefined_response(text):
    key = text.lower().strip()
    return PREDEFINED_RESPONSES.get(key, None)

# ========== TELEGRAM HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Gửi tôi chuỗi mã hóa để giải mã, hoặc đặt câu hỏi để tôi hỏi AI!")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    predefined = check_predefined_response(text)
    if predefined:
        await update.message.reply_text(predefined)
        return

    result, parsed = decode_languagemap(text)

    if parsed:
        await update.message.reply_text(result, parse_mode='HTML')
        with open("decoded.json", "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        await update.message.reply_document(InputFile("decoded.json"))
        os.remove("decoded.json")
    else:
        await update.message.reply_text("🤖 Đang hỏi ChatGPT...")
        reply = await ask_chatgpt(text)
        await update.message.reply_text(reply)

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.document
    if file.mime_type not in ['application/json', 'text/plain']:
        await update.message.reply_text("⚠️ Chỉ hỗ trợ file .json hoặc .txt")
        return

    file_obj = await file.get_file()
    temp_path = await file_obj.download_to_drive()

    with open(temp_path, 'r', encoding='utf-8') as f:
        content = f.read()

    result, parsed = decode_languagemap(content)
    await update.message.reply_text(result, parse_mode='HTML')

    if parsed:
        with open("decoded.json", "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=2, ensure_ascii=False)
        await update.message.reply_document(InputFile("decoded.json"))
        os.remove("decoded.json")

    os.remove(temp_path)

# ========== MAIN ==========
if __name__ == "__main__":
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("🤖 Bot đang chạy...")
    app.run_polling()
