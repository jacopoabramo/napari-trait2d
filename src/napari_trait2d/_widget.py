"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/plugins/guides.html?#widgets

Replace code below according to your needs.
"""

import json, csv
import numpy as np
import napari_trait2d.detection as detection
from skimage.util import invert, img_as_ubyte
from napari.viewer import Viewer
from qtpy.QtWidgets import (
    QWidget,
    QFormLayout,
    QPushButton,
    QVBoxLayout,
    QDoubleSpinBox,
    QSpinBox,
    QFileDialog,
)
from superqt import QEnumComboBox
from dataclasses import fields
from dacite import from_dict
from typing import get_type_hints
from napari_trait2d.common import *
from napari_trait2d.tracking import NewTracker

class NTRAIT2D(QWidget):
    def __init__(self, viewer: Viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.params = TRAIT2DParams()
        self.mainLayout = QVBoxLayout()

        self.fileLayout = QFormLayout()
        self.loadFileButton = QPushButton("Select")
        self.fileLayout.addRow(
            "Load parameter file (*.csv, *.json)", self.loadFileButton
        )
        self.widgets = {}

        def build_widget(attr: ParamType):
            widget = None
            attr_type = type(attr)
            if attr_type in [int, float]:
                if attr_type == int:
                    widget = QSpinBox()
                else:
                    widget = QDoubleSpinBox()
                widget.setRange(0, 2 ** (16) - 1)
                widget.setValue(attr)
                signal = widget.valueChanged
            elif attr_type == SpotEnum:
                widget = QEnumComboBox(enum_class=SpotEnum)
                signal = widget.currentEnumChanged
            else:
                raise TypeError("Parameter type is unsupported in widget selection.")
            return widget, signal

        self.paramLayout = QFormLayout()
        for field in fields(self.params):
            attr = getattr(self.params, field.name)
            self.widgets[field.name], signal = build_widget(attr)
            self.paramLayout.addRow(field.name, self.widgets[field.name])

            signal.connect(
                lambda _, name=field.name: self._update_field(name=name)
            )

        self.runButton = QPushButton("Run tracking")

        self.mainLayout.addLayout(self.fileLayout)
        self.mainLayout.addLayout(self.paramLayout)
        self.mainLayout.addWidget(self.runButton)
        self.setLayout(self.mainLayout)

        self.loadFileButton.clicked.connect(self._on_load_clicked)
        self.runButton.clicked.connect(self._on_run_button_clicked)

    def _update_field(self, name: str):
        if type(getattr(self.params, name)) in [int, float]:
            setattr(self.params, name, self.widgets[name].value())
        else: # for QEnumComboBox type
            setattr(self.params, name, self.widgets[name].currentEnum())

    def _on_load_clicked(self):

        filepath, _ = QFileDialog.getOpenFileName(
            caption="Load TRAIT2D parameters",
            filter="Datafiles (*.csv *.json)",
        )
        if filepath:
            new_data = {}
            if filepath.endswith(".json"):
                with open(filepath, "r") as file:
                    new_data = json.load(file)
            elif filepath.endswith(".csv"):
                with open(filepath, newline="") as file:
                    reader = csv.reader(file, delimiter=",")
                    for idx, row in enumerate(reader):
                        if len(row) > 2:
                            raise ValueError(
                                f"Too many values in CSV row {idx}"
                            )
                        new_data[row[0]] = row[1]
            try:
                new_data = {
                    key_hint: hint(value)
                    for key_hint, hint in get_type_hints(TRAIT2DParams).items()
                    for key_data, value in new_data.items()
                    if key_hint == key_data
                }
                self.params = from_dict(TRAIT2DParams, new_data)
            except Exception as e:
                raise Exception(e)
            for field in fields(self.params):
                for idx in range(self.paramLayout.rowCount()):
                    if (field.name == self.paramLayout.itemAt(idx, QFormLayout.ItemRole.LabelRole).widget().text()):
                        widget = self.paramLayout.itemAt(idx, QFormLayout.ItemRole.FieldRole).widget()
                        attr = getattr(self.params, field.name)
                        if type(attr) in [int, float]:
                            widget.setValue(attr)
                        else:
                            widget.setCurrentEnum(attr)
                        break
    
    def _on_run_button_clicked(self):

        for layer in self.viewer.layers.selection:
            video : np.ndarray = layer.data
            tracker = NewTracker(self.params)

            if video.dtype != np.uint8:
                video = (video - np.min(video))/(np.max(video) - np.min(video))
                video = img_as_ubyte(video)

            tracking_length = min(self.params.end_frame, video.shape[0])

            # frame to frame detection and linking loop 
            for frame_idx in range(self.params.start_frame, tracking_length):
                
                # detect particles on specific frame
                # using stored parameters
                frame = video[frame_idx]
                if self.params.spot_type == SpotEnum.DARK:
                    frame = invert(frame)
                centers = detection.detect(frame, self.params)

                # track detected particles
                tracker.update(centers, frame_idx)
            
            # set complete tracks found so far
            tracker.complete_tracks.update(tracker.tracks)
            
            # rearrange the data for saving
            # first element of the list
            # is a list of header names
            tracking_data = [['X', 'Y', 'Track ID', 't']]

            for track_id, track in tracker.complete_tracks.items():
                if len(track.trace) >= self.params.min_track_length:
                    new_frame_trace = []
                    new_trace = []
                    frame_position = 0
                    for frame_idx, trace_point in zip(track.trace_frame, track.trace):
                        # if frame is already present in the frame trace,
                        # just add it to the new list and add the point too
                        if frame_position == frame_idx:
                            new_frame_trace.append(frame_idx)
                            new_trace.append(trace_point)
                            frame_position += 1
                        else:
                            # if the frame position is incoherent with the frame trace,
                            # we try again in finding the particle
                            new_frame_trace.append(frame_idx)
                            frame = video[frame_idx]
                            
                            x, y = detection.radialsym_centre(
                                detection.get_patch(frame, trace_point, self.params.patch_size)
                            )
                            subpix = Point(x, y)

                            if (subpix.y < self.params.patch_size and 
                                subpix.x < self.params.patch_size and 
                                subpix.y >= 0 and 
                                subpix.x >= 0):
                                new_trace.append(
                                Point(
                                    subpix.x + int(trace_point.x - self.params.patch_size/2), 
                                    subpix.y + int(trace_point.y - self.params.patch_size/2))
                                )
                            else:
                                # otherwise use previous point
                                new_trace.append(track.trace[frame_position])
                    tracking_data.append(
                        [
                            [point.x, point.y, track_id, frame*track_id, frame_idx*self.params.frame_rate] 
                            for point in new_trace
                            for frame_idx in new_frame_trace
                        ]
                    )
            
            filepath, _ = QFileDialog.getSaveFileName(
                caption="Save TRAIT2D tracks",
                filter="CSV (*.csv)",
            )
            if filepath:   
                if not(filepath.endswith(".csv")):
                    filepath += ".csv"
        
                
                with open(filepath, 'w') as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerows(tracking_data)
        
                csv_file.close()