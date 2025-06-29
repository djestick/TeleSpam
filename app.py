from flask import Flask, request, render_template
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
