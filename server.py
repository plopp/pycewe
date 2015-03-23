from flask import Flask
from flask import jsonify
import json
app = Flask(__name__)

@app.route('/')
def hello_world():
    f = open('/mnt/ramdisk/out.json','r')
    data = f.read()
    f.close()
    return jsonify(json.loads(data))


if __name__ == '__main__':
    app.run('0.0.0.0',3000)
