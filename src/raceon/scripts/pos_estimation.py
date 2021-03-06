#!/usr/bin/python3

## Get image data
## to the "imu_data" topic

import rospy
from sensor_msgs.msg import Image, CompressedImage
from geometry_msgs.msg import Pose
from raceon.msg import TrackPosition
from std_msgs.msg import Int32

# Dependencies for estimation
import cv2
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt
from skimage.color import rgb2gray





class PosEstimator():
    
    def __init__(self):
        self.topic_name_camera_image = rospy.get_param("topic_name_camera_image", "camera/image")
        self.topic_name_camera_image_compressed = rospy.get_param("topic_name_camera_image_compressed", "camera/image/compressed")
        self.topic_name_pos_err = rospy.get_param("topic_name_position_error", "position/error")
        self.topic_name_pos_track = rospy.get_param("topic_name_position_track", "position/track")
        self.frame_name = rospy.get_param("frame_name", "camera")
        
        # Tooglers
        self.use_compressed_image = rospy.get_param("~use_compressed_image", True)
        
        # Parameters for estimation
        self.scan_line = rospy.get_param("~scan_line", 170)
        self.peak_thres = rospy.get_param("~peak_threshold", 170)
        self.track_width = rospy.get_param("~track_width", 600)
        self.camera_center = rospy.get_param("~camera_center", 320)
        
        self.butter_b, self.butter_a = butter(3, 0.1)
        
        self.previous_left = 150
        self.previous_right = 550
        self.previous_error = 0;
        self.error_array = []
        
    
    def start(self):
        
        if self.use_compressed_image:
            self.sub_camera = rospy.Subscriber(self.topic_name_camera_image_compressed, CompressedImage, self.image_compressed_callback)
        else:
            self.sub_camera = rospy.Subscriber(self.topic_name_camera_image, Image, self.image_callback)
            
        self.pub_pos_err = rospy.Publisher(self.topic_name_pos_err, Pose, queue_size=10)
        self.pub_pos_track = rospy.Publisher(self.topic_name_pos_track, TrackPosition, queue_size=10)
        self.pub_line_left = rospy.Publisher("line/left", Int32, queue_size=10)
        self.pub_line_right = rospy.Publisher("line/right", Int32, queue_size=10)
        self.pub_middle_error = rospy.Publisher("middle/error", Int32, queue_size=10)
        self.pub_scan_line = rospy.Publisher("scan_line", Int32, queue_size=10)
        rospy.spin()

    def image_compressed_callback(self, img_msg):
        np_arr = np.frombuffer(img_msg.data, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        self.process_image(img)

    def image_callback(self, img_msg):
        width = img_msg.width
        height = img_msg.height
        
        np_arr = np.frombuffer(img_msg.data, dtype=np.uint8)
        img = np_arr.reshape((height, width, 3))
        self.process_image(img)
    
    def process_image(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        rospy.loginfo("Image with shape {:s} received. (max, min)=({:d}, {:d})".format(str(gray.shape), gray.min(), gray.max()))        
        line_pos = self.camera_center - self.pos_estimate(gray)
        
        self.error_array.append(line_pos)
        
        self.previous_error = line_pos;
        
        self.pub_middle_error.publish(line_pos)
        
        rospy.loginfo("Estimated line_pos = " + str(line_pos))
        
        pos_msg = Pose()
        pos_msg.position.x = line_pos
        self.pub_pos_err.publish(pos_msg)
    
    def pos_estimate(self, I):
        scan_line = self.scan_line;
        if self.previous_error:
            scan_line += int((abs(self.previous_error) / 100) * 50);
        if scan_line > self.scan_line + 150:
            scan_line = self.scan_line + 150;
        self.pub_scan_line.publish(scan_line);
        # Select a horizontal line in the image
        L = I[scan_line, :]

        # Smooth the transitions so we can detect the peaks 
        Lf = filtfilt(self.butter_b, self.butter_a, L)

        # Find peaks which are higher than 0.5
        peaks, p_val = find_peaks(Lf, height=self.peak_thres)
        
        rospy.loginfo(peaks)

        line_pos    = self.camera_center
        line_left   = None
        line_right  = None
        peaks_left  = peaks[peaks < self.camera_center]
        peaks_right = peaks[peaks > self.camera_center]
        
        # Peaks on the left
        if peaks_left.size:
            line_left = peaks_left.max()

        # Peaks on the right
        if peaks_right.size:
            line_right = peaks_right.min()
        
        # Log track position
        track_msg = TrackPosition()
        track_msg.left = 0 if line_left == None else int(line_left)
        track_msg.right = 0 if line_right == None else int(line_right)
        self.pub_pos_track.publish(track_msg)
        
        #self.pub_line_left.publish(left_pos)
        #self.pub_line_right.publish(right_pos)
        

        # Evaluate the line position
        if line_left and line_right:
            line_pos    = (line_left + line_right ) // 2
            self.track_width = line_right - line_left
            self.previous_left = line_left
            self.previous_right = line_right

        elif line_left and not line_right:
            line_right = line_left + self.track_width
            line_pos    = (line_left + line_right ) // 2
            self.previous_left = line_left

        elif not line_left and line_right:
            line_left = line_right - self.track_width
            line_pos    = (line_left + line_right ) // 2
            self.previous_right = line_right
        else:
            if self.previous_left != -1 and self.previous_right != -1:
                line_pos = (self.previous_left + self.previous_right ) // 2   
            rospy.loginfo("no line")
        
        
        self.pub_line_left.publish(line_left)
        self.pub_line_right.publish(line_right)
        return line_pos

if __name__ == "__main__":
    rospy.init_node("pos_estimation")
    estimator = PosEstimator()
    try:
        estimator.start()
    except rospy.ROSInterruptException:
        pass
