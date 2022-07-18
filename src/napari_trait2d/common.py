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
    SEF_threshold: float = 4
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
    spot_type: SpotEnum = SpotEnum.BRIGHT

ParamType = Union[int, float, SpotEnum]