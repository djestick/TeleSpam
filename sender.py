import os
import json
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Optional

from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

BASE_DIR = os.path.dirname(__file__)
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
MESSAGE_FILE = os.path.join(BASE_DIR, "message.txt")
STATE_FILE = os.path.join(BASE_DIR, "state.json")

os.makedirs(SESSIONS_DIR, exist_ok=True)

_log: List[str] = []
_send_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_active_session: Optional[str] = None

_pending_sessions: Dict[str, Dict] = {}


def _list_sessions() -> List[str]:
    return [f[:-8] for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")]


def _load_message() -> str:
    if not os.path.exists(MESSAGE_FILE):
        return ""
    with open(MESSAGE_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_message(text: str) -> None:
    with open(MESSAGE_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def _load_state() -> Dict[str, object]:
    if not os.path.exists(STATE_FILE):
        return {"mode": "all", "interval": 1.0}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(mode: Optional[str] = None, interval: Optional[float] = None) -> None:
    state = _load_state()
    if mode is not None:
        state["mode"] = mode
    if interval is not None:
        state["interval"] = interval
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def get_message() -> str:
    return _load_message()


def get_log() -> List[str]:
    return list(_log)


def get_state() -> Dict[str, object]:
    return _load_state()


def list_sessions() -> List[str]:
    return _list_sessions()


def _client_for(name: str) -> Client:
    cfg_path = os.path.join(SESSIONS_DIR, f"{name}.json")
    if not os.path.exists(cfg_path):
        raise RuntimeError("session config missing")
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return Client(os.path.join(SESSIONS_DIR, name), api_id=cfg["api_id"], api_hash=cfg["api_hash"])


async def _sender_loop(session_name: str, mode: str, interval: float) -> None:
    global _active_session
    client = _client_for(session_name)
    message = _load_message()
    if not message:
        _log.append("❌ message.txt пуст")
        return
    async with client:
        _active_session = session_name
        while not _stop_event.is_set():
            try:
                if mode == "favorites":
                    await client.send_message("me", message)
                    _log.append("✅ favorites")
                elif mode == "all":
                    async for dialog in client.get_dialogs():
                        if _stop_event.is_set():
                            break
                        try:
                            await client.send_message(dialog.chat.id, message)
                            _log.append(f"✅ {dialog.chat.id}")
                        except Exception as e:  # pragma: no cover - network related
                            _log.append(f"❌ {dialog.chat.id}: {e}")
                        await asyncio.sleep(0.5)
                else:
                    try:
                        await client.send_message(int(mode), message)
                        _log.append(f"✅ {mode}")
                    except Exception as e:  # pragma: no cover - network related
                        _log.append(f"❌ {mode}: {e}")
                if _stop_event.is_set():
                    break
                _log.append("⏳ waiting")
                await asyncio.sleep(max(1.0, interval))
            except Exception as e:  # pragma: no cover - network related
                _log.append(f"❌ loop error: {e}")
                await asyncio.sleep(interval)
    _active_session = None


def start_sending(session_name: str, mode: str, interval: float) -> None:
    global _send_thread
    if _send_thread and _send_thread.is_alive():
        raise RuntimeError("sender already running")
    _stop_event.clear()
    _log.clear()
    _save_state(mode, interval)
    thread = threading.Thread(target=lambda: asyncio.run(_sender_loop(session_name, mode, interval)), daemon=True)
    _send_thread = thread
    thread.start()


def stop_sending() -> None:
    global _send_thread
    if _send_thread and _send_thread.is_alive():
        _stop_event.set()
        _send_thread.join()
    _send_thread = None
    _stop_event.clear()


# ---- session management ----
async def _create_client(session_name: str, api_id: int, api_hash: str) -> Client:
    client = Client(os.path.join(SESSIONS_DIR, session_name), api_id=api_id, api_hash=api_hash)
    await client.connect()
    return client


def start_session_creation(session_name: str, api_id: int, api_hash: str) -> None:
    if session_name in _pending_sessions:
        raise RuntimeError("creation in progress")
    client = asyncio.run(_create_client(session_name, api_id, api_hash))
    _pending_sessions[session_name] = {"client": client, "api_id": api_id, "api_hash": api_hash}


def send_phone(session_name: str, phone: str) -> None:
    state = _pending_sessions.get(session_name)
    if not state:
        raise RuntimeError("no such creation")
    result = asyncio.run(state["client"].send_code(phone))
    state["phone"] = phone
    state["phone_code_hash"] = result.phone_code_hash


def confirm_code(session_name: str, code: str) -> str:
    state = _pending_sessions.get(session_name)
    if not state:
        raise RuntimeError("no such creation")
    client = state["client"]
    try:
        asyncio.run(client.sign_in(phone_number=state["phone"], phone_code_hash=state["phone_code_hash"], phone_code=code))
    except SessionPasswordNeeded:
        state["need_password"] = True
        return "password"
    _finish_creation(session_name)
    return "ok"


def confirm_password(session_name: str, password: str) -> None:
    state = _pending_sessions.get(session_name)
    if not state or not state.get("need_password"):
        raise RuntimeError("password not required")
    client = state["client"]
    asyncio.run(client.check_password(password))
    _finish_creation(session_name)


def _finish_creation(session_name: str) -> None:
    state = _pending_sessions.pop(session_name, None)
    if not state:
        return
    client = state["client"]
    asyncio.run(client.disconnect())
    cfg_path = os.path.join(SESSIONS_DIR, f"{session_name}.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({"api_id": state["api_id"], "api_hash": state["api_hash"], "phone": state.get("phone")}, f)


def delete_session(session_name: str) -> None:
    for ext in (".session", ".session-journal", ".json"):
        path = os.path.join(SESSIONS_DIR, session_name + ext)
        if os.path.exists(path):
            os.remove(path)


def logout_session(session_name: str) -> None:
    client = _client_for(session_name)
    asyncio.run(client.log_out())


def active_session() -> Optional[str]:
    return _active_session


# ---- compatibility with initial CLI ----
def _get_session():
    sessions = list_sessions()
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


def run_sender(target: str, interval: float):
    sessions = list_sessions()
    if not sessions:
        print("Нет доступных сессий в", SESSIONS_DIR)
        return None
    _save_state(target, interval)
    start_sending(sessions[0], target, interval)
    return _send_thread
