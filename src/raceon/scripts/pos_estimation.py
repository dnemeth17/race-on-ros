#!/usr/bin/python3

## Get image data
## to the "imu_data" topic

import rospy
from sensor_msgs.msg import Image
from geometry_msgs.msg import Pose2D

# Dependencies for estimation
import numpy as np
from scipy.signal import find_peaks, butter, filtfilt

class PosEstimator():
    
    def __init__(self):
        self.topic_name_camera = rospy.get_param("~topic_name_camera", "/camera")
        self.topic_name_pos = rospy.get_param("~topic_name_position", "/position")
        self.frame_name = rospy.get_param("~frame_name", "camera")
        self.camera_width = rospy.get_param("~camera_width", 640)
        self.camera_height = rospy.get_param("~camera_height", 480)
        
        # Parameters for estimation
        self.scan_line = rospy.get_param("~scan_line", 170)
        self.peak_thres = rospy.get_param("~peak_threshold", 170)
        self.track_width = rospy.get_param("~track_width", 600)
        self.camera_center = self.camera_width // 2
        
        self.butter_b, self.butter_a = butter(3, 0.1)
    
    def start(self):
        self.sub_camera = rospy.Subscriber(self.topic_name_camera, Image, self.camera_callback)
        self.pub_pos = rospy.Publisher(self.topic_name_pos, Pose2D, queue_size=10)
        rospy.spin()

    def camera_callback(self, img_msg):
        I = np.array(img_msg.data)
        line_pos = self.pos_estimate(I)
        
        pos_msg = Pose2D()
        pos_msg.position.x = line_pos
        self.pub_pos.publish(pos_msg)
        
    def pos_estimate(self, I):

        # Select a horizontal line in the middle of the image
        L = I[self.scan_line, :]

        # Smooth the transitions so we can detect the peaks 
        Lf = filtfilt(self.butter_b, self.butter_a, L)

        # Find peaks which are higher than 0.5
        peaks, p_val = find_peaks(Lf, height=self.peak_thres)

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

        # Evaluate the line position
        if line_left and line_right:
            line_pos    = (line_left + line_right ) // 2
            
            self.track_width = line_right - line_left
        elif line_left and not line_right:
            line_pos    = line_left + int(self.track_width / 2)
            
        elif not line_left and line_right:
            line_pos    = line_right - int(self.track_width / 2)
            
        else:
            rospy.loginfo("no line")

        return line_pos

if __name__ == "__main__":
    rospy.init_node("pos_estimation")
    estimator = PosEstimator()
    try:
        estimator.start()
    except rospy.ROSInterruptException:
        pass
