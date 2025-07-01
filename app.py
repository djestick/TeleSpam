from flask import Flask, request, jsonify
import TeleSpam

app = Flask(__name__)

@app.post('/send')
def send():
    mode = request.form.get('mode', 'saved')
    target = request.form.get('target')
    interval = request.form.get('interval')
    try:
        interval = int(interval) if interval else 1
    except ValueError:
        interval = 1
    TeleSpam.configure(mode, target, interval)
    TeleSpam.start_spam()
    return 'started'


@app.post('/stop')
def stop():
    TeleSpam.stop_spam()
    return 'stopped'


@app.route('/message', methods=['GET', 'POST'])
def message():
    if request.method == 'POST':
        text = request.form.get('text', '')
        TeleSpam.set_message(text)
        return 'saved'
    return TeleSpam.get_message()


@app.get('/log')
def log():
    return TeleSpam.get_log()


@app.get('/sessions')
def sessions():
    return jsonify(TeleSpam.list_sessions())


@app.post('/sessions/new')
def new_session():
    name = request.form.get('name', 'account')
    TeleSpam.create_session(name)
    return 'created'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
