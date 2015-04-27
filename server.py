from flask import Flask
from flask import jsonify
from flask import render_template
from flask.ext.cors import CORS
import time
import json
app = Flask(__name__)

cors = CORS(app, resources={r"/data*": {"origins": "*"}})

@app.route('/data')
def data():
    while True:
        try:
            f = open('/mnt/ramdisk/out.json','r')
            data = f.read()
            f.close()
            break
        except IOError:
            time.sleep(0.01)
    return jsonify(json.loads(data))


if __name__ == '__main__':
    app.run()
