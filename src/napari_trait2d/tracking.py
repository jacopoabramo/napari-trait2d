import numpy as np
from scipy.optimize import linear_sum_assignment
from napari_trait2d.common import TRAIT2DParams, Point
from dataclasses import dataclass, field

@dataclass
class Track:
    track_id : int
    first_point: Point
    first_frame_idx: int
    skipped_frames: int = 0
    trace : list = field(init=False)
    trace_frame : list = field(init=False)

    def __post_init__(self):
        self.trace = [self.first_point]
        self.trace_frame = [self.first_frame_idx]

class Tracker:
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
                # track_id starts from 1
                cost[track_id - 1][point_id] = distance
        
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
    
    def update(self, detections: list, frame_idx: int):
        """ Concatenates found particles in frame into existing tracks,
        otherwise adds a new track into a dictionary container.

        Args:
            detections (list): list of Point objects with detected particle centers.
            frame_idx (int): index of frame in video in which the detection occurred.
        """

        # fill dictionary with initial tracks if dictionary is empty
        if not self.tracks:
            self.tracks = {
                idx + 1 : Track(first_point=point, first_frame_idx=frame_idx, track_id=idx + 1)
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
                # track id count starts from 1
                track_id = idx + 1
                if (assignment != -1):
                    # check with the cost distance threshold and unassign if cost is high
                    if (cost[idx][assignment] > self.params.link_max_dist):
                        assignment = -1
                        self.tracks[track_id].skipped_frames += 1

                    else:  # add the detection to the track
                        self.tracks[track_id].trace.append(detections[assignment])
                        self.tracks[track_id].trace_frame.append(frame_idx)
                        self.tracks[track_id].skipped_frames = 0
                else:
                    self.tracks[track_id].skipped_frames += 1
            
            # unnasigned detections
            unassigned_detections = [index for index in range(len(detections)) if index not in assignments]

            # start new tracks
            if(len(unassigned_detections) != 0):
                new_tracks = {
                    idx + self.track_id_count + 1: Track(first_point=detections[idx], 
                                                    first_frame_idx=frame_idx,
                                                    track_id = idx + self.track_id_count + 1)
                    for idx in range(len(unassigned_detections))
                }
                self.track_id_count += len(new_tracks)
                self.tracks.update(new_tracks)
            
            # remove tracks which have too many skipped frames
            for track_idx, track in self.tracks.items():
                if track.skipped_frames > self.params.link_frame_gap:
                    del self.tracks[track_idx]