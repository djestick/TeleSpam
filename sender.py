import os
import json
import asyncio
import threading
from typing import List
from pyrogram import Client

BASE_DIR = os.path.dirname(__file__)
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MESSAGE_FILE = os.path.join(BASE_DIR, "message.txt")

logs: List[str] = []
sender_thread: threading.Thread | None = None
stop_event = threading.Event()
current_session: str | None = None


def append_log(text: str):
    print(text)
    logs.append(text)


def _get_session(name: str | None = None):
    sessions = [f[:-8] for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not sessions:
        print("Нет доступных сессий в", SESSIONS_DIR)
        return None, None
    if name is None or name not in sessions:
        name = sessions[0]
    cfg_path = os.path.join(SESSIONS_DIR, f"{name}.json")
    if not os.path.exists(cfg_path):
        print("Нет конфигурации для", name)
        return None, None
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    client = Client(os.path.join(SESSIONS_DIR, name), api_id=cfg["api_id"], api_hash=cfg["api_hash"])
    return client, name


def _load_message():
    if not os.path.exists(MESSAGE_FILE):
        return ""
    with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_message(text: str):
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def list_sessions() -> List[str]:
    return [f[:-8] for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]


async def _sender_loop(session_name: str, target: str, interval: float):
    client, name = _get_session(session_name)
    if not client:
        return
    msg = _load_message()
    if not msg:
        print("message.txt пуст")
        return
    async with client:
        append_log(f"Запуск рассылки через сессию {name}. Цель: {target}. Интервал: {interval} сек")
        while not stop_event.is_set():
            try:
                if target == 'favorites':
                    await client.send_message("me", msg)
                    append_log("Отправлено в Избранное")
                elif target == 'all':
                    async for dialog in client.get_dialogs():
                        try:
                            await client.send_message(dialog.chat.id, msg)
                            append_log(f"Успешно: {dialog.chat.id}")
                        except Exception as e:
                            append_log(f"Ошибка при отправке {dialog.chat.id}: {e}")
                        await asyncio.sleep(0.5)
                else:
                    await client.send_message(int(target), msg)
                    append_log(f"Отправлено {target}")
                await asyncio.sleep(interval)
            except Exception as e:
                append_log(f"Ошибка: {e}")
                await asyncio.sleep(interval)


def run_sender(session_name: str, target: str, interval: float):
    global sender_thread, current_session
    if sender_thread and sender_thread.is_alive():
        return
    stop_event.clear()
    current_session = session_name
    thread = threading.Thread(target=lambda: asyncio.run(_sender_loop(session_name, target, interval)), daemon=True)
    sender_thread = thread
    thread.start()
    return thread


def stop_sender():
    stop_event.set()


def get_logs() -> List[str]:
    return logs


def is_running() -> bool:
    return sender_thread is not None and sender_thread.is_alive()
