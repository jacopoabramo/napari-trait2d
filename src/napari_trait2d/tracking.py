import numpy as np
from scipy.optimize import linear_sum_assignment
from napari_trait2d.common import TRAIT2DParams
from dataclasses import dataclass, field

@dataclass
class Track(object):
    track_id : int
    trace_frame: list
    trace: list
    skipped_frames: int = field(default=0, init=False)


class Tracker(object):
    """
    Links detected objects between frames
    """

    def __init__(self, parameters: TRAIT2DParams) -> None:
        self.params = parameters
        self.tracks : list[Track] = []
        self.track_id_count = 0
        self.complete_tracks: list[Track] = []

    def cost_calculation(self, detections):
        '''
        calculates cost matrix based on the distance
        '''
        N = len(self.tracks)
        M = len(detections)
        cost = np.zeros((N, M))   # Cost matrix
        for i in range(len(self.tracks)):
            for j in range(len(detections)):
                try:
                    diff = np.array(self.tracks[i].trace[len(
                        self.tracks[i].trace)-1]) - np.array(detections[j])
                    distance = np.sqrt((diff[0])**2 + (diff[1])**2)

                    cost[i][j] = distance
                except:
                    pass
        cost_array = np.asarray(cost)
        cost_array[cost_array > self.params.link_max_dist] = 10000
        cost = cost_array.tolist()
        return cost

    def assignDetectionToTracks(self, cost):
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
        main linking function
        '''

        # create tracks if no tracks  found
        if (len(self.tracks) == 0):
            for i in range(len(detections)):
                track = Track(track_id=self.track_id_count, trace_frame=[frame], trace=[detections[i]])
                self.track_id_count += 1
                self.tracks.append(track)

        # tracking the targets if there were tracks before
        else:
            
            # Calculate cost using sum of square distance between predicted vs detected centroids
            cost = self.cost_calculation(detections)

            # assigning detection to tracks
            assignment = self.assignDetectionToTracks(cost)

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
