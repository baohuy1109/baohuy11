import os
import zipfile
import shutil
import subprocess
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive
from openai import OpenAI, AuthenticationError, OpenAIError

# ✅ Cấu hình bot
BOT_TOKEN = "6367532329:AAGJh1RnIa-UZGBUdzKHTy3lyKnB81NdqjM"
shared_openai_key = None
ADMIN_ID = 5736655322

# ✅ Theos
THEOS_PATH = "/home/ubuntu/theos"
THEOS_MAKE_PATH = f"{THEOS_PATH}/make"

# ✅ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Chào bạn! Mình là GPT-4 VIP Bot:\n\n"
                                    "• Hỏi đáp GPT-4 hoặc GPT-3.5\n"
                                    "• Build tweak iOS từ file .zip (Theos project)\n\n"
                                    "Gửi câu hỏi hoặc file `.zip` project của bạn!")

# ✅ /addkey – chỉ admin
async def add_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global shared_openai_key
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Bạn không có quyền sử dụng lệnh này.")
        return

    if not context.args:
        await update.message.reply_text("⚠️ Dùng đúng cú pháp: `/addkey sk-xxx...`", parse_mode="Markdown")
        return

    key = context.args[0]
    try:
        client = OpenAI(api_key=key)
        models = [m.id for m in client.models.list()]
        if not any(m.startswith("gpt-4") or m.startswith("gpt-3.5") for m in models):
            await update.message.reply_text("❌ Key không có quyền truy cập GPT.")
            return
        shared_openai_key = key
        await update.message.reply_text("✅ Đã cập nhật key GPT dùng chung.")
    except AuthenticationError:
        await update.message.reply_text("❌ Key không hợp lệ hoặc hết hạn.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi khi kiểm tra key: {e}")

# ✅ Trả lời GPT-4 hoặc GPT-3.5 nếu fallback
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global shared_openai_key
    question = update.message.text
    await update.message.chat.send_action(action="typing")

    if not shared_openai_key:
        await update.message.reply_text("⚠️ Chưa có key GPT. Dùng /addkey để gán.")
        return

    try:
        client = OpenAI(api_key=shared_openai_key)

        # Ưu tiên GPT-4 → fallback sang GPT-3.5
        for model in ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": question}],
                    max_tokens=3000
                )
                answer = response.choices[0].message.content
                await update.message.reply_text(f"✅ {model} trả lời:\n\n{answer}")
                return
            except OpenAIError as e:
                if "model" in str(e).lower() or "not found" in str(e).lower():
                    continue  # thử model tiếp theo
                else:
                    raise e

        await update.message.reply_text("❌ Không model nào khả dụng với key này.")

    except AuthenticationError:
        await update.message.reply_text("❌ Key GPT không hợp lệ hoặc đã hết hạn.")
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi GPT: {e}")

# ✅ Build tweak từ project Theos
def build_theos_project(path: str) -> str:
    try:
        build_output = subprocess.check_output(
            ["make", "clean", "package"],
            cwd=path,
            stderr=subprocess.STDOUT,
            env=dict(os.environ, THEOS=THEOS_PATH, THEOS_MAKE_PATH=THEOS_MAKE_PATH)
        ).decode()

        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".deb"):
                    return os.path.join(root, file)

        return "BUILD_OK_NO_DEB"

    except subprocess.CalledProcessError as e:
        error_path = os.path.join(path, "build_error.txt")
        with open(error_path, "w") as f:
            f.write(e.output.decode())
        return error_path

# ✅ Xử lý file .zip Theos
async def handle_zip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_name = update.message.document.file_name
    zip_path = f"uploads/{file_name}"

    os.makedirs("uploads", exist_ok=True)
    await file.download_to_drive(zip_path)

    try:
        extract_dir = zip_path.replace(".zip", "")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        if not os.path.exists(os.path.join(extract_dir, "Makefile")):
            await update.message.reply_text("❌ Không tìm thấy Makefile. Có thể không phải project Theos.")
            return

        result = build_theos_project(extract_dir)

        if result.endswith(".deb"):
            await update.message.reply_text("✅ Build thành công! Dưới đây là file .deb của bạn:")
            await update.message.reply_document(document=open(result, "rb"))
        elif result.endswith(".txt"):
            await update.message.reply_text("❌ Build lỗi. Dưới đây là log lỗi:")
            await update.message.reply_document(document=open(result, "rb"))
        else:
            await update.message.reply_text("✅ Build xong nhưng không tìm thấy file .deb.")

    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi xử lý .zip: {e}")
    finally:
        os.remove(zip_path)
        shutil.rmtree(extract_dir, ignore_errors=True)

# ✅ Chạy bot
def main():
    keep_alive()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addkey", add_key))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ZIP, handle_zip))

    print("🤖 Bot GPT + Theos đã khởi động...")
    app.run_polling()

if __name__ == "__main__":
    main()
