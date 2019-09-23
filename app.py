from flask import Flask, render_template, request, redirect, url_for, jsonify
import os, pickle, shutil

#from google.appengine.api import app_identity
#import cloudstorage as gcs

import similar_engine
from pytube import YouTube as yt

from rq import Queue
from rq.job import Job
from worker import conn

import cv2, numpy, skimage
import time, math


app = Flask(__name__)
app.config.from_object(os.environ["APP_SETTINGS"])

q=Queue(connection=conn)

def get_distance(target, candidate):
    target = ~cv2.Canny(target, 100, 100)
    candidate = ~cv2.Canny(candidate, 100, 100)
    return numpy.linalg.norm(target-candidate) + \
        skimage.measure.compare_nrmse(target, candidate) + \
        skimage.measure.compare_ssim(target, candidate)

#last dist is used to prevent consecutive frames from being extracted
def update_order(ordering, dist, val, name, last_dist, cut_margin=0.005,fps=30):
    if ordering[-1] and dist > ordering[-1][0]:
        return False
    else:
        for i in range(len(ordering)):
            if (ordering[i] is None or ordering[i][0]>dist) and \
                    (last_dist is None or 1.0*abs(last_dist-dist)/last_dist > cut_margin):
                #cv2.imwrite("candidate.png",~cv2.Canny(val,100,100))
                ordering.insert(i,(dist,"%06d"%name ,name/fps,val,~cv2.Canny(val, 100, 100)))
                ordering.pop()
                return True
        return False


#https://stackoverflow.com/questions/30136257/how-to-get-image-from-video-using-opencv-python
def extract_top_frames(video, path_output_dir, target, top_n, pulls_per_second=2):
    ordering=[None]*top_n

    vidcap = cv2.VideoCapture(video)
    fps = vidcap.get(cv2.CAP_PROP_FPS);

    cur_frame = 0
    extracted_frames = 0

    #ensure no consecutive frames are returned
    last_dist = None

    while vidcap.isOpened():
        success = vidcap.grab()
        if success and cur_frame % (math.ceil(fps/pulls_per_second)) == 0:
            success, image = vidcap.retrieve()
            if extracted_frames==0:
                h,w,d = image.shape
                target = cv2.resize(target,(int(w),int(h)))
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if success:
                dist = get_distance(image, target)
                update_order(ordering, dist, image, cur_frame, last_dist)
                extracted_frames += 1
            last_dist = dist
            cur_frame +=1
        elif success:
            cur_frame += 1
        else:
            break
    cv2.destroyAllWindows()
    vidcap.release()
    return ordering

def run_extractor(target_img, video, path_output_dir, num_results=10):
    app.logger.debug(target_img)
    app.logger.debug(os.getcwd())
    app.logger.debug(os.listdir("."))
    app.logger.debug(os.listdir("./static"))
    app.logger.debug(os.listdir("./static/in"))
    app.logger.debug(os.listdir("./videos"))
    app.logger.debug(os.listdir("/tmp"))

    target = cv2.imread(target_img)
    target = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    top_n_frames = extract_top_frames(video, "out", target, num_results)

    for img_ind in range(len(top_n_frames)):
        if top_n_frames[img_ind] is None:
            break
        #print ("Rank %d: Frame %s with distance %f"%(img_ind, top_n_frames[img_ind][1], top_n_frames[img_ind][0]))
        cv2.imwrite(os.path.join(path_output_dir, '%s.png'%(top_n_frames[img_ind][1])), top_n_frames[img_ind][3])
        cv2.imwrite(os.path.join(path_output_dir, '%s_proc.png'%(top_n_frames[img_ind][1])), top_n_frames[img_ind][4])
    return top_n_frames

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
        file.save('/tmp/'+file.filename)

        bucket_name = 'framefinder'

        write_retry_params = gcs.RetryParams(backoff_factor=1.1)
        gcs_file = gcs.open(filename,
                      'w',
                      content_type='text/plain',
                      options={'x-goog-meta-foo': 'foo',
                               'x-goog-meta-bar': 'bar'},
                      retry_params=write_retry_params)
        gcs_file.write('abcde\n')
        gcs_file.write('f'*1024*4 + '\n')
        gcs_file.close()


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
        app.logger.debug("accessing/static/in/%s"%(file.filename))
        job = q.enqueue_call(func = run_extractor, \
            args=("./static/in/%s"%(file.filename), "videos/%s.mp4"%url_ext, "static/out/%s"%url_ext))
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