"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/plugins/guides.html?#widgets

Replace code below according to your needs.
"""
import json, csv
import numpy as np
import napari_trait2d.workflow as workflow
from napari.layers.image.image import Image
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
from napari_trait2d.common import (
    TRAIT2DParams,
    SpotEnum,
    ParamType
)

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

        self.trackButton = QPushButton("Track particles")
        self.trackAndStoreButton = QPushButton("Track and store")

        self.mainLayout.addLayout(self.fileLayout)
        self.mainLayout.addLayout(self.paramLayout)
        self.mainLayout.addWidget(self.trackButton)
        self.mainLayout.addWidget(self.trackAndStoreButton)
        self.setLayout(self.mainLayout)

        self.loadFileButton.clicked.connect(self._on_load_clicked)
        self.trackButton.clicked.connect(lambda: self._on_run_tracking_clicked(False))
        self.trackAndStoreButton.clicked.connect(lambda: self._on_run_tracking_clicked(True))

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
    
    def _on_run_tracking_clicked(self, store: bool):

        for layer in self.viewer.layers.selection:
            
            if type(layer) == Image:
                tracking_data = workflow.run_tracking(layer.data, self.params)
                if store:
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
                else:
                    # we create a Track layer with the 
                    # detected coordinates;
                    # data is arranged as follows: ['X', 'Y', 'Track ID', 't']
                    # we must reshape it as ['Track ID', 't', 'Y', 'X']
                    # the 't' parameter is multiplied for the parameters frame rate
                    # so we must divide it
                    points = np.array([
                        [
                            data[2] - 1, int(data[3]/self.params.frame_rate), data[1], data[0]
                        ]
                        for data in tracking_data 
                        if type(data[0]) != str and type(data[1]) != str
                    ])

                    self.viewer.add_tracks(
                        data=points,
                        name=layer.name + "_tracks",
                        tail_width=3,
                        tail_length=points.shape[0]
                    )