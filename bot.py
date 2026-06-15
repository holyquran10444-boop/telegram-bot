import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8797984674:AAG6A0mnr8COBny1_J6MS7CjraFj8kuQkzc"
ADMIN_ID = 605635405

waiting_users = {}
active_exchanges = {}
user_warnings = {}
banned_users = set()
user_stats = {}
all_users = set()

logging.basicConfig(level=logging.INFO)

def get_stars(rating):
    if rating >= 4.5:
        return "⭐⭐⭐⭐⭐"
    elif rating >= 3.5:
        return "⭐⭐⭐⭐"
    elif rating >= 2.5:
        return "⭐⭐⭐"
    elif rating >= 1.5:
        return "⭐⭐"
    else:
        return "⭐"

def get_user_stats(user_id):
    if user_id not in user_stats:
        user_stats[user_id] = {
            "completed": 0,
            "total_rating": 0,
            "rating_count": 0
        }
    return user_stats[user_id]

def get_rating(user_id):
    stats = get_user_stats(user_id)
    if stats["rating_count"] == 0:
        return 5.0
    return round(stats["total_rating"] / stats["rating_count"], 1)

def get_profile_text(user_id, name, username):
    stats = get_user_stats(user_id)
    rating = get_rating(user_id)
    stars = get_stars(rating)
    completed = stats["completed"]
    return (
        f"👤 الاسم: {name}\n"
        f"💬 يوزره: {username}\n"
        f"{stars}\n"
        f"✅ تبادلات ناجحة: {completed}\n"
    )

def main_keyboard():
    waiting_count = len(waiting_users)
    waiting_text = f"🟢 منتظرون الآن: {waiting_count}" if waiting_count > 0 else "🔴 لا يوجد منتظرون الآن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ابدأ التبادل", callback_data="start_exchange")],
        [InlineKeyboardButton("📊 ملفي الشخصي", callback_data="profile")],
        [InlineKeyboardButton("📢 شارك البوت مع أصدقائك", url="https://t.me/share/url?url=https://t.me/LinksSwap_bot&text=بوت تبادل الروابط 🎁")],
        [InlineKeyboardButton(waiting_text, callback_data="waiting_count")],
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ابدأ تبادل جديد", callback_data="back_start")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    all_users.add(user_id)
    if user_id in banned_users:
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
        return
    get_user_stats(user_id)
    await update.message.reply_text(
        "👋 مرحباً في بوت تبادل الروابط!\n\n"
        "🎁 تبادل روابط Temu وShein ونعناع مع أشخاص موثوقين!\n\n"
        "اختر من القائمة:",
        reply_markup=main_keyboard()
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"👥 عدد المستخدمين: {len(all_users)}\n"
        f"🚫 محظورون: {len(banned_users)}\n"
        f"⏳ في الانتظار: {len(waiting_users)}\n"
        f"🔄 تبادلات نشطة: {len(active_exchanges) // 2}"
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "waiting_count":
        waiting_count = len(waiting_users)
        await query.answer(
            f"🟢 يوجد {waiting_count} شخص ينتظر الآن!" if waiting_count > 0 else "🔴 لا يوجد أحد ينتظر الآن",
            show_alert=True
        )

    elif query.data == "back_start":
        context.user_data.clear()
        waiting_users.pop(user_id, None)
        await query.edit_message_text(
            "👋 اختر من القائمة:",
            reply_markup=main_keyboard()
        )

    elif query.data == "start_exchange":
        context.user_data["mode"] = "waiting_link"
        await query.edit_message_text(
            "🔗 أرسل رابطك الآن وسنجد لك شريكاً تلقائياً!"
        )

    elif query.data == "profile":
        stats_data = get_user_stats(user_id)
        rating = get_rating(user_id)
        stars = get_stars(rating)
        warnings = user_warnings.get(user_id, 0)
        await query.edit_message_text(
            f"📊 ملفك الشخصي:\n\n"
            f"{stars}\n"
            f"✅ تبادلات ناجحة: {stats_data['completed']}\n"
            f"🌟 تقييمك: {rating}/5\n"
            f"⚠️ تحذيرات: {warnings}/2",
            reply_markup=back_keyboard()
        )

    elif query.data.startswith("done_"):
        pid = int(query.data.split("_")[1])
        stats_data = get_user_stats(user_id)
        stats_data["completed"] += 1
        active_exchanges.pop(user_id, None)
        rating_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_5_{pid}"),
                InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate_4_{pid}"),
            ],
            [
                InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate_3_{pid}"),
                InlineKeyboardButton("⭐⭐", callback_data=f"rate_2_{pid}"),
            ],
            [InlineKeyboardButton("⭐", callback_data=f"rate_1_{pid}")]
        ])
        await query.edit_message_text(
            "✅ تم تسجيل إتمامك!\n\nكيف تقيم شريكك؟",
            reply_markup=rating_keyboard
        )
        try:
            await context.bot.send_message(pid, "✅ شريكك أكد إتمام التبادل! شكراً لك 🎉")
        except Exception:
            pass

    elif query.data.startswith("rate_"):
        parts = query.data.split("_")
        rating_value = int(parts[1])
        pid = int(parts[2])
        pstats = get_user_stats(pid)
        pstats["total_rating"] += rating_value
        pstats["rating_count"] += 1
        await query.edit_message_text(
            f"✅ تم تسجيل تقييمك!\nأعطيت {'⭐' * rating_value}\n\nشكراً لك! 🎉",
            reply_markup=back_keyboard()
        )

    elif query.data.startswith("report_"):
        pid = int(query.data.split("_")[1])
        w = user_warnings.get(pid, 0) + 1
        user_warnings[pid] = w
        pstats = get_user_stats(pid)
        pstats["total_rating"] += 1
        pstats["rating_count"] += 1
        if w >= 2:
            banned_users.add(pid)
            msg = "🚫 تم حظرك نهائياً بسبب عدم إتمام التبادل!"
        else:
            msg = "⚠️ تحذير: أتمم التبادل أو ستُحظر في المرة القادمة!"
        try:
            await context.bot.send_message(pid, msg)
        except Exception:
            pass
        await query.edit_message_text(
            "✅ تم الإبلاغ. سيتم اتخاذ الإجراء اللازم.",
            reply_markup=back_keyboard()
        )

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    user = update.effective_user
    all_users.add(user_id)

    if user_id in banned_users:
        await update.message.reply_text("🚫 أنت محظور.")
        return

    if context.user_data.get("mode") == "waiting_link":
        if not text.startswith("http"):
            await update.message.reply_text("❌ أرسل رابطاً صحيحاً يبدأ بـ http")
            return

        username = f"@{user.username}" if user.username else "لا يوجد يوزر"

        waiting_users[user_id] = {
            "link": text,
            "name": user.first_name,
            "username": username,
            "time": datetime.now()
        }
        context.user_data["mode"] = "waiting"

        partner_id = next(
            (uid for uid in waiting_users if uid != user_id),
            None
        )

        if partner_id:
            pdata = waiting_users.pop(partner_id)
            waiting_users.pop(user_id, None)
            active_exchanges[user_id] = partner_id
            active_exchanges[partner_id] = user_id

            p_profile = get_profile_text(partner_id, pdata["name"], pdata["username"])
            my_profile = get_profile_text(user_id, user.first_name, username)

            kb1 = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ أكملت التبادل", callback_data=f"done_{partner_id}"),
                InlineKeyboardButton("🚨 إبلاغ", callback_data=f"report_{partner_id}")
            ]])
            kb2 = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ أكملت التبادل", callback_data=f"done_{user_id}"),
                InlineKeyboardButton("🚨 إبلاغ", callback_data=f"report_{user_id}")
            ]])

            await update.message.reply_text(
                f"🎉 وجدنا لك شريكاً!\n\n"
                f"{p_profile}\n"
                f"📌 اتفقا وتبادلا الروابط في الخاص بمصداقية!\n"
                f"بعد التبادل اضغط ✅",
                reply_markup=kb1
            )
            await context.bot.send_message(
                partner_id,
                f"🎉 وجدنا لك شريكاً!\n\n"
                f"{my_profile}\n"
                f"📌 اتفقا وتبادلا الروابط في الخاص بمصداقية!\n"
                f"بعد التبادل اضغط ✅",
                reply_markup=kb2
            )
        else:
            await update.message.reply_text(
                "⏳ تم حفظ رابطك!\n\n"
                "🟢 حالتك: نشط\n"
                "سنخبرك فوراً عند وجود شريك! 🔔",
                reply_markup=back_keyboard()
            )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
```
