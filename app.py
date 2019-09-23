from flask import Flask, render_template, request, redirect, url_for, jsonify
import os, pickle, shutil

import similar_engine
from pytube import YouTube as yt

from rq import Queue
from rq.job import Job
from worker import conn

app = Flask(__name__)
app.config.from_object(os.environ["APP_SETTINGS"])

q=Queue(connection=conn)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['png','jpg','jpeg']

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/custom/<ext>")
def custom_results():
    pass

@app.route("/youtube",methods=["POST"])
def youtube():
    #print request
    file = request.files['target']
    if file.filename == '':
        #print 'No selected file'
        #flash('No selected file')
        return redirect(url_for('index'))
    if file and allowed_file(file.filename):
        file = request.files['target']
        file.save('static/in/'+file.filename)
        url_ext = request.form['yt_url']
        url_ext = url_ext[url_ext.find("v=")+2:]
        if url_ext.find("/") >= 0:
            url_ext = url_ext[:url_ext.find("/")]

        #print url_ext
        yt('http://youtube.com/watch?v=%s'%url_ext).streams.filter(subtype='mp4').first().download("./videos",filename=url_ext)
        try:
            os.mkdir("static/out/%s"%url_ext)
        except:
            pass
        job = q.enqueue_call(func = similar_engine.run_extractor, \
            args=("static/in/%s"%(file.filename), "videos/%s.mp4"%url_ext, "static/out/%s"%url_ext))
        return redirect(url_for("get_results",job_key=job.get_id(),ext=url_ext,target=file.filename))
        #return render_template("wait.html",joburl="http://localhost:8000/results/%s/%s/%s"%(str(job.get_id()), url_ext, file.filename))
        #return redirect(url_for('youtube_results',ext=url_ext,target=file.filename))


'''
|- static - contains served images including the original image
|- static/out/ext - contains extracted images
|- videos - temp, used only for intermediary processing
'''
@app.route("/youtube/<ext>/<target>")
def youtube_results(ext,target):
    yt('http://youtube.com/watch?v=%s'%ext).streams.filter(subtype='mp4').first().download("./videos",filename=ext)

    results = similar_engine.run_extractor("static/in/%s"%(target), "videos/"+ext+".mp4", "static/out/%s"%ext)
    app.logger.debug("\nframes extracted")

    try:
        os.mkdir("static/out/%s"%ext)
        results = similar_engine.run_extractor("static/in/%s"%(target), "videos/"+ext+".mp4", "static/out/%s"%ext)
        with open("static/out/%s/results"%ext,"wb") as f:
            pickle.dump(results,f)
    except:
        with open("static/out/%s/results"%ext,"rb") as f:
            results = pickle.load(f)
    return render_template("results.html", youtube_ext=ext, timestamps=results, target=os.path.join('/static/in',target))

@app.route("/results/<job_key>/<ext>/<target>",methods=["GET","POST"])
def get_results(job_key,ext,target):
    app.logger.info("fetching")
    if request.method=="GET":
        job = Job.fetch(job_key, connection=conn)
        if job.is_finished:
            return render_template("results.html", youtube_ext=ext, timestamps=job.result, target=os.path.join('/static/in',target))
        else:
            return render_template("wait.html",joburl="results/%s/%s/%s"%(str(job.get_id()), ext, target))
    else:
        job = Job.fetch(job_key, connection=conn)
        if job.is_finished:
            app.logger.debug("loaded")
            return {}, 200
        else:
            app.logger.debug("not loaded")
            return {}, 404

def clear_code():
    try:
        shutil.rmtree('static/in')
    except:
        pass
    try:
        shutil.rmtree('static/out')
    except:
        pass
    try:
        shutil.rmtree('videos')
    except:
        pass
    try:
        os.mkdir('static/in')
        with open('static/in/init','w') as f:
            f.write('init')
        os.mkdir('static/out')
        with open('static/out/init','w') as f:
            f.write('init')
        os.mkdir('videos')
        with open('videos/init','w') as f:
            f.write('init')
    except:
        pass

@app.route("/clear")
def clear():
    clear_code()
    return redirect(url_for('index'))

if __name__=="__main__":
    app.debug = True
    app.run(host='0.0.0.0', port=8000, use_reloader=True)