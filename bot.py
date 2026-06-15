import logging
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8797984674:AAG6A0mnr8COBny1_J6MS7CjraFj8kuQkzc"
ADMIN_ID = 605635405

# ─── البيانات في الذاكرة ──────────────────────────────────────────────────────
waiting_users    = {}   # user_id → {"name", "username", "time"}
active_exchanges = {}   # user_id → partner_id
user_warnings    = {}   # user_id → int
banned_users     = set()
user_stats       = {}   # user_id → {"completed", "total_rating", "rating_count", "joined"}
all_users        = set()
pair_history     = {}   # frozenset({id1,id2}) → date

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ─── مساعدات ──────────────────────────────────────────────────────────────────

def get_user_stats(user_id: int) -> dict:
    if user_id not in user_stats:
        user_stats[user_id] = {
            "completed": 0,
            "total_rating": 0,
            "rating_count": 0,
            "joined": date.today().isoformat()
        }
    return user_stats[user_id]

def get_rating(user_id: int) -> float:
    s = get_user_stats(user_id)
    return round(s["total_rating"] / s["rating_count"], 1) if s["rating_count"] else 5.0

def get_stars(rating: float) -> str:
    full = round(rating)
    return "⭐" * full if full > 0 else "☆"

def met_today(uid1: int, uid2: int) -> bool:
    key = frozenset({uid1, uid2})
    return pair_history.get(key) == date.today()

def record_meeting(uid1: int, uid2: int):
    pair_history[frozenset({uid1, uid2})] = date.today()

def is_banned(user_id: int) -> bool:
    return user_id in banned_users

def users_today() -> int:
    today = date.today().isoformat()
    return sum(1 for s in user_stats.values() if s.get("joined") == today)

def total_completed() -> int:
    return sum(s["completed"] for s in user_stats.values())

def profile_card(user_id: int, name: str, username: str) -> str:
    s      = get_user_stats(user_id)
    rating = get_rating(user_id)
    stars  = get_stars(rating)
    return (
        f"👤 الاسم   : {name}\n"
        f"💬 اليوزر  : {username}\n"
        f"{stars}  ({rating}/5)\n"
        f"✅ تبادلات ناجحة: {s['completed']}"
    )

# ─── لوحات المفاتيح ───────────────────────────────────────────────────────────

def main_keyboard():
    count  = len(waiting_users)
    status = f"🟢 ينتظر {count} شخص الآن" if count else "🔴 لا يوجد منتظرون الآن"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 ابدأ تبادل الروابط", callback_data="find_partner")],
        [InlineKeyboardButton("📊 ملفي الشخصي",        callback_data="profile")],
        [InlineKeyboardButton(status,                   callback_data="waiting_info")],
        [InlineKeyboardButton("📢 شارك البوت",
            url="https://t.me/share/url?url=https://t.me/LinksSwap_bot&text=بوت تبادل الروابط 🎁")],
    ])

def search_again_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 بحث عن شريك جديد", callback_data="find_partner")],
        [InlineKeyboardButton("🏠 الرئيسية",          callback_data="home")],
    ])

def exchange_keyboard(partner_id: int):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ أتممت التبادل", callback_data=f"done_{partner_id}"),
        InlineKeyboardButton("🔄 شريك آخر",      callback_data="find_partner"),
        InlineKeyboardButton("🚨 إبلاغ",         callback_data=f"report_{partner_id}"),
    ]])

def rating_keyboard(partner_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_5_{partner_id}"),
            InlineKeyboardButton("⭐⭐⭐⭐",   callback_data=f"rate_4_{partner_id}"),
        ],
        [
            InlineKeyboardButton("⭐⭐⭐",     callback_data=f"rate_3_{partner_id}"),
            InlineKeyboardButton("⭐⭐",       callback_data=f"rate_2_{partner_id}"),
        ],
        [InlineKeyboardButton("⭐",           callback_data=f"rate_1_{partner_id}")],
    ])

# ─── البحث عن شريك ────────────────────────────────────────────────────────────

async def do_find_partner(user_id: int, user_obj, context, edit_msg=None):
    username = f"@{user_obj.username}" if user_obj.username else "بدون يوزر"
    name     = user_obj.first_name or "مستخدم"

    waiting_users.pop(user_id, None)

    partner_id = next(
        (uid for uid in list(waiting_users)
         if uid != user_id
         and not is_banned(uid)
         and not met_today(user_id, uid)),
        None
    )

    if partner_id:
        pdata = waiting_users.pop(partner_id)
        active_exchanges[user_id]    = partner_id
        active_exchanges[partner_id] = user_id
        record_meeting(user_id, partner_id)

        p_card  = profile_card(partner_id, pdata["name"], pdata["username"])
        my_card = profile_card(user_id, name, username)

        intro = (
            "🎉 وجدنا لك شريكاً للتبادل!\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "{card}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "📌 تواصلا في الخاص وتبادلا الروابط.\n"
            "🤝 كونوا صادقين ومحترمين مع بعضكم.\n"
            "بعد الانتهاء اضغط ✅ أو ابحث عن شريك آخر 🔄"
        )

        if edit_msg:
            await edit_msg.edit_text(intro.format(card=p_card),
                                     reply_markup=exchange_keyboard(partner_id))
        else:
            await context.bot.send_message(user_id, intro.format(card=p_card),
                                           reply_markup=exchange_keyboard(partner_id))

        await context.bot.send_message(partner_id, intro.format(card=my_card),
                                       reply_markup=exchange_keyboard(user_id))
    else:
        waiting_users[user_id] = {"name": name, "username": username, "time": datetime.now()}
        wait_text = (
            "⏳ أنت في قائمة الانتظار الآن...\n\n"
            f"🟢 عدد المنتظرين: {len(waiting_users)}\n\n"
            "سنُعلمك فوراً عند وجود شريك! 🔔\n"
            "يمكنك الضغط على 🔄 في أي وقت للتحديث."
        )
        if edit_msg:
            await edit_msg.edit_text(wait_text, reply_markup=search_again_keyboard())
        else:
            await context.bot.send_message(user_id, wait_text,
                                           reply_markup=search_again_keyboard())

# ─── المعالجات ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    get_user_stats(user.id)

    if is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور من استخدام البوت.")
        return

    await update.message.reply_text(
        "👋 أهلاً بك في بوت تبادل الروابط!\n\n"
        "🔄 اضغط الزر أدناه لتبادل الروابط مع شريك موثوق.",
        reply_markup=main_keyboard()
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_text(
        f"📊 إحصائيات البوت:\n\n"
        f"👥 إجمالي المستخدمين  : {len(all_users)}\n"
        f"📅 انضموا اليوم       : {users_today()}\n"
        f"🚫 محظورون            : {len(banned_users)}\n"
        f"⏳ في الانتظار        : {len(waiting_users)}\n"
        f"🔄 تبادلات نشطة       : {len(active_exchanges) // 2}\n"
        f"✅ تبادلات ناجحة كلياً : {total_completed()}"
    )

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("الاستخدام: /unban <user_id>")
        return
    uid = int(args[0])
    banned_users.discard(uid)
    user_warnings[uid] = 0
    await update.message.reply_text(f"✅ تم رفع الحظر عن {uid}")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("الاستخدام: /broadcast <الرسالة>")
        return
    sent, failed = 0, 0
    for uid in list(all_users):
        try:
            await context.bot.send_message(uid, f"📢 {text}")
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ أُرسلت إلى {sent} مستخدم.\n❌ فشل: {failed}")

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user    = query.from_user
    user_id = user.id

    all_users.add(user_id)
    get_user_stats(user_id)

    if is_banned(user_id):
        await query.answer("🚫 أنت محظور.", show_alert=True)
        return

    if query.data == "home":
        waiting_users.pop(user_id, None)
        await query.edit_message_text("🏠 القائمة الرئيسية:", reply_markup=main_keyboard())

    elif query.data == "waiting_info":
        c = len(waiting_users)
        await query.answer(
            f"🟢 يوجد {c} شخص ينتظر الآن!" if c else "🔴 لا يوجد أحد ينتظر الآن",
            show_alert=True
        )

    elif query.data == "profile":
        s        = get_user_stats(user_id)
        rating   = get_rating(user_id)
        stars    = get_stars(rating)
        warnings = user_warnings.get(user_id, 0)
        await query.edit_message_text(
            f"📊 ملفك الشخصي:\n\n"
            f"{stars}  ({rating}/5)\n"
            f"✅ تبادلات ناجحة : {s['completed']}\n"
            f"⚠️ تحذيرات       : {warnings}/2\n"
            f"📅 تاريخ الانضمام: {s['joined']}",
            reply_markup=search_again_keyboard()
        )

    elif query.data == "find_partner":
        active_exchanges.pop(user_id, None)
        await do_find_partner(user_id, user, context, edit_msg=query.message)

    elif query.data.startswith("done_"):
        partner_id = int(query.data.split("_")[1])
        get_user_stats(user_id)["completed"] += 1
        active_exchanges.pop(user_id, None)
        await query.edit_message_text(
            "✅ أحسنت! تم تسجيل إتمامك.\n\nكيف تقيّم شريكك؟",
            reply_markup=rating_keyboard(partner_id)
        )
        try:
            await context.bot.send_message(
                partner_id,
                "✅ شريكك أكد إتمام التبادل! شكراً لك 🎉",
                reply_markup=search_again_keyboard()
            )
        except Exception:
            pass

    elif query.data.startswith("rate_"):
        _, val, pid = query.data.split("_")
        val, pid = int(val), int(pid)
        ps = get_user_stats(pid)
        ps["total_rating"] += val
        ps["rating_count"] += 1
        await query.edit_message_text(
            f"✅ تم تسجيل تقييمك: {'⭐' * val}\n\nشكراً لك! 🎉",
            reply_markup=search_again_keyboard()
        )

    elif query.data.startswith("report_"):
        partner_id = int(query.data.split("_")[1])
        w = user_warnings.get(partner_id, 0) + 1
        user_warnings[partner_id] = w
        ps = get_user_stats(partner_id)
        ps["total_rating"] += 1
        ps["rating_count"] += 1
        if w >= 2:
            banned_users.add(partner_id)
            msg_text = "🚫 تم حظرك نهائياً بسبب عدم إتمام التبادل!"
        else:
            msg_text = "⚠️ تحذير: أتمم التبادل وإلا ستُحظر في المرة القادمة!"
        try:
            await context.bot.send_message(partner_id, msg_text)
        except Exception:
            pass
        active_exchanges.pop(user_id, None)
        await query.edit_message_text(
            "✅ تم الإبلاغ. سيتم اتخاذ الإجراء اللازم.",
            reply_markup=search_again_keyboard()
        )

async def msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    all_users.add(user.id)
    get_user_stats(user.id)
    if is_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور.")
        return
    await update.message.reply_text("اختر من القائمة:", reply_markup=main_keyboard())

# ─── التشغيل ──────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("stats",     stats_cmd))
    app.add_handler(CommandHandler("unban",     unban_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
