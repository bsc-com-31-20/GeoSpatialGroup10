# -*- coding: utf-8 -*-
"""
/***************************************************************************
 waterManager
                                 A QGIS plugin
 this plugin willl allow users to load community dataset and water source dataset and process and give them the results for the nearest water sorce for communities
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2024-11-30
        git sha              : $Format:%H$
        copyright            : (C) 2024 by group10
        email                : danielkasambala51@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QDialog
from qgis.core import QgsProject, Qgis, QgsMapLayer

# Initialize Qt resources from file resources.py
from .resources import *

# Import the code for the dialog
from .water_manager_dialog import waterManagerDialog
import os.path


class waterManager:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(
            self.plugin_dir, "i18n", "waterManager_{}.qm".format(locale)
        )

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&water management plugin")

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("waterManager", message)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ":/plugins/water_manager/icon.png"
        self.add_action(
            icon_path,
            text=self.tr("nearest water source plugin"),
            callback=self.run,
            parent=self.iface.mainWindow(),
        )

        # will be set False in run()
        self.first_start = True

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(self.tr("&water management plugin"), action)
            self.iface.removeToolBarIcon(action)

    def select_output_file(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select output file ","", '*.csv')
        self.dlg.lineEdit.setText(filename)
    def action_on_ok(self):
        
        """Handles the OK button press action."""
        # Check if the OK button was pressed
        filename = self.dlg.lineEdit.text()
        if not filename:
            self.iface.messageBar().pushMessage(
                "Error", "No output file specified.", level=Qgis.Critical, duration=5)
            return

        # Get the selected layer index and layer
        selectedLayerIndex = self.dlg.comboBoxCom.currentIndex()
        if selectedLayerIndex < 0:
            self.iface.messageBar().pushMessage(
                "Error", "No community layer selected.", level=Qgis.Critical, duration=5)
            return

        layers = QgsProject.instance().layerTreeRoot().children()
        selectedLayer = layers[selectedLayerIndex].layer()

        # Write data to the output file
        try:
            with open(filename, 'w') as output_file:
                fieldnames = [field.name() for field in selectedLayer.fields()]
                # Write header
                output_file.write(','.join(fieldnames) + '\n')

                # Write feature attributes
                for feature in selectedLayer.getFeatures():
                    output_file.write(','.join(str(feature[field]) for field in fieldnames) + '\n')

            self.iface.messageBar().pushMessage(
                "Success", f"Output file written at {filename}", level=Qgis.Success, duration=3)
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Error", f"An error occurred: {e}", level=Qgis.Critical, duration=5)
  
        
   
    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = waterManagerDialog()
        
            #clicked 
            self.dlg.pushButton.clicked.connect(self.select_output_file)
            self.dlg.buttonBox.clicked.connect(self.action_on_ok)

            # Fetch the currently loaded layers
        layers = QgsProject.instance().layerTreeRoot().children()

        # Clear the contents of the comboBoxes from previous runs
        self.dlg.comboBoxCom.clear()
        self.dlg.comboBoxSource.clear()

        # Populate comboBoxCom with names of all loaded layers
        self.dlg.comboBoxCom.addItems([layer.name() for layer in layers])

        # # Filter layers for water-related keywords and populate comboBox_Source
        # water_source_layers = [
        #     layer.name()
        #     for layer in layers
        #     if "water" in layer.name().lower() or "source" in layer.name().lower()
        # ]
        self.dlg.comboBoxSource.addItems([layer.name() for layer in layers])

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # def action_on_ok(self):
                

         


 