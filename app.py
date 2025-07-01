import argparse
import os
from flask import Flask, request, jsonify, render_template
import sender
import TeleSpam

app = Flask(__name__)

active_session = None

def get_default_session():
    sessions = sender.list_sessions()
    return sessions[0] if sessions else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sessions')
def sessions_api():
    return jsonify({'sessions': sender.list_sessions(), 'active': sender.current_session})

@app.route('/api/use_session', methods=['POST'])
def use_session():
    name = request.json.get('name')
    if name:
        sender.current_session = name
    return jsonify({'ok': True})

@app.route('/api/message', methods=['GET', 'POST'])
def message_api():
    if request.method == 'POST':
        text = request.json.get('text', '')
        sender.save_message(text)
        return jsonify({'ok': True})
    return jsonify({'text': open(sender.MESSAGE_FILE, 'r', encoding='utf-8').read() if os.path.exists(sender.MESSAGE_FILE) else ''})

@app.route('/api/start', methods=['POST'])
def start():
    data = request.json
    target = data.get('target', 'all')
    interval = float(data.get('interval', 60))
    session = sender.current_session or get_default_session()
    if not session:
        return jsonify({'error': 'no session'}), 400
    sender.run_sender(session, target, interval)
    return jsonify({'ok': True})

@app.route('/api/stop', methods=['POST'])
def stop():
    sender.stop_sender()
    return jsonify({'ok': True})

@app.route('/api/logs')
def logs_api():
    return jsonify({'logs': sender.get_logs(), 'running': sender.is_running()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--console', action='store_true')
    args = parser.parse_args()
    if args.console:
        import asyncio
        asyncio.run(TeleSpam.main())
    else:
        app.run(host='0.0.0.0', port=8080)


if __name__ == '__main__':
    main()
