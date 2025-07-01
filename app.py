from flask import Flask, request, jsonify
import threading
import asyncio
import io
import contextlib
import TeleSpam

app = Flask(__name__)

log_buffer = io.StringIO()
sender_thread = None


def run_sender(mode: str, target: str | None, interval: float, session: str | None):
    async def runner():
        await TeleSpam.start(mode=mode, target=target, interval=interval, session_name=session)
    global log_buffer
    log_buffer = io.StringIO()
    with contextlib.redirect_stdout(log_buffer):
        asyncio.run(runner())


@app.route('/send', methods=['POST'])
def start_send():
    global sender_thread
    if sender_thread and sender_thread.is_alive():
        return jsonify({'status': 'already running'}), 400
    data = request.get_json() or {}
    mode = data.get('mode', 'saved')
    target = data.get('target')
    interval = float(data.get('interval', 1))
    session = data.get('session')
    sender_thread = threading.Thread(target=run_sender, args=(mode, target, interval, session), daemon=True)
    sender_thread.start()
    return jsonify({'status': 'started'})


@app.route('/stop', methods=['POST'])
def stop_send():
    TeleSpam.stop()
    return jsonify({'status': 'stopping'})


@app.route('/log', methods=['GET'])
def get_log():
    return jsonify({'log': log_buffer.getvalue()})


@app.route('/message', methods=['GET', 'POST'])
def message():
    if request.method == 'GET':
        return jsonify({'message': TeleSpam.get_message()})
    data = request.get_json() or {}
    TeleSpam.set_message(data.get('message', ''))
    return jsonify({'status': 'updated'})


@app.route('/sessions', methods=['GET'])
def sessions():
    return jsonify({'sessions': TeleSpam.list_sessions()})


@app.route('/sessions/new', methods=['POST'])
def sessions_new():
    data = request.get_json() or {}
    name = data.get('name', 'account1')
    TeleSpam.set_session(name)
    asyncio.run(TeleSpam.authorize(
        api_id=int(data['api_id']),
        api_hash=data['api_hash'],
        phone=data['phone'],
        code=data['code'],
        password=data.get('password')
    ))
    return jsonify({'status': 'created', 'session': name})


@app.route('/sessions/logout', methods=['POST'])
def sessions_logout():
    name = request.get_json().get('name')
    if not name:
        return jsonify({'error': 'name required'}), 400
    asyncio.run(TeleSpam.logout_session(name))
    return jsonify({'status': 'logged out'})


@app.route('/sessions/delete', methods=['POST'])
def sessions_delete():
    name = request.get_json().get('name')
    if not name:
        return jsonify({'error': 'name required'}), 400
    TeleSpam.delete_session(name)
    return jsonify({'status': 'deleted'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
