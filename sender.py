import os
import json
import asyncio
import threading
from pyrogram import Client

BASE_DIR = os.path.dirname(__file__)
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MESSAGE_FILE = os.path.join(BASE_DIR, "message.txt")


def _get_session():
    sessions = [f[:-8] for f in os.listdir(SESSIONS_DIR) if f.endswith('.session')]
    if not sessions:
        print("Нет доступных сессий в", SESSIONS_DIR)
        return None, None
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


async def _sender_loop(target: str, interval: float):
    client, name = _get_session()
    if not client:
        return
    msg = _load_message()
    if not msg:
        print("message.txt пуст")
        return
    async with client:
        print(f"\nЗапуск рассылки через сессию {name}. Цель: {target}. Интервал: {interval} сек")
        while True:
            try:
                if target == 'favorites':
                    await client.send_message("me", msg)
                    print("Отправлено в Избранное")
                elif target == 'all':
                    async for dialog in client.get_dialogs():
                        try:
                            await client.send_message(dialog.chat.id, msg)
                            print("Успешно:", dialog.chat.id)
                        except Exception as e:
                            print("Ошибка при отправке", dialog.chat.id, e)
                        await asyncio.sleep(0.5)
                else:
                    await client.send_message(int(target), msg)
                    print("Отправлено", target)
                await asyncio.sleep(interval)
            except Exception as e:
                print("Ошибка:", e)
                await asyncio.sleep(interval)


def run_sender(target: str, interval: float):
    thread = threading.Thread(target=lambda: asyncio.run(_sender_loop(target, interval)), daemon=True)
    thread.start()
    return thread
