from flask import Flask

app = Flask(__name__)
app.config.from_prefixed_env()


@app.route('/')
def index():
    return 'OK'


if __name__ == '__main__':
    app.run()
