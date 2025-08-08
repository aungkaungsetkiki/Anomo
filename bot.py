from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ApplicationHandlerStop
import asyncio
import re
import time
import logging
from datetime import datetime, timedelta
import os

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Data storage
paired_users = {}
all_users = set()
broadcast_group = {}
poll_data = {}
waiting_users = []
banned_users = set()
user_names = {}
custom_nicknames = {}
chat_counts = {}
group_message_counts = {}
vip_users = {}
exemption_counts = {}
nickname_changes = {}
last_reset = time.time()
text_styles = {}
custom_badges = {}
user_points = {}  # AnonP အတွက်
user_badges = {}  # ဆုတံဆိပ်များ
daily_message_counts = {}  # နေ့စဉ် Group မက်ဆေ့ချ်ရေအတွက်
last_daily_reset = {}  # နေ့စဉ် reset အချိန်
anonman_bonus_given = {}  # AnonMan Plan ဘောနပ်စ်ပေးခဲ့ပြီလား
first_time_users = set()  # ပထမဆုံး start လုပ်တဲ့ user များကို မှတ်တမ်းတင်ဖို့

# Offensive words list
OFFENSIVE_WORDS = [
    "fuck", "shit", "bitch", "damn", "asshole", "bastard", "cunt", "dick", "piss", "slut",
    "လီး", "ကိုမေကိုလိုး", "မအေလိုး", "ငါလိုးမသား", "လီးဘဲ", "နို့ပြ", "လော်ပြ",
    "လော်ကြီးတယ်", "မင်းမေလိုး", "ပူစီပြ", "မင်းအမေလိုး", "မင်းညီမငါ့ပေး",
    "ဖင်ယားနေတာလား", "မင်းကဆရာကြီးလား", "မင်းအဖေငါ", "သုတ်ကြောင်မ",
    "လော်ကြောင်မ", "စမူကောင်", "စမူကြောင်", "လီးတွေပြော", "သုတ်ကြောင်ကောင်",
    "ဖာသိမ်း", "သုတ်သားကောင်", "လူမဲ့", "သေချာလိုး", "ပေကြောင်", "လိုးကြောင်"
]

# Keyboards
admin_menu_keyboard = ReplyKeyboardMarkup([
    ['💬 Anonymous Chat', '📤 Anonymous Groups', '📤 Broadcast', '🚫 Ban User'],
    ['📋 View User List', '📋 Profile', '🆘 Help'],
    ['🎁 Gift AnonMan Plan', 'AnonP 🏆']
], resize_keyboard=True)

user_menu_keyboard = ReplyKeyboardMarkup([
    ['💬 Anonymous Chat', '📤 Anonymous Groups'],
    ['📋 Profile', '🆘 Help', 'AnonP 🏆']
], resize_keyboard=True)

chat_keyboard = ReplyKeyboardMarkup([
    ['🚪 End Chat', '📡 Send Status']
], resize_keyboard=True)

broadcast_keyboard = ReplyKeyboardMarkup([
    ['🚪 Leave', '📊 View Members']
], resize_keyboard=True)

poll_keyboard = ReplyKeyboardMarkup([
    ['💟 Yes', '💔 No', '/viewpoll'],
    ['/resetpoll']
], resize_keyboard=True)

ban_keyboard = ReplyKeyboardMarkup([
    ['✅ Confirm Ban', '❌ Cancel']
], resize_keyboard=True)

def escape_markdown(text):
    special_chars = r'_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def apply_text_style(text, style, username, is_anonman=False):
    username_escaped = escape_markdown(username)
    text_escaped = escape_markdown(text)
    badge = custom_badges.get(user_id, "🌟") if is_anonman else "🌟"
    if is_anonman:
        prefix = "🔥 "
    else:
        prefix = ""
    if style == "bold":
        return f"{prefix}{badge} **{username_escaped}**: **{text_escaped}**"
    elif style == "italic":
        return f"{prefix}{badge} *{username_escaped}*: *{text_escaped}*"
    return f"{prefix}{badge} {username_escaped}: {text_escaped}"

async def handle_error(update, context, error_msg):
    user_id = update.effective_user.id if update else "Unknown"
    if update and update.effective_user:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"❌ အမှားတစ်ခု ဖြစ်ပွားခဲ့ပါတယ်: {error_msg}. ကျေးဇူးပြု၍ နောက်တစ်ကြိမ် စမ်းကြည့်ပါ။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
    if user_id != ADMIN_ID:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚫 Error Occurred! User: {user_id}, Message: {error_msg}",
            reply_markup=admin_menu_keyboard
        )
    logger.error(f"Update {update} caused error {error_msg}")

async def error_handler(update, context):
    error_msg = str(context.error)
    await handle_error(update, context, error_msg)
    raise ApplicationHandlerStop

def reset_nickname_changes():
    global last_reset
    current_time = time.time()
    if current_time - last_reset >= 604800:
        nickname_changes.clear()
        last_reset = current_time

def contains_emoji(nickname):
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F700-\U0001F77F"
        u"\U0001F780-\U0001F7FF"
        u"\U0001F800-\U0001F8FF"
        u"\U0001F900-\U0001F9FF"
        u"\U0001FA00-\U0001FA6F"
        u"\U0001FA70-\U0001FAFF"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE)
    return bool(emoji_pattern.search(nickname))

async def start(update, context):
    user_id = update.effective_user.id
    user = update.effective_user
    first_name = user.first_name if user.first_name else ""
    last_name = user.last_name if user.last_name else ""
    user_names[user_id] = f"{first_name} {last_name}".strip() or "Anonymous"
    all_users.add(user_id)
    if user_id not in chat_counts:
        chat_counts[user_id] = 0
    if user_id not in group_message_counts:
        group_message_counts[user_id] = 0
    if user_id not in user_points:
        user_points[user_id] = 0
    if user_id not in user_badges:
        user_badges[user_id] = []
    if user_id not in daily_message_counts:
        daily_message_counts[user_id] = 0
    if user_id not in last_daily_reset:
        last_daily_reset[user_id] = datetime.now()
    if user_id not in anonman_bonus_given:
        anonman_bonus_given[user_id] = False
    if user_id not in first_time_users:
        first_time_users.add(user_id)
        vip_users[user_id] = "AnonMan Plan"  # 3-day free AnonMan Plan
        current_nick = custom_nicknames.get(user_id, user_names.get(user_id, "Anonymous"))
        custom_nicknames[user_id] = f"🎭 {current_nick}"
        await context.bot.send_message(
            chat_id=user_id,
            text=f"👋 ကြိုဆိုပါတယ် {first_name}! သင်သည် ပထမဆုံး start လုပ်သူဖြစ်ပြီး 3-day AnonMan Plan လေးကို လက်ခံရရှိပါတယ်! 💬 Anonymous Chat သို့မဟုတ် Anonymous Groups မှာ မက်ဆေ့ချ်ပို့ဖို့ အောက်က button တွေကို သုံးပါ။ 😊",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
    elif user_id not in chat_counts and user_id not in banned_users:
        await update.message.reply_text(
            f"👋 ကြိုဆိုပါတယ် {first_name}! 💬 Anonymous Chat သို့မဟုတ် Anonymous Groups မှာ မက်ဆေ့ချ်ပို့ဖို့ အောက်က button တွေကို သုံးပါ။ 😊",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        paired_users[user_id] = None
    elif user_id in banned_users:
        await update.message.reply_text(
            "❌ သင်သည် Anonymous Group မှ Ban ခံထားရပါသည်။",
            reply_markup=None
        )
    else:
        await update.message.reply_text(
            "🙌 သင်သည် ကြိုတင်စတင်ပြီးသား ဖြစ်ပါတယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )

async def join(update, context):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text(
            "❌ သင်သည် Ban ခံထားရပါသည်။ Anonymous Chat သုံးရန် မရပါ။",
            reply_markup=None
        )
        return
    if user_id in paired_users and paired_users[user_id] is not None:
        await update.message.reply_text(
            "❌ သင်သည် ချိတ်ဆက်ပြီးသားဖြစ်ပါတယ်။ 🚪 End Chat နှိပ်ပြီး နောက်တစ်ယောက်ရှာနိုင်ပါတယ်။",
            reply_markup=chat_keyboard
        )
        return
    if user_id in waiting_users:
        waiting_users.remove(user_id)
    
    if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
        waiting_users.insert(0, user_id)
    else:
        waiting_users.append(user_id)
    
    paired_users[user_id] = None
    chat_counts[user_id] += 1
    if len(waiting_users) >= 2:
        user1, user2 = waiting_users.pop(0), waiting_users.pop(0)
        paired_users[user1] = user2
        paired_users[user2] = user1
        await context.bot.send_message(chat_id=user1, text=f"🎉 Friend {custom_nicknames.get(user2, user_names[user2])} နဲ့ ချိတ်ဆက်ပြီးပါတယ်! 💬 စာပို့ပြီး စကားစမြည်ပြောနိုင်ပါတယ်။ 🌟", reply_markup=chat_keyboard)
        await context.bot.send_message(chat_id=user2, text=f"🎉 Friend {custom_nicknames.get(user1, user_names[user1])} နဲ့ ချိတ်ဆက်ပြီးပါတယ်! 💬 စာပို့ပြီး စကားစမြည်ပြောနိုင်ပါတယ်။ 🌟", reply_markup=chat_keyboard)
    else:
        await update.message.reply_text(
            "⏳ တခြားသူတစ်ဦးကို စောင့်နေပါတယ်... (တစ်ဖက်လူကလည်း 💬 Anonymous Chat နှိပ်ရပါမယ်။)",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )

async def end(update, context):
    user_id = update.effective_user.id
    if user_id in banned_users:
        await update.message.reply_text(
            "❌ သင်သည် Ban ခံထားရပါသည်။",
            reply_markup=None
        )
        return
    if user_id in paired_users and paired_users[user_id] is not None:
        partner_id = paired_users[user_id]
        paired_users[user_id] = None
        paired_users[partner_id] = None
        if user_id in waiting_users: waiting_users.remove(user_id)
        if partner_id in waiting_users: waiting_users.remove(partner_id)
        await context.bot.send_message(chat_id=user_id, text="👋 Chat ကို အဆုံးသတ်လိုက်ပါပြီ။ 💬 Anonymous Chat နဲ့ နောက်တစ်ယောက်ရှာပါ�။ 😊", reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard)
        await context.bot.send_message(chat_id=partner_id, text=f"👋 Friend {custom_nicknames.get(user_id, user_names[user_id])} က chat ကို အဆုံးသတ်လိုက်ပါပြီ။ 💬 Anonymous Chat နဲ့ နောက်တစ်ယောက်ရှာပါ။ 😊", reply_markup=admin_menu_keyboard if partner_id == ADMIN_ID else user_menu_keyboard)
    else:
        await update.message.reply_text("❌ သင်သည် မည်သူနှင့်မျှ ချိတ်ဆက်မထားပါ။ 💬 Anonymous Chat နဲ့ စတင်ပါ။", reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard)

async def help(update, context):
    user_id = update.effective_user.id
    help_text = (
        "📖 **Help Menu**\n\n"
        "💬 Anonymous Chat - တခြားသူတစ်ဦးနဲ့ ချိတ်ဆက်ပါ\n"
        "🚪 End Chat - လက်ရှိ chat ကို အဆုံးသတ်ပါ\n"
        "📡 Send Status - သင့်လက်ရှိ Chat အခြေအနေကို စစ်ကြည့်ပါ\n"
        "📤 Anonymous Groups - အားလုံးထံသို့ မက်ဆေ့ချ်ပို့ပါ\n"
        "📊 View Members - Anonymous Group ထဲက အဖွဲ့ဝင်များကို ကြည့်ပါ\n"
        "⚠️ ရိုင်းစိုင်းတဲ့ စကားလုံးများသုံးရင် Auto-Ban ခံရမှာဖြစ်ပါတယ်။\n"
        "📋 Profile - သင့်ရဲ့ profile ကို ကြည့်ပါ\n"
        "AnonP 🏆 - သင့်ရဲ့ AnonP ကို ကြည့်ပြီး Prize လဲလှယ်ပါ\n"
        "/report - မသင့်လျော်တဲ့ message ကို reply ပြီး report လုပ်ပါ\n"
    )
    if user_id == ADMIN_ID:
        help_text += (
            "📤 Broadcast - အကုန်လုံးထံသို့ မက်ဆေ့ချ်၊ ပုံ၊ လင့်ပို့ပါ\n"
            "📝 Create Poll - Anonymous Group ထဲမှာ Poll ဖန်တီးပါ\n"
            "/viewpoll - Poll ရလဒ်ကို ကြည့်ပါ\n"
            "/resetpoll - Poll ကို ပြန်စပါ\n"
            "🚫 Ban User - Anonymous Group ထဲက အသုံးပြုသူတစ်ဦးကို Ban လုပ်ပါ\n"
            "📋 View User List - အားလုံး User List ကို ကြည့်ပါ\n"
            "🎁 Gift AnonMan Plan - User တစ်ဦးကို AnonMan Plan ပေးပါ\n"
        )
    help_text += "🚪 Leave - Anonymous Group ကနေ ထွက်ပါ\nအကယ်၍ ပြဿနာရှိရင် Bot ကို /start ပြန်စတင်ကြည့်ပါ။"
    await update.message.reply_text(help_text, reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard)

async def check_offensive_message(message_text, user_id, context):
    if message_text:
        message_text_lower = message_text.lower()
        for word in OFFENSIVE_WORDS:
            if word.lower() in message_text_lower:
                if user_id not in vip_users or vip_users[user_id] != "AnonMan Plan":
                    banned_users.add(user_id)
                    if user_id in broadcast_group:
                        del broadcast_group[user_id]
                    if user_id in paired_users:
                        partner_id = paired_users[user_id]
                        if partner_id:
                            paired_users[partner_id] = None
                        paired_users[user_id] = None
                    if user_id in waiting_users:
                        waiting_users.remove(user_id)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="❌ ရိုင်းစိုင်းတဲ့ စကားလုံးသုံးမှုကြောင့် Auto-Ban ခံလိုက်ရပါပြီ။",
                        reply_markup=None
                    )
                    if user_id != ADMIN_ID:
                        await context.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=f"🚫 User {user_id} သည် ရိုင်းစိုင်းတဲ့ စကားလုံးသုံးမှုကြောင့် Auto-Ban ခံလိုက်ရပါတယ်။ Message: {message_text}",
                            reply_markup=admin_menu_keyboard
                        )
                    return True
                else:
                    if user_id not in exemption_counts:
                        exemption_counts[user_id] = 0
                    exemption_counts[user_id] += 1
                    remaining_exemptions = 3 - exemption_counts[user_id]
                    if remaining_exemptions > 0:
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=f"⚠️ ရိုင်းစိုင်းတဲ့ စကားလုံးသုံးခဲ့ပြီး AnonMan Plan ကြောင့် လွတ်မြောက်ခံရပါတယ်။ ကျန်ရှိသေးတဲ့ ကင်းလွတ်ခွင့်: {remaining_exemptions} ကြိမ်။",
                            reply_markup=user_menu_keyboard
                        )
                        return False
                    else:
                        banned_users.add(user_id)
                        if user_id in broadcast_group:
                            del broadcast_group[user_id]
                        if user_id in paired_users:
                            partner_id = paired_users[user_id]
                            if partner_id:
                                paired_users[partner_id] = None
                            paired_users[user_id] = None
                        if user_id in waiting_users:
                            waiting_users.remove(user_id)
                        del vip_users[user_id]
                        del exemption_counts[user_id]
                        await context.bot.send_message(
                            chat_id=user_id,
                            text="❌ ရိုင်းစိုင်းတဲ့ စကားလုံးသုံးမှုကြောင့် ကင်းလွတ်ခွင့် ၃ ကြိမ်ပြည့်သွားပြီး Auto-Ban ခံလိုက်ရပါပြီ။",
                            reply_markup=None
                        )
                        if user_id != ADMIN_ID:
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=f"🚫 User {user_id} သည် ရိုင်းစိုင်းတဲ့ စကားလုံးသုံးမှုကြောင့် Auto-Ban ခံလိုက်ရပါတယ်။ Message: {message_text}",
                                reply_markup=admin_menu_keyboard
                            )
                        return True
    return False

async def check_link_message(message_text, user_id, context):
    if message_text:
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|www\.[^\s]+'
        if re.search(url_pattern, message_text):
            banned_users.add(user_id)
            if user_id in broadcast_group:
                del broadcast_group[user_id]
            if user_id in paired_users:
                partner_id = paired_users[user_id]
                if partner_id:
                    paired_users[partner_id] = None
                paired_users[user_id] = None
            if user_id in waiting_users:
                waiting_users.remove(user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text="❌ Link ပို့မှုကြောင့် Auto-Ban ခံလိုက်ရပါပြီ။",
                reply_markup=None
            )
            if user_id != ADMIN_ID:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"🚫 User {user_id} သည် Link ပို့မှုကြောင့် Auto-Ban ခံလိုက်ရပါတယ်။ Message: {message_text}",
                    reply_markup=admin_menu_keyboard
                )
            return True
    return False

async def handle_message(update, context):
    global user_id
    user_id = update.effective_user.id
    message_text = update.message.text
    reply_to_message = update.message.reply_to_message

    if user_id in banned_users:
        await update.message.reply_text("❌ သင်သည် Ban ခံထားရပါသည်။", reply_markup=None)
        return

    # Daily reset check for message counts
    current_time = datetime.now()
    if user_id in last_daily_reset and (current_time - last_daily_reset[user_id]).days >= 1:
        daily_message_counts[user_id] = 0
        last_daily_reset[user_id] = current_time

    # Active User AnonP (based on days since last activity)
    last_active = last_daily_reset.get(user_id, datetime.now())
    days_active = (current_time - last_active).days + 1
    if days_active <= 7:
        if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
            active_points = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 8, 7: 10}.get(days_active, 0)
        else:
            active_points = min(days_active, 7)  # Normal User: 1 day = 1 AnonP, up to 7 AnonP
        user_points[user_id] = user_points.get(user_id, 0) + active_points
        last_daily_reset[user_id] = current_time  # Update last active time

    # AnonMan Plan ဘောနပ်စ် (ပထမဆုံး start လုပ်သူမှာ AnonP မပေးဘူး)
    if user_id in vip_users and vip_users[user_id] == "AnonMan Plan" and not anonman_bonus_given.get(user_id, False):
        if user_id not in first_time_users:  # ပထမဆုံး start လုပ်သူမဟုတ်ရင်ပဲ AnonP 30 ပေးမယ်
            user_points[user_id] = user_points.get(user_id, 0) + 30
            anonman_bonus_given[user_id] = True
            await context.bot.send_message(chat_id=user_id, text="🏆 AnonMan Plan ကြောင့် 30 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard if user_id in broadcast_group else user_menu_keyboard)

    if message_text == "💬 Anonymous Chat":
        await join(update, context)
        return
    elif message_text == "🚪 End Chat":
        await end(update, context)
        return
    elif message_text == "🆘 Help":
        await help(update, context)
        return
    elif message_text == "📡 Send Status":
        if user_id not in paired_users:
            await update.message.reply_text(
                "❌ သင်သည် မည်သူနှင့်မျှ ချိတ်ဆက်မထားပါ။ အရင် /start နှိပ်ပြီး စတင်ပါ။",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            return
        status = "သင်သည် မည်သူနှင့်မျှ ချိတ်ဆက်မထားပါ" if paired_users.get(user_id) is None else f"သင်သည် Friend {custom_nicknames.get(paired_users[user_id], user_names.get(paired_users[user_id], 'Anonymous'))} နှင့် ချိတ်ဆက်ထားပါတယ်"
        await update.message.reply_text(
            f"📡 **Your Status**\nStatus: {status}",
            reply_markup=chat_keyboard if paired_users.get(user_id) is not None else (admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard)
        )
        return
    elif message_text == "📤 Anonymous Groups":
        if user_id not in broadcast_group and user_id not in banned_users:
            broadcast_group[user_id] = custom_nicknames.get(user_id, user_names[user_id])
            await update.message.reply_text(
                "📤 သင်သည် Anonymous Group ထဲရောက်ပါတယ်။ မက်ဆေ့ချ်ရိုက်ထည့်ပြီး ပို့လိုက်ပါ (AnonMan Plan မရှိရင် စာလုံးရေ 50 အထိ၊ ရှိရင် 200 အထိပို့နိုင်ပါတယ်၊ Link ပို့ရင် Ban ဖြစ်ပါမယ်)။ AnonMan Plan ရှိရင် ပုံနဲ့ ဗီဒီယိုလည်း ပို့နိုင်ပါတယ်။",
                reply_markup=broadcast_keyboard
            )
        elif user_id in banned_users:
            await update.message.reply_text("❌ သင်သည် Ban ခံထားရပါသည်။", reply_markup=None)
        else:
            await update.message.reply_text(
                "📤 သင်သည် ကြိုတင်ရောက်နေပြီ။ မက်ဆေ့ချ်ရိုက်ထည့်ပြီး ပို့ပါ (AnonMan Plan မရှိရင် စာလုံးရေ 50 အထိ၊ ရှိရင် 200 အထိပို့နိုင်ပါတယ်၊ Link ပို့ရင် Ban ဖြစ်ပါမယ်)။ AnonMan Plan ရှိရင် ပုံနဲ့ ဗီဒီယိုလည်း ပို့နိုင်ပါတယ်။",
                reply_markup=broadcast_keyboard
            )
        return
    elif message_text == "📊 View Members" and user_id in broadcast_group:
        if broadcast_group:
            members = [f"{name}" for user, name in broadcast_group.items() if user not in banned_users]
            members_list = "\n".join(members)
            await update.message.reply_text(
                f"📊 **Group Members**\n{members_list}",
                reply_markup=broadcast_keyboard
            )
        else:
            await update.message.reply_text(
                "📊 **Group Members**\nအဖွဲ့ဝင်မရှိပါ။",
                reply_markup=broadcast_keyboard
            )
        return
    elif message_text == "📝 Create Poll" and user_id == ADMIN_ID and user_id in broadcast_group:
        if "question" in poll_data:
            await update.message.reply_text(
                "📝 လက်ရှိ Poll ရှိနေပါတယ်။ /resetpoll နဲ့ ရှင်းလိုက်ပြီး အသစ်ဖန်တီးပါ။",
                reply_markup=broadcast_keyboard
            )
        else:
            context.user_data["creating_poll"] = True
            await update.message.reply_text(
                "📝 Poll အတွက် မေးခွန်းရိုက်ထည့်ပါ (Yes/No ပုံစံ)။",
                reply_markup=broadcast_keyboard
            )
        return
    elif message_text == "📤 Broadcast" and user_id == ADMIN_ID:
        context.user_data["broadcasting"] = True
        await update.message.reply_text(
            "📤 Broadcast အတွက် မက်ဆေ့ချ်၊ ပုံ၊ လင့်ရိုက်ထည့်ပြီး ပို့ပါ။",
            reply_markup=admin_menu_keyboard
        )
        return
    elif message_text == "🚫 Ban User" and user_id == ADMIN_ID:
        context.user_data["banning_user"] = True
        await update.message.reply_text(
            "🚫 Ban လုပ်မယ့် user ID ရိုက်ထည့်ပါ (ဥပမာ: 123456789)။",
            reply_markup=admin_menu_keyboard
        )
        return
    elif message_text == "📋 View User List" and user_id == ADMIN_ID:
        if all_users:
            user_list = [f"{custom_nicknames.get(uid, user_names.get(uid, 'Anonymous'))} (ID: {uid})" for uid in all_users if uid not in banned_users]
            user_list_text = "\n".join(user_list)
            total_users = len(all_users) - len(banned_users)
            await update.message.reply_text(
                f"📋 **User List**\n{user_list_text}\n\nTotal Users: {total_users}",
                reply_markup=admin_menu_keyboard
            )
        else:
            await update.message.reply_text(
                "📋 **User List**\nသုံးပြုသူမရှိပါ။",
                reply_markup=admin_menu_keyboard
            )
        return
    elif message_text == "📋 Profile" and user_id not in banned_users:
        chat_count = chat_counts.get(user_id, 0)
        group_count = group_message_counts.get(user_id, 0)
        vip_status = vip_users.get(user_id, "None")
        points = user_points.get(user_id, 0)
        badges = ", ".join(user_badges.get(user_id, [])) or "None"
        badge = custom_badges.get(user_id, "🌟") if vip_status == "AnonMan Plan" else f"🌟 {vip_status}"
        display_nick = custom_nicknames.get(user_id, user_names.get(user_id, "Anonymous"))
        if user_id in vip_users and "AnonMan Plan" in vip_users[user_id]:
            display_nick = f"🎭 {display_nick}"
        keyboard = [
            [InlineKeyboardButton("Set Nickname", callback_data=f"setnickname_{user_id}")],
            [InlineKeyboardButton("Set Text Style", callback_data=f"settextstyle_{user_id}") if user_id in vip_users and vip_users[user_id] == "AnonMan Plan" else InlineKeyboardButton("Set Text Style", callback_data=f"notallowed_{user_id}")],
            [InlineKeyboardButton("Set Custom Badge", callback_data=f"setbadge_{user_id}") if user_id in vip_users and vip_users[user_id] == "AnonMan Plan" else InlineKeyboardButton("Set Custom Badge", callback_data=f"notallowed_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"📋 **Your Profile**\nName: {display_nick} {badge}\nID: {user_id}\nAnonymous Chats: {chat_count}\nGroup Messages: {group_count}\nPoints: {points}\nBadges: {badges}",
            reply_markup=reply_markup
        )
        return
    elif message_text == "AnonP 🏆":
        total_anonp = user_points.get(user_id, 0)
        keyboard = [
            [InlineKeyboardButton("3day AnonMan Plan: 3000AnonP", callback_data=f"prize_3day_{user_id}")],
            [InlineKeyboardButton("1wk AnonMan Plan: 5000AnonP", callback_data=f"prize_1wk_{user_id}")],
            [InlineKeyboardButton("1000 Bill: 1000AnonP", callback_data=f"prize_1000bill_{user_id}")],
            [InlineKeyboardButton("3000 Cash: 3000AnonP", callback_data=f"prize_3000cash_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🏆 **Your AnonP**\nTotal AnonP: {total_anonp}\n\nPrize တွေကို AnonP နဲ့ လဲနိုင်ပါတယ်။",
            reply_markup=reply_markup
        )
        return

    if context.user_data.get("setting_nickname", False) and user_id not in banned_users:
        nickname = message_text.strip()
        if contains_emoji(nickname):
            await update.message.reply_text(
                "❌ Nickname မှာ emoji မပါရပါ။ စာလုံးတွေပဲ ထည့်ပါ (ဥပမာ: CoolUser)",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            return
        if not nickname or len(nickname) > 20:
            await update.message.reply_text(
                "❌ Nickname ကို 20 လုံးထက်မပိုဘဲ ထည့်ပါ (ဥပမာ: CoolUser)",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            return
        custom_nicknames[user_id] = nickname
        if user_id in broadcast_group:
            broadcast_group[user_id] = nickname
        if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
            custom_nicknames[user_id] = f"🎭 {nickname}"
        await update.message.reply_text(
            f"✅ Nickname ကို {custom_nicknames[user_id]} အဖြစ် သတ်မှတ်လိုက်ပါတယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        del context.user_data["setting_nickname"]
        return
    elif context.user_data.get("setting_textstyle", False) and user_id not in banned_users:
        if user_id not in vip_users or vip_users[user_id] != "AnonMan Plan":
            await update.message.reply_text(
                "❌ သင်သည် AnonMan Plan မရှိလို့ Text Style ပြောင်းလို့မရပါ။",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            del context.user_data["setting_textstyle"]
            return
        style = message_text.strip().lower()
        if style not in ["bold", "italic", "none"]:
            await update.message.reply_text(
                "❌ Text Style ကို 'bold', 'italic', ဒါမှမဟုတ် 'none' ထည့်ပါ။",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            return
        text_styles[user_id] = style
        await update.message.reply_text(
            f"✅ Text Style ကို '{style}' အဖြစ် သတ်မှတ်လိုက်ပါတယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        del context.user_data["setting_textstyle"]
        return
    elif context.user_data.get("setting_badge", False) and user_id not in banned_users:
        if user_id not in vip_users or vip_users[user_id] != "AnonMan Plan":
            await update.message.reply_text(
                "❌ သင်သည် AnonMan Plan မရှိလို့ Custom Badge သတ်မှတ်လို့မရပါ။",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            del context.user_data["setting_badge"]
            return
        badge = message_text.strip()
        if not badge or len(badge) != 1 or not contains_emoji(badge):
            await update.message.reply_text(
                "❌ Custom Badge အဖြစ် emoji တစ်ခုထည့်ပါ (ဥပမာ: ⭐)။",
                reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
            )
            return
        custom_badges[user_id] = badge
        await update.message.reply_text(
            f"✅ Custom Badge ကို '{badge}' အဖြစ် သတ်မှတ်လိုက်ပါတယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        del context.user_data["setting_badge"]
        return
    elif message_text == "/report" and reply_to_message and user_id not in banned_users:
        reported_user_id = reply_to_message.from_user.id
        reported_message = reply_to_message.text or "No text (e.g., photo/voice)"
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🚨 Report Received!\nReported User: {custom_nicknames.get(reported_user_id, user_names.get(reported_user_id, 'Anonymous'))} (ID: {reported_user_id})\nReported by: {custom_nicknames.get(user_id, user_names[user_id])} (ID: {user_id})\nMessage: {reported_message}",
            reply_markup=admin_menu_keyboard
        )
        await update.message.reply_text(
            "✅ Report ပို့လိုက်ပါတယ်။ Admin က စစ်ဆေးပါမယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        return
    elif context.user_data.get("banning_user", False) and user_id == ADMIN_ID and message_text.isdigit():
        target_user_id = int(message_text)
        if target_user_id in broadcast_group:
            context.user_data["target_ban_id"] = target_user_id
            await update.message.reply_text(
                f"🚫 {target_user_id} ကို Ban လုပ်မယ်လို့ သေချာပါသလား?",
                reply_markup=ban_keyboard
            )
            del context.user_data["banning_user"]
        else:
            await update.message.reply_text(
                "❌ ထိုသက်တမ်းသုံးပြုသူသည် Anonymous Group ထဲမှာ မရှိပါ။",
                reply_markup=admin_menu_keyboard
            )
    elif message_text == "✅ Confirm Ban" and user_id == ADMIN_ID and "target_ban_id" in context.user_data:
        target_user_id = context.user_data["target_ban_id"]
        banned_users.add(target_user_id)
        if target_user_id in broadcast_group:
            del broadcast_group[target_user_id]
        del context.user_data["target_ban_id"]
        await update.message.reply_text(
            f"🚫 {target_user_id} ကို Ban လုပ်ပြီးပါတယ်။",
            reply_markup=admin_menu_keyboard
        )
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ သင်သည် Anonymous Group မှ Ban ခံထားရပါသည်။",
                reply_markup=None
            )
        except Exception:
            pass
    elif message_text == "❌ Cancel" and user_id == ADMIN_ID and "target_ban_id" in context.user_data:
        del context.user_data["target_ban_id"]
        await update.message.reply_text(
            "🚫 Ban လုပ်မှုကို မသိမ်းပါ။",
            reply_markup=admin_menu_keyboard
        )
    elif message_text == "/viewpoll" and user_id in broadcast_group:
        if "question" in poll_data:
            question = poll_data["question"]
            yes_votes = poll_data["yes"]
            no_votes = poll_data["no"]
            await update.message.reply_text(
                f"📊 **Poll Results**\nQuestion: {question}\nYes: {yes_votes}\nNo: {no_votes}",
                reply_markup=poll_keyboard
            )
        else:
            await update.message.reply_text(
                "📝 လက်ရှိမှာ Poll မရှိပါ။",
                reply_markup=broadcast_keyboard
            )
        return
    elif message_text == "/resetpoll" and user_id in broadcast_group:
        poll_data.clear()
        for target_user in broadcast_group.keys():
            try:
                await context.bot.send_message(
                    chat_id=target_user,
                    text="📝 Poll ကို ရှင်းလိုက်ပါပြီ။ အသစ်ဖန်တီးနိုင်ပါတယ်။",
                    reply_markup=broadcast_keyboard
                )
            except Exception as e:
                pass
        return
    elif message_text == "💟 Yes" and user_id in broadcast_group and "question" in poll_data:
        if user_id not in poll_data["voters"]:
            poll_data["yes"] += 1
            poll_data["voters"].add(user_id)
            await update.message.reply_text(
                "✅ သင့်မဲကို မှတ်တမ်းတင်လိုက်ပါတယ်။ /viewpoll နဲ့ ရလဒ်ကြည့်ပါ။",
                reply_markup=poll_keyboard
            )
        else:
            await update.message.reply_text(
                "❌ သင်သည် မဲပေးပြီးဖြစ်ပါတယ်။ /viewpoll နဲ့ ရလဒ်ကြည့်ပါ။",
                reply_markup=poll_keyboard
            )
        return
    elif message_text == "💔 No" and user_id in broadcast_group and "question" in poll_data:
        if user_id not in poll_data["voters"]:
            poll_data["no"] += 1
            poll_data["voters"].add(user_id)
            await update.message.reply_text(
                "✅ သင့်မဲကို မှတ်တမ်းတင်လိုက်ပါတယ်။ /viewpoll နဲ့ ရလဒ်ကြည့်ပါ။",
                reply_markup=poll_keyboard
            )
        else:
            await update.message.reply_text(
                "❌ သင်သည် မဲပေးပြီးဖြစ်ပါတယ်။ /viewpoll နဲ့ ရလဒ်ကြည့်ပါ။",
                reply_markup=poll_keyboard
            )
        return
    elif message_text == "🚪 Leave" and user_id in broadcast_group:
        del broadcast_group[user_id]
        await update.message.reply_text(
            "🚪 သင်သည် Anonymous Group မှ ထွက်လိုက်ပါတယ်။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
        if not broadcast_group:
            poll_data.clear()
        return

    if context.user_data.get("creating_poll", False) and user_id == ADMIN_ID and user_id in broadcast_group:
        if update.message.text:
            poll_question = update.message.text
            poll_data["question"] = poll_question
            poll_data["yes"] = 0
            poll_data["no"] = 0
            poll_data["voters"] = set()
            context.user_data["creating_poll"] = False
            for target_user in broadcast_group.keys():
                try:
                    await context.bot.send_message(
                        chat_id=target_user,
                        text=f"📝 **New Poll**\nQuestion: {poll_question}\n💟 Yes / 💔 No နှိပ်ပြီး မဲပေးပါ။",
                        reply_markup=poll_keyboard
                    )
                except Exception as e:
                    await handle_error(update, context, f"Poll creation error: {str(e)}")
        return

    if context.user_data.get("broadcasting", False) and user_id == ADMIN_ID:
        if update.message.text:
            broadcast_message = update.message.text
            for target_user in all_users:
                try:
                    await context.bot.send_message(chat_id=target_user, text=f"📤 Team ဘက်မှ ကြော်ငြာချက်: {broadcast_message}")
                except Exception as e:
                    await handle_error(update, context, f"Broadcast error: {str(e)}")
            context.user_data["broadcasting"] = False
            await update.message.reply_text("📤 Broadcast ပို့လိုက်ပါတယ်။", reply_markup=admin_menu_keyboard)
        elif update.message.photo:
            photo = update.message.photo[-1]
            for target_user in all_users:
                try:
                    await context.bot.send_photo(chat_id=target_user, photo=photo.file_id, caption="📤 Team ဘက်မှ ကြော်ငြာချက်: Photo")
                except Exception as e:
                    await handle_error(update, context, f"Broadcast photo error: {str(e)}")
            context.user_data["broadcasting"] = False
            await update.message.reply_text("📤 Broadcast Photo ပို့လိုက်ပါတယ်။", reply_markup=admin_menu_keyboard)
        return

    if user_id in broadcast_group:
        if update.message.text:
            broadcast_message = update.message.text
            group_message_counts[user_id] += 1
            daily_message_counts[user_id] = daily_message_counts.get(user_id, 0) + 1
            char_limit = 200 if user_id in vip_users and vip_users[user_id] == "AnonMan Plan" else 50
            # Validate message length only
            if len(broadcast_message) > char_limit:
                await update.message.reply_text(
                    f"❌ စာသားကို {char_limit} လုံးထက်မပိုရပါ။",
                    reply_markup=broadcast_keyboard
                )
                return

            user_name = broadcast_group[user_id]
            is_anonman = user_id in vip_users and vip_users[user_id] == "AnonMan Plan"
            style = text_styles.get(user_id, "none")
            formatted_message = apply_text_style(broadcast_message, style, user_name, is_anonman)

            # Group message AnonP based on daily message count
            daily_count = daily_message_counts[user_id]
            if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
                if daily_count == 500:
                    user_points[user_id] = user_points.get(user_id, 0) + 20
                    await context.bot.send_message(chat_id=user_id, text="🏆 500 စာကြောင်းပြည့်ပြီး 20 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
                elif daily_count == 300:
                    user_points[user_id] = user_points.get(user_id, 0) + 8
                    await context.bot.send_message(chat_id=user_id, text="🏆 300 စာကြောင်းပြည့်ပြီး 8 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
                elif daily_count == 100:
                    user_points[user_id] = user_points.get(user_id, 0) + 6
                    await context.bot.send_message(chat_id=user_id, text="🏆 100 စာကြောင်းပြည့်ပြီး 6 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
                elif daily_count == 50:
                    user_points[user_id] = user_points.get(user_id, 0) + 2
                    await context.bot.send_message(chat_id=user_id, text="🏆 50 စာကြောင်းပြည့်ပြီး 2 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
            else:
                if daily_count == 300:
                    user_points[user_id] = user_points.get(user_id, 0) + 5
                    await context.bot.send_message(chat_id=user_id, text="🏆 300 စာကြောင်းပြည့်ပြီး 5 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
                elif daily_count == 100:
                    user_points[user_id] = user_points.get(user_id, 0) + 3
                    await context.bot.send_message(chat_id=user_id, text="🏆 100 စာကြောင်းပြည့်ပြီး 3 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)
                elif daily_count == 50:
                    user_points[user_id] = user_points.get(user_id, 0) + 1
                    await context.bot.send_message(chat_id=user_id, text="🏆 50 စာကြောင်းပြည့်ပြီး 1 AnonP ရရှိပါတယ်။", reply_markup=broadcast_keyboard)

            for target_user in broadcast_group.keys():
                if target_user != user_id and target_user not in banned_users:
                    try:
                        await context.bot.send_message(
                            chat_id=target_user,
                            text=formatted_message,
                            parse_mode="MarkdownV2",
                            reply_markup=broadcast_keyboard
                        )
                    except Exception as e:
                        await handle_error(update, context, f"Message send error: {str(e)}")
            return
        elif update.message.photo and user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
            photo = update.message.photo[-1]
            user_name = broadcast_group[user_id]
            user_name_escaped = escape_markdown(user_name)
            for target_user in broadcast_group.keys():
                if target_user != user_id and target_user not in banned_users:
                    try:
                        await context.bot.send_photo(
                            chat_id=target_user,
                            photo=photo.file_id,
                            caption=f"🌟 {user_name_escaped} မှ ပုံတစ်ပုံ",
                            parse_mode="MarkdownV2",
                            reply_markup=broadcast_keyboard
                        )
                    except Exception as e:
                        await handle_error(update, context, f"Photo send error: {str(e)}")
            return
        elif update.message.video and user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
            video = update.message.video
            user_name = broadcast_group[user_id]
            user_name_escaped = escape_markdown(user_name)
            for target_user in broadcast_group.keys():
                if target_user != user_id and target_user not in banned_users:
                    try:
                        await context.bot.send_video(
                            chat_id=target_user,
                            video=video.file_id,
                            caption=f"🌟 {user_name_escaped} မှ ဗီဒီယိုတစ်ခု",
                            parse_mode="MarkdownV2",
                            reply_markup=broadcast_keyboard
                        )
                    except Exception as e:
                        await handle_error(update, context, f"Video send error: {str(e)}")
            return
        elif (update.message.photo or update.message.video) and (user_id not in vip_users or vip_users[user_id] != "AnonMan Plan"):
            await update.message.reply_text(
                "❌ AnonMan Plan မရှိလို့ ပုံတွေ နဲ့ ဗီဒီယိုတွေ ပို့လို့မရပါ။",
                reply_markup=broadcast_keyboard
            )
            return

    if user_id in paired_users and paired_users[user_id] is not None:
        partner_id = paired_users[user_id]
        if partner_id in paired_users and paired_users[partner_id] == user_id:
            if update.message.text:
                message_text = update.message.text
                try:
                    await context.bot.send_message(chat_id=partner_id, text=message_text)
                except Exception as e:
                    await handle_error(update, context, f"Chat message error: {str(e)}")
            elif update.message.voice:
                voice = update.message.voice
                try:
                    await context.bot.send_voice(chat_id=partner_id, voice=voice.file_id, reply_markup=chat_keyboard)
                except Exception as e:
                    await handle_error(update, context, f"Voice send error: {str(e)}")
            elif update.message.photo:
                photo = update.message.photo[-1]
                try:
                    await context.bot.send_photo(chat_id=partner_id, photo=photo.file_id, reply_markup=chat_keyboard)
                except Exception as e:
                    await handle_error(update, context, f"Photo send error: {str(e)}")
        else:
            await update.message.reply_text(
                "❌ ချိတ်ဆက်မှု ပြတ်တောက်သွားပါပြီ။ 🚪 End Chat နှိပ်ပြီး ပြန်စပါ။",
                reply_markup=chat_keyboard
            )

async def button(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    if data.startswith("prize_"):
        await query.answer()
        total_anonp = user_points.get(user_id, 0)
        prize_type = data.split("_")[1]
        if prize_type == "3day":
            cost = 3000
            prize = "3day AnonMan Plan"
            if total_anonp >= cost:
                user_points[user_id] -= cost
                vip_users[user_id] = "AnonMan Plan"
                await query.edit_message_text(
                    text=f"🎉 {prize} ကို {cost} AnonP နဲ့ ရယူပြီးပါတယ်။ သင့် Total AnonP: {total_anonp - cost}",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    text=f"❌ {cost} AnonP လိုအပ်ပါတယ်။ သင့်မှာ {total_anonp} AnonP သာရှိပါတယ်။",
                    reply_markup=None
                )
        elif prize_type == "1wk":
            cost = 5000
            prize = "1wk AnonMan Plan"
            if total_anonp >= cost:
                user_points[user_id] -= cost
                vip_users[user_id] = "AnonMan Plan"
                await query.edit_message_text(
                    text=f"🎉 {prize} ကို {cost} AnonP နဲ့ ရယူပြီးပါတယ်။ သင့် Total AnonP: {total_anonp - cost}",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    text=f"❌ {cost} AnonP လိုအပ်ပါတယ်။ သင့်မှာ {total_anonp} AnonP သာရှိပါတယ်။",
                    reply_markup=None
                )
        elif prize_type == "1000bill":
            cost = 1000
            prize = "1000 Bill"
            if total_anonp >= cost:
                user_points[user_id] -= cost
                await query.edit_message_text(
                    text=f"🎉 {prize} ကို {cost} AnonP နဲ့ ရယူပြီးပါတယ်။ (Admin ကို ဆက်သွယ်ပါ) သင့် Total AnonP: {total_anonp - cost}",
                    reply_markup=None
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 User {user_id} has redeemed {prize} with {cost} AnonP.")
            else:
                await query.edit_message_text(
                    text=f"❌ {cost} AnonP လိုအပ်ပါတယ်။ သင့်မှာ {total_anonp} AnonP သာရှိပါတယ်။",
                    reply_markup=None
                )
        elif prize_type == "3000cash":
            cost = 3000
            prize = "3000 Cash"
            if total_anonp >= cost:
                user_points[user_id] -= cost
                await query.edit_message_text(
                    text=f"🎉 {prize} ကို {cost} AnonP နဲ့ ရယူပြီးပါတယ်။ (Admin ကို ဆက်သွယ်ပါ) သင့် Total AnonP: {total_anonp - cost}",
                    reply_markup=None
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 User {user_id} has redeemed {prize} with {cost} AnonP.")
            else:
                await query.edit_message_text(
                    text=f"❌ {cost} AnonP လိုအပ်ပါတယ်။ သင့်မှာ {total_anonp} AnonP သာရှိပါတယ်။",
                    reply_markup=None
                )
        return

    if data.startswith("setnickname_"):
        await query.answer()
        if user_id not in banned_users:
            reset_nickname_changes()
            change_limit = 5 if user_id in vip_users and vip_users[user_id] == "AnonMan Plan" else 3
            current_changes = nickname_changes.get(user_id, 0)
            if current_changes >= change_limit:
                await query.edit_message_text(
                    text=f"❌ သင်သည် တစ်ပတ်အတွင်း nickname ပြောင်းခွင့် {change_limit} ကြိမ် ပြည့်သွားပါပြီ။ နောက်ပတ်ထိ စောင့်ပါ။",
                    reply_markup=None
                )
                return
            nickname_changes[user_id] = current_changes + 1
            await query.edit_message_text(
                text="📝 နောက်ထပ် မက်ဆေ့ချ်ထဲမှာ nickname ရိုက်ထည့်ပါ (20 လုံးထက်မပိုရပါဘူး၊ emoji မပါရပါ)။",
                reply_markup=None
            )
            context.user_data["setting_nickname"] = True
        return
    elif data.startswith("settextstyle_"):
        await query.answer()
        if user_id not in banned_users:
            if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
                await query.edit_message_text(
                    text="📝 Text Style ကို 'bold', 'italic', ဒါမှမဟုတ် 'none' ထည့်ပါ။",
                    reply_markup=None
                )
                context.user_data["setting_textstyle"] = True
            else:
                await query.edit_message_text(
                    text="❌ သင်သည် AnonMan Plan မရှိလို့ Text Style ပြောင်းလို့မရပါ။",
                    reply_markup=None
                )
        return
    elif data.startswith("setbadge_"):
        await query.answer()
        if user_id not in banned_users:
            if user_id in vip_users and vip_users[user_id] == "AnonMan Plan":
                await query.edit_message_text(
                    text="📝 Custom Badge အဖြစ် emoji တစ်ခုထည့်ပါ (ဥပမာ: ⭐)။",
                    reply_markup=None
                )
                context.user_data["setting_badge"] = True
            else:
                await query.edit_message_text(
                    text="❌ သင်သည် AnonMan Plan မရှိလို့ Custom Badge သတ်မှတ်လို့မရပါ။",
                    reply_markup=None
                )
        return
    elif data.startswith("notallowed_"):
        await query.answer()
        await query.edit_message_text(
            text="❌ သင်သည် AnonMan Plan မရှိလို့ ဒီလုပ်ဆောင်ချက်ကို သုံးလို့မရပါ။",
            reply_markup=None
        )
        return

    await query.answer()

async def upgrade_vip(update, context):
    user_id = update.effective_user.id
    if user_id in vip_users:
        await update.message.reply_text(
            f"🌟 သင်က {vip_users[user_id]} အဖြစ် ရှိနေပါပြီ။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )
    else:
        await update.message.reply_text(
            "🌟 VIP ဝင်ခွင့်ရဖို့ [Your Payment Link] မှာ ပိုက်ဆံပေးချေပါ။ ပိုက်ဆံပေးပြီးရင် Admin ကို ဆက်သွယ်ပါ။",
            reply_markup=admin_menu_keyboard if user_id == ADMIN_ID else user_menu_keyboard
        )

async def set_vip(update, context):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ ဒီ command ကို Admin ပဲ သုံးလို့ရပါတယ်။")
        return
    if not context.args:
        await update.message.reply_text("❌ အသုံးပြုပုံ: /set_vip <user_id> <tier>")
        return
    try:
        target_user_id = int(context.args[0])
        tier = context.args[1]
        if tier not in ["VIP Bronze", "VIP Silver", "VIP Gold", "AnonMan Plan"]:
            await update.message.reply_text("❌ Tier ကို VIP Bronze, VIP Silver, VIP Gold, ဒါမှမဟုတ် AnonMan Plan ဖြစ်ရမယ်။")
            return
        vip_users[target_user_id] = tier
        if tier == "AnonMan Plan":
            current_nick = custom_nicknames.get(target_user_id, user_names.get(target_user_id, "Anonymous"))
            custom_nicknames[target_user_id] = f"🎭 {current_nick}"
            anonman_bonus_given[target_user_id] = False  # Reset bonus flag for new AnonMan Plan
        await update.message.reply_text(
            f"✅ User {target_user_id} ကို {tier} အဖြစ် သတ်မှတ်ပြီးပါတယ်။",
            reply_markup=admin_menu_keyboard
        )
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🌟 ဂုဏ်ယူပါတယ်! သင်က {tier} အဖြစ် အဆင့်မြှင့်တင်ခံရပါတယ်။ {'(Nickname ကို 🎭 ထည့်ပေးထားပါတယ်)' if tier == 'AnonMan Plan' else ''}",
            reply_markup=user_menu_keyboard
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ အသုံးပြုပုံ: /set_vip <user_id> <tier>")

async def gift_anonman_plan(update, context):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ ဒီ command ကို Admin ပဲ သုံးလို့ရပါတယ်။")
        return
    if not context.args:
        await update.message.reply_text("❌ အသုံးပြုပုံ: /gift_anonman <user_id>")
        return
    try:
        target_user_id = int(context.args[0])
        if target_user_id not in all_users:
            await update.message.reply_text("❌ ထို User ID မရှိပါ။", reply_markup=admin_menu_keyboard)
            return
        vip_users[target_user_id] = "AnonMan Plan"
        current_nick = custom_nicknames.get(target_user_id, user_names.get(target_user_id, "Anonymous"))
        custom_nicknames[target_user_id] = f"🎭 {current_nick}"
        anonman_bonus_given[target_user_id] = False  # Reset bonus flag for gifted AnonMan Plan
        await update.message.reply_text(
            f"🎁 User {target_user_id} ကို AnonMan Plan လက်ဆောင်ပေးလိုက်ပါတယ်။",
            reply_markup=admin_menu_keyboard
        )
        await context.bot.send_message(
            chat_id=target_user_id,
            text="🎉 ဂုဏ်ယူပါတယ်! Admin ထံမှ AnonMan Plan လက်ဆောင်ရရှိပါတယ်။ (Nickname ကို 🎭 ထည့်ပေးထားပါတယ်)",
            reply_markup=user_menu_keyboard
        )
    except (IndexError, ValueError):
        await update.message.reply_text("❌ အသုံးပြုပုံ: /gift_anonman <user_id>")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("join", join))
    application.add_handler(CommandHandler("end", end))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("upgrade_vip", upgrade_vip))
    application.add_handler(CommandHandler("set_vip", set_vip))
    application.add_handler(CommandHandler("gift_anonman", gift_anonman_plan))
    application.add_handler(MessageHandler(filters.ALL, handle_message))
    application.add_handler(CallbackQueryHandler(button))
    application.add_error_handler(error_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
