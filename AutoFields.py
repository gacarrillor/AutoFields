# -*- coding:utf-8 -*-
"""
/***************************************************************************
AutoFields
A QGIS plugin
Automatic attribute updates when creating or modifying vector features
                             -------------------
begin                : 2016-05-22
copyright            : (C) 2016 by Germán Carrillo (GeoTux)
email                : gcarrillo@linuxmail.org
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

import os.path
import json

from qgis.core import ( QgsApplication, QgsMapLayerRegistry, QgsMapLayer,
                        QgsVectorDataProvider )
from PyQt4.QtCore import ( Qt, QTranslator, QFileInfo, QCoreApplication,
    QLocale, QSettings )
from PyQt4.QtGui import QIcon, QAction, QDockWidget, QFileDialog, QApplication
import resources_rc
from AutoFieldsDockWidget import AutoFieldsDockWidget
from ExportAutoFieldsDialog import ExportAutoFieldsDialog
from ImportAutoFieldsDialog import ImportAutoFieldsDialog
from AutoFieldManager import AutoFieldManager
from MessageManager import MessageManager


class AutoFields:

  def __init__( self, iface ):
    self.iface = iface
    self.messageMode = 'production' # 'production' or 'debug'
    self.language='en'
    self.installTranslator()


  def initGui( self ):

    # Remove Redo buttons from menus and toolbars, they can lead to crashes due
    #   to a corrupted undo stack.
    redoActionList = [action for action in self.iface.advancedDigitizeToolBar().actions() if action.objectName() == u'mActionRedo']
    if redoActionList:
        self.iface.advancedDigitizeToolBar().removeAction( redoActionList[0] )
        self.iface.editMenu().removeAction( redoActionList[0] )

    QSettings().setValue( "/shortcuts/Redo", "" ) # Override Redo shortcut

    # This block (2 options for disabling the Undo panel) didn't work
    #QSettings().setValue( '/UI/Customization/enabled', True )
    #QSettings( "QGIS", "QGISCUSTOMIZATION2" ).setValue( '/Customization/Panels/Undo', False )
    #undoDock = self.iface.mainWindow().findChild( QDockWidget, u'Undo' )
    #self.iface.removeDockWidget( undoDock )

    # Create action that will start plugin configuration
    self.actionDock = QAction(QIcon( ":/plugins/AutoFields/icon.png"), \
        "AutoFields plugin...", self.iface.mainWindow() )
    self.actionDock.triggered.connect( self.toggleDockWidget )

    self.actionExport = QAction(QIcon( ":/plugins/AutoFields/icons/export.png"), \
        "Export AutoFields to JSON file...", self.iface.mainWindow() )
    self.actionExport.triggered.connect( self.openExportDialog )

    self.actionImport = QAction(QIcon( ":/plugins/AutoFields/icons/import.png"), \
        "Import AutoFields from JSON file...", self.iface.mainWindow() )
    self.actionImport.triggered.connect( self.openImportFileDialog )

    # Add custom submenu to Vector menu
    self.iface.addPluginToVectorMenu( "&AutoFields", self.actionDock )
    self.iface.addPluginToVectorMenu( "&AutoFields", self.actionExport )
    self.iface.addPluginToVectorMenu( "&AutoFields", self.actionImport )

    # Add a custom toolbar
    self.toolbar = self.iface.addToolBar( "AutoFields" )
    self.toolbar.setObjectName("AutoFields")
    self.toolbar.addAction( self.actionDock )
    self.toolbar.addAction( self.actionExport )
    self.toolbar.addAction( self.actionImport )

    self.messageManager = MessageManager( self.messageMode, self.iface )

    self.autoFieldManager = AutoFieldManager( self.messageManager, self.iface )
    self.autoFieldManager.readAutoFields()

    self.dockWidget = AutoFieldsDockWidget( self.iface.mainWindow(), self.iface, self.autoFieldManager, self.messageManager, self.language )
    self.iface.addDockWidget( Qt.RightDockWidgetArea, self.dockWidget )


  def unload( self ):
    # Remove the plugin menu and toolbar
    self.iface.removePluginVectorMenu( "&AutoFields", self.actionDock )
    self.iface.removePluginVectorMenu( "&AutoFields", self.actionExport )
    self.iface.removePluginVectorMenu( "&AutoFields", self.actionImport )
    self.iface.mainWindow().removeToolBar( self.toolbar )

    self.autoFieldManager.disconnectAll()

    self.dockWidget.disconnectAll()
    self.dockWidget.close()
    self.iface.removeDockWidget( self.dockWidget )


  def toggleDockWidget( self ):
    if self.dockWidget:
      if self.dockWidget.isVisible():
        self.dockWidget.hide()
      else:
        self.dockWidget.show()


  def openExportDialog( self ):
    dlg = ExportAutoFieldsDialog( self.iface.mainWindow(), self.autoFieldManager, self.messageManager )
    dlg.show()


  def openImportFileDialog( self ):
    bLayers = False
    layers = QgsMapLayerRegistry.instance().mapLayers().values()
    for layer in layers:
      if layer.type() == QgsMapLayer.VectorLayer:
        if layer.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures:
          bLayers = True
          break

    if not bLayers:
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
          "First load some vector layers to QGIS where you would like to import AutoFields to." ), 'warning' )
      return

    settings = QSettings()
    path = QFileDialog.getOpenFileName( self.iface.mainWindow(), QApplication.translate( "ImportAutoFields", "Select a JSON file" ),
      settings.value( self.autoFieldManager.settingsPrefix + "/import/dir", "", type=str ), "JSON files (*.json)" )
    if path:
      settings.setValue( self.autoFieldManager.settingsPrefix + "/import/dir", os.path.dirname( path ) )
      listAutoFields = self.validateInputJSON( path )
      # Now openImportDialog()
      dlg = ImportAutoFieldsDialog( self.iface.mainWindow(), self.autoFieldManager, self.messageManager, listAutoFields, path, self.dockWidget.chkCalculateOnExisting.isChecked() )
      dlg.show()


  def validateInputJSON( self, filePath ):
    if not os.path.isfile(filePath):
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
            "The JSON file does not exist." ) )
      return False

    if os.path.splitext( filePath )[1] != '.json':
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
            "File must have the 'json' extension." ) )
      return False
    inputFile = open( filePath )

    try:
      dictJSON = json.load( inputFile )
    except ValueError, e:
      inputFile.close()
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
            "The given file is not a valid JSON." ) )
      return False

    inputFile.close()

    if ['AutoFields'] != dictJSON.keys():
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
            "Invalid JSON. The JSON file does not have a unique root property called 'AutoFields'." ) )
      return False

    listAF = dictJSON['AutoFields']
    for dictAF in listAF:
      if set(['layer','field','expression','order']) != set(dictAF.keys()):
        self.messageManager.show( QApplication.translate( "ImportAutoFields",
            "Invalid JSON. JSON content does not match what AutoFields plugin expects." ) )
        return False

    if not listAF:
      self.messageManager.show( QApplication.translate( "ImportAutoFields",
          "Invalid JSON. The JSON file does not contain any AutoField to import." ) )
      return False

    return listAF


  def installTranslator( self ):
    userPluginPath = os.path.join( os.path.dirname( str( QgsApplication.qgisUserDbFilePath() ) ), "python/plugins/AutoFields" )
    systemPluginPath = os.path.join( str( QgsApplication.prefixPath() ), "python/plugins/AutoFields" )
    translationPath = ''

    locale = QSettings().value( "locale/userLocale", type=str )
    myLocale = str( locale[0:2] )
    if myLocale == 'es':
      self.language='es'

    if os.path.exists( userPluginPath ):
      translationPath = os.path.join( userPluginPath, 'i18n', "AutoFields_" + myLocale + ".qm" )
    else:
      translationPath = os.path.join( systemPluginPath, 'i18n', "AutoFields_" + myLocale + ".qm" )

    if QFileInfo( translationPath ).exists():
      self.translator = QTranslator()
      self.translator.load( translationPath )
      QCoreApplication.installTranslator( self.translator )

