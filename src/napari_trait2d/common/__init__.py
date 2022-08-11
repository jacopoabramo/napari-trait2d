from dataclasses import dataclass
from enum import Enum
from typing import Union
from dataclasses import dataclass
from numpy import array

@dataclass(order=True)
class Point:
    x: Union[int, float]
    y: Union[int, float]

    def __array__(self):
        return array([self.x, self.y])

class SpotEnum(Enum):
    DARK = "DARK"
    BRIGHT = "BRIGHT"

@dataclass
class TRAIT2DParams:
    SEF_sigma: int = 6
    SEF_threshold: float = 4.0
    SEF_min_dist: int = 4
    SEF_min_peak: float = 0.2
    patch_size: int = 10
    link_max_dist: int = 15
    link_frame_gap: int = 15
    min_track_length: int = 1
    resolution: int = 1
    frame_rate: int = 100
    start_frame: int = 0
    end_frame: int = 100
    spot_type: SpotEnum = SpotEnum.DARK

    def __post_init__(self):
        self.info = {
            "SEF_sigma": "SEF sigma width (px)",
            "SEF_threshold": "SEF threshold [0.01, 10]",
            "SEF_min_peak": "SEF min. peak value [0.1, 1.0]",
            "SEF_min_dist": "SEF min. distance (px)",
            "patch_size": "Patch size (even, px)",
            "link_max_dist": "Maximum link distance (px)",
            "link_frame_gap": "Maximum allowed frame grap (frame)",
            "min_track_length": "Minimum allowed track length (frame)",
            "resolution": "Resolution (μm per px)",
            "frame_rate": "Framerate (FPS)",
            "start_frame": "Track start frame",
            "end_frame": "Track end frame",
            "spot_type": "Particle type"
        }

ParamType = Union[int, float, SpotEnum]