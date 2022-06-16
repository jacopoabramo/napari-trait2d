"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/plugins/guides.html?#widgets

Replace code below according to your needs.
"""

from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QWidget, 
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QDoubleSpinBox,
    QSpinBox
)
from dataclasses import dataclass, fields

@dataclass
class TRAIT2DParams:
    SEF_sigma : int = 6
    SEF_threshold : int = 4
    SEF_min_peak : float = 0.2
    patch_size : int = 10
    link_max_dist : int = 15
    link_frame_gap : int = 15
    min_track_length : int = 1
    resolution : int = 1
    frame_rate : int = 100 


class NTRAIT2D(QWidget):
    def __init__(self, viewer: Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.params = TRAIT2DParams()
        self.mainLayout = QVBoxLayout()

        self.fileLayout = QFormLayout()
        self.loadFileButton = QPushButton("Select")
        self.fileLayout.addRow("Load parameter file (*.csv, *.json)", self.loadFileButton)

        self.paramLayout = QFormLayout()
        for field in fields(self.params):
            attr = getattr(self.params, field.name)
            if type(attr) == int:
                spinBox = QSpinBox()
            else:
                spinBox = QDoubleSpinBox()
            spinBox.setValue(attr)
            self.paramLayout.addRow(field.name, spinBox)

        self.mainLayout.addLayout(self.fileLayout)
        self.mainLayout.addLayout(self.paramLayout)
        self.setLayout(self.mainLayout)