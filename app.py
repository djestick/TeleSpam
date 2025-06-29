from flask import Flask, request, jsonify, send_file, render_template
import sender

app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        target = request.form.get('target', 'all')
        interval = request.form.get('interval', '60')
        try:
            interval = float(interval)
        except ValueError:
            interval = 60.0
        sender.run_sender(target.strip(), interval)
        return 'Рассылка запущена'
    return render_template('index.html')


@app.post('/send')
def send():
    data = request.get_json(force=True)
    session_name = data.get('session_name')
    mode = data.get('mode', 'all')
    interval = float(data.get('interval', 1))
    try:
        sender.start_sending(session_name, mode, interval)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    return jsonify({'status': 'started'})


@app.post('/stop')
def stop():
    sender.stop_sending()
    return jsonify({'status': 'stopped'})


@app.get('/message')
def get_message():
    return send_file(sender.MESSAGE_FILE, mimetype='text/plain; charset=utf-8')


@app.post('/message')
def save_message():
    text = request.data.decode('utf-8')
    sender.save_message(text)
    return jsonify({'status': 'saved'})


@app.get('/log')
def get_log():
    return jsonify({'log': sender.get_log()})


@app.get('/state')
def get_state():
    return jsonify(sender.get_state())


@app.get('/sessions')
def get_sessions():
    return jsonify({'sessions': sender.list_sessions(), 'active': sender.active_session()})


@app.post('/sessions/new')
def create_session():
    data = request.get_json(force=True)
    step = data.get('step')
    name = data.get('session_name')
    if step == 'start':
        sender.start_session_creation(name, int(data['api_id']), data['api_hash'])
        return jsonify({'status': 'ok'})
    if step == 'phone':
        sender.send_phone(name, data['phone'])
        return jsonify({'status': 'code_sent'})
    if step == 'code':
        status = sender.confirm_code(name, data['code'])
        return jsonify({'status': status})
    if step == 'password':
        sender.confirm_password(name, data['password'])
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'bad step'}), 400


@app.post('/sessions/delete')
def delete_session():
    data = request.get_json(force=True)
    sender.delete_session(data['session_name'])
    return jsonify({'status': 'deleted'})


@app.post('/sessions/logout')
def logout():
    data = request.get_json(force=True)
    sender.logout_session(data['session_name'])
    return jsonify({'status': 'logged_out'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
