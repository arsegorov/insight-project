from app import app
from flask import render_template
from datetime import datetime
from random import seed, randint


@app.route('/')
def front():
    return 'Hello, World!'


@app.route('/status')
def status():
    data = []
    seed()

    for i in range(24):
        data.append([])
        for j in range(60):
            data[i].append(randint(0, 1))
    return render_template(
        'index.html',
        date=str(datetime.now()),
        data=data,
        percent=75)
