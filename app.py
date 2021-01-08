import os

from flask import Flask, render_template, request, session

from xfutil import audio_to_text

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index1.html')


@app.route('/ars', methods=["POST"])
def ars():
    if request.method == 'POST':
        filename = request.form['audio-filename']
        file = request.files['audio-blob']
        upload_folder = 'static/audio'
        audio_path = os.path.join(upload_folder, filename)
        file.save(audio_path)
        res = audio_to_text(audio_path)
        return res


if __name__ == "__main__":
    app.run()
