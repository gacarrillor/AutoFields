# -*- coding:utf-8 -*-
"""
/***************************************************************************
AutoFields
A QGIS plugin
Automatic attribute updates when creating or modifying vector features
                             -------------------
begin                : 2017-04-11
copyright            : (C) 2017 by Germán Carrillo (GeoTux)
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

from PyQt4.QtCore import Qt, QSettings
from PyQt4.QtGui import QApplication, QDialog, QDialogButtonBox, QTableWidgetItem, QFileDialog, QMessageBox

from Ui_Export_AutoFields import Ui_ExportAutoFieldsDialog

class ExportAutoFieldsDialog( QDialog, Ui_ExportAutoFieldsDialog ):

    def __init__( self, parent, autoFieldManager, messageManager ):
        QDialog.__init__( self, parent )
        self.setupUi( self )
        self.setModal( True )
        self.parent = parent
        self.autoFieldManager = autoFieldManager
        self.messageManager = messageManager
        self.tblAutoFields.sortItems(0, Qt.AscendingOrder)
        self.btnOpenFileDialog.clicked.connect( self.openFileDialog )

        self.populateAutoFieldsTable()


    def populateAutoFieldsTable( self ):
        dictAutoFields = self.autoFieldManager.listAutoFields()
        self.tblAutoFields.clearContents()
        self.tblAutoFields.setRowCount( 0 )
        self.tblAutoFields.setColumnCount( 4 )

        self.tblAutoFields.setSortingEnabled( False )
        for key in dictAutoFields.keys():
            autoField = dictAutoFields[key]
            self.addAutoFieldToAutoFieldsTable( key, autoField )

        self.tblAutoFields.setSortingEnabled( True )


    def addAutoFieldToAutoFieldsTable( self, autoFieldId, autoField ):
        """ Add a whole row to the AutoFields table """
        row = self.tblAutoFields.rowCount()
        self.tblAutoFields.insertRow( row )
        name = autoField['layer']
        if 'layerId' in autoField:
            lyr = QgsMapLayerRegistry.instance().mapLayer( autoField['layerId'] )
            name = lyr.name()
        item = QTableWidgetItem( name )
        item.setData( Qt.UserRole, autoFieldId )
        item.setData( Qt.ToolTipRole, autoField['layer'] )
        self.tblAutoFields.setItem( row, 0, item )
        item = QTableWidgetItem( autoField['field'] )
        self.tblAutoFields.setItem( row, 1, item )
        item = QTableWidgetItem( autoField['expression'] )
        self.tblAutoFields.setItem( row, 2, item )
        item = QTableWidgetItem( QApplication.translate( "ExportAutoFields",
            "Enabled" ) if autoField['enabled'] else QApplication.translate( "ExportAutoFields", "Disabled" ) )
        self.tblAutoFields.setItem( row, 3, item )


    def openFileDialog( self ):
        settings = QSettings()
        path = QFileDialog.getSaveFileName( self, QApplication.translate( "ExportAutoFields", "Create a JSON file" ),
            settings.value( self.autoFieldManager.settingsPrefix + "/export/dir", "", type=str ), "JSON files (*.json)" )
        if path:
            if not path.endswith( '.json' ):
                path += '.json'
            self.txtExportFile.setText( path )


    def doExport( self ):
        listAFExport = []
        for dictAF in self.autoFieldManager.dictAutoFields.values(): # TODO only selected
            listAFExport.append( {k:v for k,v in dictAF.iteritems() if k in ['layer','field','expression','order']} )

        f = open( self.txtExportFile.text(), "wt" )
        f.write(json.dumps( {'AutoFields':listAFExport}, ensure_ascii=False, sort_keys=True, indent=3) .encode( 'utf-8' ) )
        f.close()


    def accept( self ):
        if not self.tblAutoFields.selectedItems():
            QMessageBox.warning( self.parent, "Warning", "Select at least one AutoField to export." )
            return
        if not self.txtExportFile.text():
            QMessageBox.warning( self.parent, "Warning", "Select an output file." )
            return

        self.doExport()
        self.messageManager.show( QApplication.translate( "ExportAutoFields",
            "Selected AutoFields have been exported to {}.".format( self.txtExportFile.text() ) ) )

        self.done( 1 )

