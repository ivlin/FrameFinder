# FrameFinder

by Ivan Lin

FrameFinder is meant to automatically look through videos for a specific moment for people. If you have hours of uncut video and you are trying to recall a specific moment, draw it out as best you can and use FrameFinder to look for you while you do something else.

# Usage

1.Enter the url for the youtube video you want to search. User-uploaded videos will be allowed soon.
2.Select an image that you want to find in the video. This app is more aimed at hand-drawn images.
3.Receive results of which frames look most like your desired image.

![website][static/example.png]"Visit now"

# How it works
The original intention of this app was to use DeepRanking, a neural network architecture with strong results for ranking image similarity. However, due to time constraints, we we forced to restrict ourselves to simpler methods of comparison - we run OpenCV's Canny Edge detection over every frame, and use distance operations like normalized root mean square of the difference, euclidean distance, and the skimage structural similarity function to determine closeness.

# Future Developments
##Features
- Incorporation of DeepRanking for more accurate image comparison
- Better UI
- For the sake of speed and convenience, we do not compare every frame. The default setting is to only use two frames per second. This will hopefully change as we improve the process.
- Consecutive frames have similar difference indexes from the target image, so frames of the same sequence must be tossed out. Currently, the computer's way of deciding if two frames should be part of the same sequence is unreliable, as is its selection method of which frame should be discarded.