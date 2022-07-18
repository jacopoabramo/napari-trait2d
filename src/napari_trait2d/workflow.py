import numpy as np
import napari_trait2d.detection as detection
import napari_trait2d.tracking as tracking
from skimage.util import invert, img_as_ubyte
from napari_trait2d.common import (
    TRAIT2DParams,
    Point,
    SpotEnum
)

def run_tracking(video: np.ndarray, params: TRAIT2DParams) -> list:
    
    # rearrange the data for saving
    # first element of the list
    # is a list of header names
    tracking_data = [['X', 'Y', 'Track ID', 't']]
    
    if video.dtype != np.uint8:
        video = (video - np.min(video))/(np.max(video) - np.min(video))
        video = img_as_ubyte(video)

    tracking_length = min(params.end_frame + 1, video.shape[0])
    
    tracker = tracking.Tracker(params)

    # frame to frame detection and linking loop 
    for frame_idx in range(params.start_frame, tracking_length):
        
        # detect particles on specific frame
        # using stored parameters
        frame = video[frame_idx]
        if params.spot_type == SpotEnum.DARK:
            frame = invert(frame)
        centers = detection.detect(frame, params)

        # track detected particles
        tracker.update(centers, frame_idx)
    
    # set complete tracks found so far
    tracker.complete_tracks.update(tracker.tracks)

    new_frame_trace = []
    new_trace = []

    for track_id, track in tracker.complete_tracks.items():
        if len(track.trace) >= params.min_track_length:
            old_position = track.trace_frame[0]
            for frame_idx in range(track.trace_frame[0], track.trace_frame[-1] + 1):
                # we reconstruct the point trace
                # and try to fill the gaps between frames
                new_frame_trace.append(frame_idx)
                frame_idx_old = track.trace_frame[old_position]

                # if frame is already present in the frame trace,
                # just add it to the new list and add the point too
                if frame_idx_old == frame_idx:
                    new_trace.append(track.trace[old_position])
                    old_position += 1
                else:
                    # if the frame position is incoherent with the frame trace,
                    # we try again in finding the particle on the current frame
                    # but using as a reference the point at old_position
                    frame = video[frame_idx]
                    trace_point = track.trace[old_position]
                    
                    subpix = detection.radial_symmetry_centre(
                        detection.get_patch(frame, trace_point, params.patch_size, full_search=True)
                    )

                    if (subpix < Point(params.patch_size, params.patch_size) and
                        subpix >= Point(0, 0)):
                        new_trace.append(
                        Point(
                            subpix.x + int(trace_point.x - params.patch_size/2), 
                            subpix.y + int(trace_point.y - params.patch_size/2))
                        )
                    else:
                        # otherwise use previous point
                        new_trace.append(track.trace[old_position])
            
            for point, frame_idx in zip(new_trace, new_frame_trace):
                tracking_data.append(
                    # we are swapping x and y
                    # due to how the video stack is arranged
                    [
                        point.y*params.resolution,
                        point.x*params.resolution,
                        track_id,
                        frame_idx*params.frame_rate
                    ]
                )
            
            # clear lists for next iteration
            new_frame_trace.clear()
            new_trace.clear()
    
    return tracking_data