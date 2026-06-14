

```python
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8797984674:AAG6A0mnr8COBny1_J6MS7CjraFj8kuQkzc"

waiting_users = {}
active_exchanges = {}
user_warnings = {}
banned_users = set()

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text("🚫 أنت محظور.")
        return
    keyboard = [
        [InlineKeyboardButton("🔄 تبادل تلقائي", callback_data="auto")],
        [InlineKeyboardButton("📊 حالتي", callback_data="status")],
    ]
    await update.message.reply_text(
        "👋 مرحباً في بوت تبادل الروابط!\nاختر:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "auto":
        context.user_data["mode"] = "auto"
        await query.edit_message_text("🔗 أرسل رابطك الآن:")
    elif query.data == "status":
        w = user_warnings.get(user_id, 0)
        await query.edit_message_text(f"⚠️ تحذيرات: {w}/2")
    elif query.data.startswith("done_"):
        pid = int(query.data.split("_")[1])
        await query.edit_message_text("✅ شكراً! تم تسجيل إتمامك.")
        active_exchanges.pop(user_id, None)
        try:
            await context.bot.send_message(pid, "✅ شريكك أكد إتمام التبادل!")
        except Exception:
            pass
    elif query.data.startswith("report_"):
        pid = int(query.data.split("_")[1])
        w = user_warnings.get(pid, 0) + 1
        user_warnings[pid] = w
        if w >= 2:
            banned_users.add(pid)
            msg = "🚫 تم حظرك بسبب عدم التبادل!"
        else:
            msg = "⚠️ تحذير: أتمم التبادل أو ستُحظر!"
        try:
            await context.bot.send_message(pid, msg)
        except Exception:
            pass
        await query.edit_message_text("✅ تم الإبلاغ.")

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    if user_id in banned_users:
        await update.message.reply_text("🚫 أنت محظور.")
        return
    if context.user_data.get("mode") == "auto":
        if not text.startswith("http"):
            await update.message.reply_text("❌ أرسل رابطاً صحيحاً يبدأ بـ http")
            return
        waiting_users[user_id] = {"link": text, "name": update.effective_user.first_name}
        context.user_data["mode"] = "waiting"
        partner_id = next((uid for uid in waiting_users if uid != user_id), None)
        if partner_id:
            pdata = waiting_users.pop(partner_id)
            waiting_users.pop(user_id, None)
            active_exchanges[user_id] = partner_id
            active_exchanges[partner_id] = user_id
            kb1 = [[InlineKeyboardButton("✅ أكملت", callback_data=f"done_{partner_id}"), InlineKeyboardButton("🚨 إبلاغ", callback_data=f"report_{partner_id}")]]
            kb2 = [[InlineKeyboardButton("✅ أكملت", callback_data=f"done_{user_id}"), InlineKeyboardButton("🚨 إبلاغ", callback_data=f"report_{user_id}")]]
            await update.message.reply_text(
                f"🎉 وجدنا شريكاً!\n👤 {pdata['name']}\n🔗 {pdata['link']}",
                reply_markup=InlineKeyboardMarkup(kb1)
            )
            await context.bot.send_message(
                partner_id,
                f"🎉 وجدنا شريكاً!\n👤 {update.effective_user.first_name}\n🔗 {text}",
                reply_markup=InlineKeyboardMarkup(kb2)
            )
        else:
            await update.message.reply_text("⏳ تم حفظ رابطك! ننتظر شريكاً...")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
```
