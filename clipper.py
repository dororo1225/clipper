# -*- coding: utf-8 -*-
__author__ = 'yamamoto'

from flask import Flask, jsonify, g, request, render_template
import json
import os
import re
import sqlite3
import time
from pprint import pprint

# 各ユーザーのdropboxフォルダを取得（データベースフォルダ共有済み＋デフォルト設定を想定）
# macでは動かない模様
data_path = os.getenv("HOMEDRIVE") + \
                    os.getenv("HOMEPATH") +  \
                    "\\Dropbox\\test_db\\samples.db"

home = os.getenv("HOMEPATH")
teacher = home.split("Users\\")[1]

app = Flask(__name__)
app.config.update(
    DATABASE = data_path,
    DEBUG = True
)

db = None
samples = None


def getdb():  # データベースにアクセス
    global db
    if db is None:
        db = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


def querydb(query, args=(), one=False):  # クエリ
    cur = getdb().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def getsamples(update=False):  # DBのsamplesテーブルからid, filepathを取得
    global samples
    if update or samples is None:
        sql = 'SELECT id, filepath FROM samples'
        samples = querydb(sql)
    return samples


def getpos():  # progressテーブルのカラムposのデータを取得
    sql = 'SELECT pos FROM progress'
    pos = querydb(sql, one=True)['pos']
    return pos


def updatepos(pos):  # progressテーブルのposカラムのデータを更新
    sql = 'UPDATE progress SET pos=?'
    db = getdb()
    db.execute(sql, (pos,))
    db.commit()


def getstatus(pos):  # samplesテーブルでid=pos+1となるカラムstatusのデータを取得
    sql = 'SELECT status FROM samples WHERE id=?'
    row = querydb(sql, (pos + 1,), one=True)
    return (row['status'] if row else None)


def updatecoords(coords, pos):  # samplesテーブルでid=posとなるデータを更新
    sql = 'UPDATE samples SET x=?, y=?, width=?, height=?, status=?, teacher=?, updated_date=? WHERE id=?'
    db = getdb()
    db.execute(sql, (coords['x'], coords['y'], coords['w'], coords['h'], 200, teacher, time.strftime('%Y-%m-%d %H:%M:%S'), pos))
    db.commit()


@app.route('/clipper')
def index():
    message = 'ready to load images ok.'
    samples = getsamples()
    imgtotal = len(samples)
    pos = getpos()
    if pos == imgtotal:  # すべての画像のアノテーションが終了した場合
        message = 'complete !'
        return render_template('index.html', progress=100, message=message)

    try:
        imgsrc = samples[pos]['filepath']  # DBから抽出したfilepathの画像を取得
    except IndexError as e:
        imgsrc = None

    status = getstatus(pos)
    remain = imgtotal - pos
    progress = 1.0*pos/imgtotal*100
    return render_template('index.html', imgsrc=imgsrc, imgtotal=imgtotal, pos=pos, status=status, remain=remain, progress=progress, message=message)

    # log.datを作成
    logf = open('log.dat', 'w')


@app.route('/clipper/next')  # 次の画像に移動
def next():
    coords = json.loads(request.args.get('coords'))
    isskip = request.args.get('skip')
    samples = getsamples()
    pos = getpos()
    imgtotal = len(samples)
    app.logger.debug(coords)

    if coords is not None:
        updatecoords(coords, pos + 1)

    if pos < imgtotal:
        pos += 1
        updatepos(pos)

    try:
        imgsrc = samples[pos]['filepath']
    except IndexError as e:
        imgsrc = None

    status = getstatus(pos)
    remain = imgtotal - pos
    progress = 1.0*pos/imgtotal*100
    return jsonify(imgsrc=imgsrc, pos=pos, status=status, remain=remain, progress=progress)


@app.route('/clipper/prev')
def prev():
    coords = json.loads(request.args.get('coords'))
    samples = getsamples()
    pos = getpos()
    imgtotal = len(samples)
    if pos > 0:
        pos -= 1
        updatepos(pos)

    try:
        imgsrc = samples[pos]['filepath']
    except IndexError as e:
        imgsrc = None

    status = getstatus(pos)
    remain = imgtotal - pos
    progress = 1.0*pos/imgtotal*100
    return jsonify(imgsrc=imgsrc, pos=pos, status=status, remain=remain, progress=progress)


@app.route('/clipper/progress', methods=['POST'])
def updateprogress():
    pos = json.loads(request.form['pos'])
    app.logger.debug(pos)
    if pos is not None:
        updatepos(pos)

    return jsonify(status=200, message='ok')


@app.route('/clipper/sync', methods=['POST'])
def syncdatabase():
    getsamples(update=True)
    return jsonify(status=200, message='ok')

## main
if __name__ == '__main__':
    port = int(os.environ.get("port", 5000))
    app.run(port = port)