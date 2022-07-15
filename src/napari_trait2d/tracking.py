import numpy as np
from scipy.optimize import linear_sum_assignment
from napari_trait2d.common import TRAIT2DParams

class Track(object):

    def __init__(self, first_point, first_frame, track_id_count):
        self.track_id = track_id_count  # track identification number
        self.trace_frame = [first_frame]  # index of frames in which particle is detected
        self.skipped_frames = 0  # number of skipped frames due to undetected particles
        self.trace = [first_point]  # list of detected points linked together
    
    def __str__(self):
        return f"{self.trace_frame}, {self.trace}"


class Tracker(object):
    """
    Links detected objects between frames
    """

    def __init__(self, parameters: TRAIT2DParams) -> None:
        self.params = parameters
        self.tracks = []
        self.track_id_count = 0
        self.complete_tracks = []

    def cost_calculation(self, detections):
        '''
        calculates cost matrix based on the distance
        '''
        N = len(self.tracks)
        M = len(detections)
        cost = np.zeros((N, M))   # Cost matrix
        for i in range(len(self.tracks)):
            for j in range(len(detections)):
                diff = np.array(self.tracks[i].trace[len(self.tracks[i].trace)-1]) - np.array(detections[j])
                distance = np.sqrt((diff[0])**2 + (diff[1])**2)
                cost[i][j] = distance
        cost_array = np.asarray(cost)
        cost_array[cost_array > self.params.link_max_dist] = 10000
        cost = cost_array.tolist()
        return cost

    def assign_detection_to_tracks(self, cost):
        '''
        Assignment based on Hungarian Algorithm
        https://en.wikipedia.org/wiki/Hungarian_algorithm
        '''

        N = len(self.tracks)
        assignment = [-1 for _ in range(N)]
        row_ind, col_ind = linear_sum_assignment(cost)
        for i in range(len(row_ind)):
            assignment[row_ind[i]] = col_ind[i]

        return assignment

    def update(self, detections, frame):
        '''
        Main linking function
        '''

        # create tracks if no tracks found
        if (len(self.tracks) == 0):
            for detection in detections:
                track = Track(first_point=detection, first_frame=frame, track_id_count=self.track_id_count)
                self.track_id_count += 1
                self.tracks.append(track)

        # tracking the targets if there were tracks before
        else:
            
            # Calculate cost using sum of square distance between predicted vs detected centroids
            cost = self.cost_calculation(detections)

            # assigning detection to tracks
            assignment = self.assign_detection_to_tracks(cost)

            # add the position to the assigned tracks and detect annasigned tracks
            un_assigned_tracks = []

            for i in range(len(assignment)):
                if (assignment[i] != -1):
                    # check with the cost distance threshold and unassign if cost is high
                    if (cost[i][assignment[i]] > self.params.link_max_dist):
                        assignment[i] = -1
                        un_assigned_tracks.append(i)
                        self.tracks[i].skipped_frames += 1

                    else:  # add the detection to the track
                        self.tracks[i].trace.append(detections[assignment[i]])
                        self.tracks[i].trace_frame.append(frame)
                        self.tracks[i].skipped_frames = 0

                else:
                    un_assigned_tracks.append(i)
                    self.tracks[i].skipped_frames += 1

            # Unnasigned detections
            un_assigned_detects = []
            for i_det in range(len(detections)):
                if i_det not in assignment:
                    un_assigned_detects.append(i_det)

            # Start new tracks
            if(len(un_assigned_detects) != 0):
                for i in range(len(un_assigned_detects)):
                    track = Track(detections[un_assigned_detects[i]], frame,
                                  self.track_id_count)

                    self.track_id_count += 1
                    self.tracks.append(track)

            del_tracks = []  # list of tracks to delete

            # remove tracks which have too many skipped frames
            for i in range(len(self.tracks)):
                if (self.tracks[i].skipped_frames > self.params.link_frame_gap):
                    del_tracks.append(i)

            # delete track
            if len(del_tracks) > 0:

                val_compensate_for_del = 0
                for id in del_tracks:
                    new_id = id-val_compensate_for_del

                    self.complete_tracks.append(self.tracks[new_id])
                    del self.tracks[new_id]
                    val_compensate_for_del += 1

class NewTracker:
    def __init__(self, parameters: TRAIT2DParams) -> None:
        self.params = parameters
        self.tracks : dict = {}
        self.track_id_count : int = 0
        self.complete_tracks : dict = {}
    
    def cost_calculation(self, detections: list) -> list:
        '''
        Calculates cost matrix based on the distance.
        '''
        N = len(self.tracks)
        M = len(detections)
        cost = np.zeros((N, M)) # Cost matrix
        for track_id, track in self.tracks.items():
            current_track_trace : list = track.trace
            for point_id, point in enumerate(detections):
                # get the difference between the last point detected in the stack trace and the new detected particle
                diff = np.array(current_track_trace[len(current_track_trace) - 1]) - np.array(point)

                # calculate euclidean distance
                distance = np.sqrt((diff[0])**2 + (diff[1])**2)

                # assign value in the cost matrix
                cost[track_id][point_id] = distance
        
        # flat array and filter out values which are greater 
        # than the minimum desired distance
        cost_array = np.asarray(cost)
        cost_array[cost_array > self.params.link_max_dist] = 100_000 # TODO: this should be a value like NaN
        return cost_array.tolist()

    def assign_detection_to_tracks(self, cost):
        '''
        Assignment based on Hungarian Algorithm
        https://en.wikipedia.org/wiki/Hungarian_algorithm
        '''

        N = len(self.tracks)
        assignment = [-1 for _ in range(N)]
        row_ind, col_ind = linear_sum_assignment(cost)
        for i in range(len(row_ind)):
            assignment[row_ind[i]] = col_ind[i]

        return assignment
    
    def update(self, detections: list, frame: int):
        """ Concatenates found particles in frame into existing tracks,
        otherwise adds a new track into a dictionary container.

        Args:
            detections (list): list of Point objects with detected particle centers.
            frame (int): index of frame in video in which the detection occurred.
        """

        # fill dictionary with initial tracks if dictionary is empty
        if not self.tracks:
            self.tracks = {
                idx : Track(first_point=point, first_frame=frame, track_id_count=idx)
                for idx, point in enumerate(detections)
            }
            self.track_id_count += len(self.tracks)
        else:
            # try to concatenate newly found particles into existing tracks
            # first calculate cost using sum of square distance between predicted vs detected centroids
            # then assign detection to tracks
            cost = self.cost_calculation(detections)
            assignments = self.assign_detection_to_tracks(cost)

            for idx, assignment in enumerate(assignments):
                if (assignment != -1):
                    # check with the cost distance threshold and unassign if cost is high
                    if (cost[idx][assignment] > self.params.link_max_dist):
                        assignment = -1
                        self.tracks[idx].skipped_frames += 1

                    else:  # add the detection to the track
                        self.tracks[idx].trace.append(detections[assignment])
                        self.tracks[idx].trace_frame.append(frame)
                        self.tracks[idx].skipped_frames = 0
                else:
                    self.tracks[idx].skipped_frames += 1
            
            # Unnasigned detections
            unassigned_detections = [index for index in range(len(detections)) if index not in assignments]

            # Start new tracks
            if(len(unassigned_detections) != 0):
                new_tracks = {
                    f"track_{idx + self.track_id_count}": Track(first_point=detections[idx], 
                                                                first_frame=frame,
                                                                track_id_count=self.track_id_count)
                    for idx in range(len(unassigned_detections))
                }
                self.track_id_count += len(new_tracks)
                self.tracks.update(new_tracks)
            
            # remove tracks which have too many skipped frames
            for track_idx, track in self.tracks.items():
                if track.skipped_frames > self.params.link_frame_gap:
                    del self.tracks[track_idx]