#!/usr/bin/env python
# coding: utf-8

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

import cStringIO, importlib, re, os, sys

from calibre.devices.usbms.driver import debug_print
from calibre.gui2 import show_restart_warning
from calibre.gui2.ui import get_gui
from calibre.utils.config import config_dir, JSONConfig

from PyQt4.Qt import (Qt, QCheckBox, QComboBox, QGridLayout, QGroupBox,
                      QLabel, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget)

plugin_prefs = JSONConfig('plugins/Marvin Mangler')

class ConfigWidget(QWidget):
    '''
    Config dialog for iOS Reader Apps
    '''
    # Location reporting template
    LOCATION_TEMPLATE = "{cls}:{func}({arg1}) {arg2}"

    def __init__(self, plugin_action):
        self.gui = get_gui()
        self.icon = plugin_action.icon
        self.parent = plugin_action
        self.prefs = plugin_prefs
        self.resources_path = plugin_action.resources_path
        self.verbose = plugin_action.verbose
        self._log_location()

        QWidget.__init__(self)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        # ~~~~~~~~ Create the Collections options group box ~~~~~~~~
        self.cfg_collection_options_gb = QGroupBox(self)
        self.cfg_collection_options_gb.setTitle('Collections')
        self.l.addWidget(self.cfg_collection_options_gb)

        self.cfg_collection_options_qgl = QGridLayout(self.cfg_collection_options_gb)
        current_row = 0

        # Add the label/combobox for collections destination
        self.cfg_collections_label = QLabel('Collections')
        self.cfg_collections_label.setAlignment(Qt.AlignLeft)
        self.cfg_collection_options_qgl.addWidget(self.cfg_collections_label, current_row, 0)

        self.collection_field_comboBox = QComboBox(self.cfg_collection_options_gb)
        self.collection_field_comboBox.setObjectName('collection_field_comboBox')
        self.collection_field_comboBox.setToolTip('custom field for Marvin collections')
        self.cfg_collection_options_qgl.addWidget(self.collection_field_comboBox, current_row, 1)
        current_row += 1

        spacerItem1 = QSpacerItem(20, 60, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.cfg_collection_options_qgl.addItem(spacerItem1)

        # ~~~~~~~~ Create the General options group box ~~~~~~~~
        self.cfg_runtime_options_gb = QGroupBox(self)
        self.cfg_runtime_options_gb.setTitle('General options')
        self.l.addWidget(self.cfg_runtime_options_gb)
        self.cfg_runtime_options_qvl = QVBoxLayout(self.cfg_runtime_options_gb)

        # ~~~~~~~~ Progress as percentage checkbox ~~~~~~~~
        self.reading_progress_checkbox = QCheckBox('Show reading progress as percentage')
        self.reading_progress_checkbox.setObjectName('show_progress_as_percentage')
        self.reading_progress_checkbox.setToolTip('Display percentage in Progress column')
        self.cfg_runtime_options_qvl.addWidget(self.reading_progress_checkbox)

        # ~~~~~~~~ Debug logging checkbox ~~~~~~~~
        self.debug_plugin_checkbox = QCheckBox('Enable debug logging for plugin')
        self.debug_plugin_checkbox.setObjectName('debug_plugin_checkbox')
        self.debug_plugin_checkbox.setToolTip('Print plugin diagnostic messages to console')
        self.cfg_runtime_options_qvl.addWidget(self.debug_plugin_checkbox)

        self.debug_libimobiledevice_checkbox = QCheckBox('Enable debug logging for libiMobileDevice')
        self.debug_libimobiledevice_checkbox.setObjectName('debug_libimobiledevice_checkbox')
        self.debug_libimobiledevice_checkbox.setToolTip('Print libiMobileDevice diagnostic messages to console')
        self.cfg_runtime_options_qvl.addWidget(self.debug_libimobiledevice_checkbox)

        spacerItem2 = QSpacerItem(20, 60, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.cfg_runtime_options_qvl.addItem(spacerItem2)

        spacerItem3 = QSpacerItem(20, 60, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.l.addItem(spacerItem3)

        # ~~~~~~~~ End of construction zone ~~~~~~~~
        self.resize(self.sizeHint())
        self.eligible_custom_fields = self.get_eligible_custom_fields()
        self.collection_field_comboBox.addItems([''])
        ecf = sorted(self.eligible_custom_fields.keys(), key=lambda s: s.lower())
        self.collection_field_comboBox.addItems(ecf)

        # ~~~~~~~~ Restore settings ~~~~~~~~
        # Restore the collection field
        cf = self.prefs.get('collection_field_comboBox', '')
        idx = self.collection_field_comboBox.findText(cf)
        if idx > -1:
            self.collection_field_comboBox.setCurrentIndex(idx)

        # Restore general settings
        self.reading_progress_checkbox.setChecked(self.prefs.get('show_progress_as_percentage', False))
        self.debug_plugin_checkbox.setChecked(self.prefs.get('debug_plugin', False))
        self.debug_libimobiledevice_checkbox.setChecked(self.prefs.get('debug_libimobiledevice', False))

    def get_eligible_custom_fields(self):
        '''
        Discover qualifying custom fields for collection assignments
        '''
        self._log_location()

        eligible_custom_fields = {}
        for cf in self.gui.current_db.custom_field_keys():
            cft = self.gui.current_db.metadata_for_field(cf)['datatype']
            cfn = self.gui.current_db.metadata_for_field(cf)['name']
            if cft in ['enumeration', 'text']:
                eligible_custom_fields[cfn] = cf
        return eligible_custom_fields

    def save_settings(self):
        self._log_location()

        # Save collection field
        cf = str(self.collection_field_comboBox.currentText())
        self.prefs.set('collection_field_comboBox', cf)
        if cf:
            self.prefs.set('collection_field_lookup', self.eligible_custom_fields[cf])
        else:
            self.prefs.set('collection_field_lookup', '')

        # Save general settings
        self.prefs.set('show_progress_as_percentage', self.reading_progress_checkbox.isChecked())
        self.prefs.set('debug_plugin', self.debug_plugin_checkbox.isChecked())
        self.prefs.set('debug_libimobiledevice', self.debug_libimobiledevice_checkbox.isChecked())

    def _log(self, msg=None):
        '''
        Print msg to console
        '''
        if not self.verbose:
            return

        if msg:
            debug_print(" %s" % msg)
        else:
            debug_print()

    def _log_location(self, *args):
        '''
        Print location, args to console
        '''
        if not self.verbose:
            return

        arg1 = arg2 = ''

        if len(args) > 0:
            arg1 = args[0]
        if len(args) > 1:
            arg2 = args[1]

        debug_print(self.LOCATION_TEMPLATE.format(cls=self.__class__.__name__,
            func=sys._getframe(1).f_code.co_name,
            arg1=arg1, arg2=arg2))


# For testing ConfigWidget, run from command line:
# cd ~/Documents/calibredev/Marvin_Manager
# calibre-debug config.py
# Search 'Marvin'
if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    from calibre.gui2.preferences import test_widget
    app = QApplication([])
    test_widget('Advanced', 'Plugins')

