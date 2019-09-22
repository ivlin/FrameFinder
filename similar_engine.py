import cv2, numpy, skimage
import os, time, math

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
    target = cv2.imread(target_img)
    target = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    app.logger.info("\n\ntarget loaded")
    top_n_frames = extract_top_frames(video, "out", target, num_results)
    app.logger.info("\n frames extracted")
    for img_ind in xrange(len(top_n_frames)):
        if top_n_frames[img_ind] is None:
            break
        #print ("Rank %d: Frame %s with distance %f"%(img_ind, top_n_frames[img_ind][1], top_n_frames[img_ind][0]))
        cv2.imwrite(os.path.join(path_output_dir, '%s.png'%(top_n_frames[img_ind][1])), top_n_frames[img_ind][3])
        cv2.imwrite(os.path.join(path_output_dir, '%s_proc.png'%(top_n_frames[img_ind][1])), top_n_frames[img_ind][4])
    return top_n_frames

if __name__=="__main__":
    run_extractor("out/target1.jpg","stance.mp4","out")