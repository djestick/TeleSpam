import os
import sys
import asyncio
import json
import time
import logging
from pyrogram import Client
from pyrogram.errors import PeerIdInvalid, SessionPasswordNeeded
from colorama import init, Fore, Style
from tqdm.asyncio import tqdm
from datetime import datetime, timedelta

sys.stderr = open(os.devnull, 'w')
logging.getLogger("pyrogram.connection.connection").setLevel(logging.CRITICAL)
init()

BASE_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(BASE_DIR, "session_config.json")
MESSAGE_FILE = os.path.join(BASE_DIR, "message.txt")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
SESSION_NAME = None
stop_event = asyncio.Event()
send_mode = "saved"
send_target = None
current_user = None
all_dialogs_count = None
client_instance = None
interval_minutes = 1

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def get_message():
    if not os.path.exists(MESSAGE_FILE):
        with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
            f.write('<emoji id="5276032951342088188">\ud83d\udca5</emoji> Telegram mass sender')
    with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def set_message(text: str):
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write(text)

def list_sessions():
    return [f.replace(".session", "") for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")]

def set_session(name: str):
    global SESSION_NAME
    SESSION_NAME = name

def load_config(name):
    path = os.path.join(SESSIONS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(name, data):
    path = os.path.join(SESSIONS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

def delete_session(name):
    """Delete session files for given name."""
    sess = os.path.join(SESSIONS_DIR, f"{name}.session")
    cfg = os.path.join(SESSIONS_DIR, f"{name}.json")
    if os.path.exists(sess):
        os.remove(sess)
    if os.path.exists(cfg):
        os.remove(cfg)

async def logout_session(name):
    """Log out of the specified session."""
    config = load_config(name)
    if not config:
        return False
    async with Client(os.path.join(SESSIONS_DIR, name), api_id=config["api_id"], api_hash=config["api_hash"]) as app:
        await app.log_out()
    return True

async def authorize(api_id=None, api_hash=None, phone=None, code=None, password=None):
    """Authorize account. If parameters are None, fallback to interactive input."""
    clear()
    print("Авторизация с https://my.telegram.org/apps:")
    if api_id is None:
        api_id = int(input("API ID: ").strip())
    if api_hash is None:
        api_hash = input("API HASH: ").strip()
    if phone is None:
        phone = input("Телефон (с +кодом): ").strip()
    app = Client(os.path.join(SESSIONS_DIR, SESSION_NAME), api_id=api_id, api_hash=api_hash)
    await app.connect()
    code_data = await app.send_code(phone)
    if code is None:
        code = input(f"Код для {phone}: ").strip()
    try:
        await app.sign_in(phone_number=phone, phone_code_hash=code_data.phone_code_hash, phone_code=code)
    except SessionPasswordNeeded:
        if password is None:
            password = input("Пароль (если есть): ").strip()
        await app.check_password(password)
    await app.disconnect()
    save_config(SESSION_NAME, {"api_id": api_id, "api_hash": api_hash, "phone": phone})
    print("✅ Вход выполнен")
    time.sleep(1)

async def init_client(name=None):
    """Initialize client for specified session name."""
    global SESSION_NAME
    if name is not None:
        SESSION_NAME = name
    sessions = list_sessions()
    if not sessions:
        SESSION_NAME = name or "account1"
        await authorize()
        sessions = list_sessions()
    if not sessions:
        print("❌ Не удалось создать сессию.")
        exit()
    if SESSION_NAME is None:
        SESSION_NAME = sessions[0]
    config = load_config(SESSION_NAME)
    return Client(os.path.join(SESSIONS_DIR, SESSION_NAME), api_id=config["api_id"], api_hash=config["api_hash"])

async def get_all_dialog_ids(app):
    ids = []
    async for dialog in app.get_dialogs():
        ids.append((dialog.chat.id, getattr(dialog.chat, "title", None) or getattr(dialog.chat, "username", None) or "без названия"))
    return ids

def render_header():
    clear()
    print(Fore.RED + "=== Telegram Mass Sender ===" + Style.RESET_ALL)
    print(f"Аккаунт: @{current_user.username if current_user.username else current_user.id}")
    if send_mode == "saved":
        mode_info = "В избранное"
    elif send_mode == "one":
        mode_info = f"В чат (@{send_target})"
    else:
        count_str = f" ({all_dialogs_count})" if all_dialogs_count else ""
        mode_info = f"Во все чаты{count_str}"
    print(f"Текущий режим: {mode_info}")
    print(f"Текущий интервал: {interval_minutes} мин")
    print(" ")

async def send_messages(app):
    global all_dialogs_count
    render_header()
    msg = get_message()
    if not msg:
        print("❌ message.txt пуст")
        return

    try:
        while not stop_event.is_set():
            start = datetime.now()
            if send_mode == "saved":
                print("→ Режим: В избранное")
                await app.send_message("me", msg)
                print(f"✅ В избранное отправлено @ {start.strftime('%H:%M:%S')}")

            elif send_mode == "one":
                print(f"→ Режим: Конкретный чат @{send_target}")
                user = await app.get_users(send_target)
                await asyncio.sleep(0.5)
                await app.send_message(user.id, msg)
                print(f"✅ Отправлено @{send_target} @ {start.strftime('%H:%M:%S')}")

            elif send_mode == "all":
                print("→ Режим: Во все чаты")
                dialogs = await get_all_dialog_ids(app)
                all_dialogs_count = len(dialogs)
                render_header()
                print(f"Найдено {all_dialogs_count} чатов. Рассылаем...\n")
                for chat_id, name in dialogs:
                    try:
                        await app.send_message(chat_id, msg)
                        print(f"✅ Успешно: {name} | {chat_id}")
                    except Exception as e:
                        print(f"❌ Ошибка в {name} | {chat_id}: {e}")
                    await asyncio.sleep(0.5)

            next_time = datetime.now() + timedelta(minutes=interval_minutes)
            print(f"⏳ Ждём {interval_minutes} минут... (до {next_time.strftime('%H:%M:%S')})")
            try:
                await asyncio.wait_for(stop_event.wait(), interval_minutes * 60)
            except asyncio.TimeoutError:
                continue
            except KeyboardInterrupt:
                print("⛔ Остановлено пользователем (Ctrl+C)")
                return

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        stop_event.clear()

async def change_target():
    global send_mode, send_target, all_dialogs_count
    clear()
    print("1. В избранное\n2. Во все чаты\n3. В конкретный чат")
    m = input("Режим: ").strip()
    if m == "1":
        send_mode = "saved"
        send_target = None
        all_dialogs_count = None
    elif m == "2":
        send_mode = "all"
        send_target = None
        if client_instance:
            dialogs = await get_all_dialog_ids(client_instance)
            all_dialogs_count = len(dialogs)
    elif m == "3":
        send_target = input("@username или ID: ").strip().lstrip("@")
        send_mode = "one"
        all_dialogs_count = None

async def change_interval():
    global interval_minutes
    clear()
    print("Введите интервал в минутах:")
    try:
        minutes = int(input("Интервал: ").strip())
        if minutes > 0:
            interval_minutes = minutes
    except:
        pass

async def start(mode="saved", target=None, interval=1, session_name=None):
    """Start sending messages using given parameters."""
    global send_mode, send_target, interval_minutes, current_user, client_instance, all_dialogs_count
    send_mode = mode
    send_target = target
    interval_minutes = interval
    app = await init_client(session_name)
    async with app:
        client_instance = app
        current_user = await app.get_me()
        if send_mode == "all":
            dialogs = await get_all_dialog_ids(app)
            all_dialogs_count = len(dialogs)
        await send_messages(app)

def stop():
    """Signal sender to stop."""
    if not stop_event.is_set():
        stop_event.set()

async def main():
    global current_user, client_instance, all_dialogs_count
    app = await init_client()
    async with app:
        client_instance = app
        current_user = await app.get_me()
        if send_mode == "all":
            dialogs = await get_all_dialog_ids(app)
            all_dialogs_count = len(dialogs)
        while True:
            render_header()
            print("1. Начать рассылку")
            print("2. Изменить путь рассылки")
            print("3. Изменить интервал")
            print("4. Завершить")
            choice = input("Ваш выбор: ").strip()
            if choice == "1":
                await send_messages(app)
            elif choice == "2":
                await change_target()
            elif choice == "3":
                await change_interval()
            elif choice == "4":
                clear()
                break
            else:
                input("Неверный ввод. Enter...")

if __name__ == "__main__":
    asyncio.run(main())
