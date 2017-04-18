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
import re
import json
from functools import partial
from osgeo import ogr

from qgis.core import QgsMapLayerRegistry, QgsMapLayer, QgsVectorDataProvider
from PyQt4.QtCore import Qt, QSettings
from PyQt4.QtGui import ( QApplication, QDialog, QDialogButtonBox, QComboBox,
                          QTableWidgetItem, QFileDialog, QMessageBox, QIcon,
                          QPixmap, QLabel )
import resources_rc

from Ui_Import_AutoFields import Ui_ImportAutoFieldsDialog

class ImportAutoFieldsDialog( QDialog, Ui_ImportAutoFieldsDialog ):

    def __init__( self, parent, autoFieldManager, messageManager, listAutoFields, filePath, bCalculateOnExisting ):
        QDialog.__init__( self, parent )
        self.setupUi( self )
        self.setModal( True )
        self.parent = parent
        self.autoFieldManager = autoFieldManager
        self.messageManager = messageManager
        self.listAutoFields = listAutoFields
        self.filePath = filePath
        self.bCalculateOnExisting = bCalculateOnExisting
        self.listCandidates = self.getCandidates( listAutoFields )
        self.layers = []
        layers = QgsMapLayerRegistry.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                if layer.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures:
                    self.layers.append( layer )

        self.tblAutoFields.setColumnWidth( 0, 120 )
        self.tblAutoFields.setColumnWidth( 3, 80 )
        self.tblAutoFields.setColumnWidth( 4, 150 )
        self.tblAutoFields.setColumnWidth( 5, 120 )

        self.populateAutoFieldsTable()


    def populateAutoFieldsTable( self ):
        self.tblAutoFields.clearContents()
        self.tblAutoFields.setRowCount( 0 )
        self.tblAutoFields.setColumnCount( 6 )

        for i in range(len(self.listAutoFields)):
            self.addAutoFieldToAutoFieldsTable( self.listAutoFields[i], self.listCandidates[i] )


    def addAutoFieldToAutoFieldsTable( self, autoField, candidateLayer ):
        """ Add a whole row to the AutoFields table """
        row = self.tblAutoFields.rowCount()
        self.tblAutoFields.insertRow( row )
        layerName = self.ogrLayerName( autoField['layer'] )
        item = QTableWidgetItem( layerName if layerName else autoField['layer'] )
        item.setData( Qt.UserRole, autoField['layer'] )
        item.setData( Qt.ToolTipRole, autoField['layer'] )
        self.tblAutoFields.setItem( row, 0, item )
        item = QTableWidgetItem( autoField['field'] )
        self.tblAutoFields.setItem( row, 1, item )
        item = QTableWidgetItem( autoField['expression'] )
        self.tblAutoFields.setItem( row, 2, item )

        layerCombo = QComboBox()
        layerCombo.addItem( '[Select a layer]', None )
        for layer in self.layers:
           layerCombo.addItem( layer.name(), layer.id() )
        if candidateLayer:
            layerCombo.setCurrentIndex( layerCombo.findData( candidateLayer.id() ) )
        layerCombo.currentIndexChanged.connect( partial( self.layerOrFieldCombosChanged, row ) )
        self.tblAutoFields.setCellWidget( row, 4, layerCombo )

        fieldCombo = QComboBox()
        fieldCombo.addItem( '[Select a field]', None )
        if layerCombo.currentIndex() != 0:
            for field in candidateLayer.fields():
                fieldCombo.addItem( field.name() )
            fieldIndex = fieldCombo.findText( autoField['field'] )
            fieldCombo.setCurrentIndex( fieldIndex if fieldIndex != -1 else 0 )
        fieldCombo.currentIndexChanged.connect( partial( self.layerOrFieldCombosChanged, None ) )
        self.tblAutoFields.setCellWidget( row, 5, fieldCombo )

        label = self.getLabelWithArrow( layerCombo.currentIndex(), fieldCombo.currentIndex(), candidateLayer, autoField['field'] )
        self.tblAutoFields.setCellWidget( row, 3, label )

        self.layerOrFieldCombosChanged( None, None ) # Validate initial load of AutoFields/Layers


    def getLabelWithArrow( self, indexLayerCombo, indexFieldCombo, layer, fieldName ):
        label = QLabel()
        if indexLayerCombo != 0 and indexFieldCombo != 0:
            if self.autoFieldManager.isFieldAnAutoField( layer, fieldName ):
                label.setPixmap( QPixmap( ":/plugins/AutoFields/icons/orange_arrow.png" ) )
                label.setToolTip( u'By clicking OK, this AutoField will overwrite an existing AutoField in {}/{}'.format(layer.name(),fieldName) )
            else:
                label.setPixmap( QPixmap( ":/plugins/AutoFields/icons/green_arrow.png" ) )
                label.setToolTip( 'AutoField correctly assigned' )
        else:
            label.setPixmap( QPixmap( ":/plugins/AutoFields/icons/gray_arrow.png" ) )
            label.setToolTip( 'This AutoField will not be set on any layer/field' )
        label.setAlignment( Qt.AlignCenter )
        return label


    def ogrLayerName( self, uri ):
        """Borrowed and adapted from
           https://github.com/qgis/QGIS/blob/master/python/plugins/processing/tools/vector.py
        """
        if os.path.isfile(uri):
            return os.path.basename(os.path.splitext(uri)[0])

        if ' table=' in uri:
            # table="schema"."table"
            re_table_schema = re.compile(' table="([^"]*)"\\."([^"]*)"')
            r = re_table_schema.search(uri)
            if r:
                return r.groups()[0] + '.' + r.groups()[1]
            # table="table"
            re_table = re.compile(' table="([^"]*)"')
            r = re_table.search(uri)
            if r:
                return r.groups()[0]
            # table='table'
            re_table = re.compile(" table='([^']*)'")
            r = re_table.search(uri)
            if r:
                return r.groups()[0]
        elif 'layername' in uri:
            regex = re.compile('(layername=)([^|]*)')
            r = regex.search(uri)
            return r.groups()[1]

        fields = uri.split('|')
        basePath = fields[0]
        fields = fields[1:]
        layerid = 0
        for f in fields:
            if f.startswith('layername='):
                return f.split('=')[1]
            if f.startswith('layerid='):
                layerid = int(f.split('=')[1])

        ds = ogr.Open(basePath)
        if not ds:
            # Check if we can get basename from non-existing layer
            baseName = os.path.basename(uri)
            if baseName:
                ext = os.path.splitext( baseName )
                if len(ext) == 2:
                    return ext[0]
            return None

        ly = ds.GetLayer(layerid)
        if not ly:
            return None

        name = ly.GetName()
        ds = None
        return name


    def getCandidates( self, listAF ):
        listCandidates = []
        for af in listAF:
            afLayerName = self.ogrLayerName( af['layer'] )
            layers = QgsMapLayerRegistry.instance().mapLayersByName(afLayerName)
            layers = [l for l in layers if l.type() == QgsMapLayer.VectorLayer and l.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures]
            if not layers: # Check layer source
                for layer in QgsMapLayerRegistry.instance().mapLayers().values():
                    if layer.type() == QgsMapLayer.VectorLayer:
                        if self.ogrLayerName( layer.source() ) == afLayerName:
                            if layer.dataProvider().capabilities() & QgsVectorDataProvider.AddFeatures:
                                layers.append( layer )
            if not layers:
                listCandidates.append( None )
                continue # No candidate layer for this AF

            # Now check fields
            bFieldFound = False
            for layer in layers:
                if layer.fieldNameIndex( af['field'] ) != -1: # We got a candidate layer/field pair
                    bFieldFound = True
                    listCandidates.append( layer )
                    break

            if not bFieldFound:
                listCandidates.append( layers[0] ) # If no field found, propose layer anyways

        return listCandidates


    def layerOrFieldCombosChanged( self, callerRow=None, idx=None ):
        """ SLOT. Handles both layer or field selection changed SIGNALS updating
            all rows in the table. Namely, this function:
            + updates assignation arrows,
            + enables/disables OK button accordingly, and
            + updates field comboBox if layer was changed.
        """
        assigned = []
        bEnableOkButton = True
        for row in range(self.tblAutoFields.rowCount()):
            indexLayerCombo = self.tblAutoFields.cellWidget( row, 4 ).currentIndex()
            indexFieldCombo = self.tblAutoFields.cellWidget( row, 5 ).currentIndex()
            layerId = self.tblAutoFields.cellWidget( row, 4 ).itemData( indexLayerCombo )
            fieldName = self.tblAutoFields.cellWidget( row, 5 ).itemText( indexFieldCombo )
            layer = QgsMapLayerRegistry.instance().mapLayer( layerId )

            # Update fieldCombo if necessary
            if callerRow is not None and row == callerRow:
                fieldCombo = self.tblAutoFields.cellWidget( row, 5 )
                fieldCombo.blockSignals(True)
                fieldCombo.clear()
                fieldCombo.addItem( '[Select a field]', None )
                if indexLayerCombo != 0:
                    autoFieldFieldName = self.tblAutoFields.item( row, 1 ).text()
                    for field in layer.fields():
                        fieldCombo.addItem( field.name() )
                    fieldIndex = fieldCombo.findText( autoFieldFieldName )
                    fieldCombo.setCurrentIndex( fieldIndex if fieldIndex != -1 else 0 )
                fieldCombo.blockSignals(False)
                # Update fieldCombo status info
                indexFieldCombo = self.tblAutoFields.cellWidget( row, 5 ).currentIndex()
                fieldName = self.tblAutoFields.cellWidget( row, 5 ).itemText( indexFieldCombo )

            # Arrows
            label = QLabel()
            if indexLayerCombo != 0 and indexFieldCombo != 0 and layerId + "_" + fieldName in assigned:
                label.setPixmap( QPixmap( ":/plugins/AutoFields/icons/red_arrow.png" ) )
                label.setToolTip( 'Target layer/field pair already selected. You cannot assign two AutoFields to the same layer/field pair.' )
                label.setAlignment( Qt.AlignCenter )
                bEnableOkButton = False
            else:
                if indexLayerCombo != 0 and indexFieldCombo != 0:
                    assigned.append( layerId + "_" + fieldName )
                label = self.getLabelWithArrow( indexLayerCombo, indexFieldCombo, layer, fieldName )
            self.tblAutoFields.setCellWidget( row, 3, label )

        self.buttonBox.button( QDialogButtonBox.Ok ).setEnabled( bEnableOkButton )


    def accept( self ):
        # Create/Overwrite configured AutoFields to given layer/field pairs
        importedCount = 0
        for row in range(self.tblAutoFields.rowCount()):
            indexLayerCombo = self.tblAutoFields.cellWidget( row, 4 ).currentIndex()
            indexFieldCombo = self.tblAutoFields.cellWidget( row, 5 ).currentIndex()
            layerId = self.tblAutoFields.cellWidget( row, 4 ).itemData( indexLayerCombo )
            fieldName = self.tblAutoFields.cellWidget( row, 5 ).itemText( indexFieldCombo )
            expression = self.tblAutoFields.item( row, 2 ).text()
            layer = QgsMapLayerRegistry.instance().mapLayer( layerId )

            if indexLayerCombo != 0 and indexFieldCombo != 0:
                importedCount += 1
                if self.autoFieldManager.isFieldAnAutoField( layer, fieldName ):
                    self.autoFieldManager.overwriteAutoField( layer, fieldName, expression, calculateOnExisting=self.bCalculateOnExisting )
                else:
                    self.autoFieldManager.createAutoField( layer, fieldName, expression, calculateOnExisting=self.bCalculateOnExisting )

        if importedCount:
            self.messageManager.show( QApplication.translate( "ImportAutoFields",
                u"Configured AutoFields have been imported into QGIS from file {}.".format( self.filePath ) ) )
        else:
            self.messageManager.show( QApplication.translate( "ImportAutoFields",
                u"None of the AutoFields from file {} has been imported into QGIS.".format( self.filePath ) ) )

        self.done( 1 )

