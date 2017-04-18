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

from qgis.core import QgsMapLayerRegistry, QgsMapLayer, QgsVectorDataProvider
from PyQt4.QtCore import Qt, QSettings
from PyQt4.QtGui import ( QApplication, QDialog, QDialogButtonBox,
                          QTableWidgetItem, QFileDialog, QMessageBox )

from Ui_Set_AutoField_on_Layer import Ui_SetAutoFieldOnLayerDialog

class SetAutoFieldOnLayerDialog( QDialog, Ui_SetAutoFieldOnLayerDialog ):

    def __init__( self, parent, autoFieldManager, messageManager, autoFieldId, bCalculateOnExisting ):
        QDialog.__init__( self, parent )
        self.setupUi( self )
        self.setModal( True )
        self.parent = parent
        self.autoFieldManager = autoFieldManager
        self.messageManager = messageManager
        self.autoFieldId = autoFieldId
        self.bCalculateOnExisting = bCalculateOnExisting

        self.autoField = self.autoFieldManager.dictAutoFields[ self.autoFieldId ]

        self.populateLayerCombo()


    def populateLayerCombo( self ):
        fieldName = self.autoField['field']
        self.cboLayer.clear()

        layers = QgsMapLayerRegistry.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                if layer.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures:
                    if layer.fieldNameIndex( fieldName ) != -1:
                        if not self.autoFieldManager.isFieldAnAutoField( layer, fieldName ):
                            self.cboLayer.addItem( layer.name(), layer.id() )

        if self.cboLayer.currentIndex() == -1:
            self.buttonBox.button( QDialogButtonBox.Ok ).setEnabled( False )


    def accept( self ):
        layerId = self.cboLayer.itemData( self.cboLayer.currentIndex() )
        layer = QgsMapLayerRegistry.instance().mapLayer( layerId )
        if layer:
            self.autoFieldManager.createAutoField( layer, self.autoField['field'], self.autoField['expression'], calculateOnExisting=self.bCalculateOnExisting )
            self.autoFieldManager.removeAutoField( self.autoFieldId )
        else:
            QMessageBox.warning( self.parent, "Warning", "Layer not found." )
            return

        self.messageManager.show( QApplication.translate( "ExportAutoFields",
            "Selected AutoField has been set on {}.{}.".format( layer.name(), self.autoField['field'] ) ) )

        self.done( 1 )

