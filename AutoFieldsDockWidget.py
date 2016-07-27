# -*- coding:utf-8 -*-
"""
/***************************************************************************
AutoFields
A QGIS plugin
Automatic vector field updates when modifying or creating features
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

from qgis.core import ( QgsMapLayerRegistry, QgsProject, QgsMapLayer, QgsField, 
    QgsVectorDataProvider, QgsExpressionContext, QgsExpressionContextUtils, 
    QgsDistanceArea, GEO_NONE )
from PyQt4.QtCore import Qt, QSize, pyqtSlot, QVariant
from PyQt4.QtGui import ( QApplication, QIcon, QDockWidget, QTableWidgetItem,  
    QButtonGroup, QBrush, QHeaderView, QMessageBox )
import resources_rc
from Ui_AutoFields_dock import Ui_AutoFieldsDockWidget
from ExpressionBuilderDialog import ExpressionBuilderDialog


class AutoFieldsDockWidget( QDockWidget, Ui_AutoFieldsDockWidget ):
    """ Class in charge of all the UI logic """

    def __init__( self, parent, iface, autoFieldManager, messageManager ):
        self.iface = iface 
        self.msg = messageManager
        QDockWidget.__init__( self, parent )
        # Set up the user interface from Designer.
        self.setupUi( self )
        
        self.autoFieldManager = autoFieldManager
        self.geometryDict = ['points','lines','polygons']
        self.fieldTypesDict = ['Integer','Real','String','Date']
        
        self.root = QgsProject.instance().layerTreeRoot()
        
        # UI stuff that wasn't set/initialized in Qt-Designer
        self.tblLayers.setColumnWidth( 0, 24 )
        self.tblLayers.setColumnWidth( 1, 140 )
        self.tblLayers.setColumnWidth( 2, 110 )
        self.tblLayers.horizontalHeader().setResizeMode( 0, QHeaderView.Fixed )
        self.tblLayers.sortItems(1, Qt.AscendingOrder)
        self.cboField.setEnabled( False )
        self.cboFieldType.setItemData( 0, QVariant.Int, Qt.UserRole )
        self.cboFieldType.setItemData( 1, QVariant.Double, Qt.UserRole )
        self.cboFieldType.setItemData( 2, QVariant.String, Qt.UserRole )
        self.cboFieldType.setItemData( 3, QVariant.Date, Qt.UserRole )
        self.fieldTypeChanged( self.cboFieldType.currentIndex() ) # Update length/precision controls
        self.btnGroup = QButtonGroup()
        self.btnGroup.addButton( self.optXCoord )
        self.btnGroup.addButton( self.optYCoord )
        self.btnGroup.addButton( self.optLength )
        self.btnGroup.addButton( self.optPerimeter )
        self.btnGroup.addButton( self.optArea )
        self.btnGroup.addButton( self.optDate )
        self.btnGroup.addButton( self.optCustomExpression )
        #self.btnGroup.addButton( self.optSpatialValue )
        self.updateExpressionControls( self.optCustomExpression )
        
        self.frameFields.setEnabled( False )
        self.frameExpression.setEnabled( False )
        self.populateLayersTable()

        QgsMapLayerRegistry.instance().legendLayersAdded.connect( self.populateLayersTable )
        QgsMapLayerRegistry.instance().layersRemoved.connect( self.populateLayersTable )
        self.tblLayers.itemSelectionChanged.connect( self.updateFieldAndExpressionControls )
        self.optNewField.toggled.connect( self.newFieldToggled )                
        self.cboField.currentIndexChanged.connect( self.fieldChanged )
        self.cboFieldType.currentIndexChanged.connect( self.fieldTypeChanged )
        self.btnSaveAutoField.clicked.connect( self.saveAutoField )
        self.btnNewCustomExpression.clicked.connect( self.setCustomExpression )        
        self.btnGroup.buttonClicked.connect( self.updateExpressionControls )
        
        self.expressionDlg = None
        
        # 'List of AutoFields' Tab
        self.btnRemoveAutoFields.setEnabled( False )
        self.tblAutoFields.sortItems(0, Qt.AscendingOrder)
        self.populateAutoFieldsTable()
        self.autoFieldManager.autoFieldCreated.connect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldRemoved.connect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldEnabled.connect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldDisabled.connect( self.populateAutoFieldsTable )
        self.tblAutoFields.itemSelectionChanged.connect( self.updateRemoveAutoFieldButton )
        self.btnRemoveAutoFields.clicked.connect( self.removeAutoFieldFromTable )
        

    def populateLayersTable( self, foo=None ):
        """ List vector layers that support changes in attributes and are writable """
        
        # Initialize Layers Table
        self.tblLayers.clearContents()
        self.tblLayers.setRowCount( 0 )
        
        vLayers = []
        for layer in QgsMapLayerRegistry.instance().mapLayers().values():
            if layer.type() == QgsMapLayer.VectorLayer:
                if layer.dataProvider().capabilities() & QgsVectorDataProvider.ChangeAttributeValues:
                    if not layer.isReadOnly():
                        if layer.geometryType() < 3: # Avoid UnknownGeometry and NoGeometry
                            vLayers.append( layer )
                  
        self.tblLayers.setRowCount( len( vLayers ) )
        self.tblLayers.setColumnCount( 3 )

        self.tblLayers.setSortingEnabled( False )
        for row, lyr in enumerate( vLayers ):
            item = QTableWidgetItem( QIcon( ":/plugins/AutoFields/icons/" + \
                self.geometryDict[lyr.geometryType()] + ".png"), 
                str( lyr.geometryType() ) )                     
            self.tblLayers.setItem( row, 0, item )
            
            item = QTableWidgetItem( lyr.name() )
            item.setData( Qt.UserRole, lyr.id() )
            self.tblLayers.setItem( row, 1, item )
            
            tmpTreeLayer = self.root.findLayer( lyr.id() )
            if tmpTreeLayer:
                group = tmpTreeLayer.parent().name()
                self.tblLayers.setItem(row, 2, 
                    QTableWidgetItem( group if group else QApplication.translate("AutoFieldsDockWidgetPy", 
                        "< root >" ) ) )

        self.tblLayers.setSortingEnabled( True )
        

    def updateFieldAndExpressionControls( self ):
        """ After a selection is changed, reflect possible values in field controls """
        self.msg.show( "New selection " + str(len( self.tblLayers.selectedItems() ) / 3), 'info', True )
        
        if not self.tblLayers.selectedItems():
            self.frameFields.setEnabled( False )
            self.frameExpression.setEnabled( False )
            return
        else:
            self.frameFields.setEnabled( True )
            self.frameExpression.setEnabled( True )
        
        # List common fields in cboField and get geometries selected 
        geometryTypeSet = self.updateFieldList()


        # Update expression controls
        if 0 in geometryTypeSet and len( geometryTypeSet ) == 1:
            self.optXCoord.setEnabled( True )
            self.optYCoord.setEnabled( True )
            self.optLength.setEnabled( False )
            self.optPerimeter.setEnabled( False )
            self.optArea.setEnabled( False )
        elif 1 in geometryTypeSet and len( geometryTypeSet ) == 1:
            self.optXCoord.setEnabled( False )
            self.optYCoord.setEnabled( False )
            self.optLength.setEnabled( True )
            self.optPerimeter.setEnabled( False )
            self.optArea.setEnabled( False )
        elif 2 in geometryTypeSet and len( geometryTypeSet ) == 1:
            self.optXCoord.setEnabled( False )
            self.optYCoord.setEnabled( False )
            self.optLength.setEnabled( False )
            self.optPerimeter.setEnabled( True )
            self.optArea.setEnabled( True )    
        else:    
            self.optXCoord.setEnabled( False )
            self.optYCoord.setEnabled( False )
            self.optLength.setEnabled( False )
            self.optPerimeter.setEnabled( False )
            self.optArea.setEnabled( False )    

        if not self.btnGroup.checkedButton().isEnabled():
            self.optCustomExpression.setChecked( True ) # Default selection
            self.updateExpressionControls( self.optCustomExpression )
            
        self.expressionDlg = None # Initialize the dialog
        
        
    def updateFieldList( self ):
        """ Update field list and return geometries selected """
        commonFields = []
        geometryTypeSet = set()
        bFirstFlag = True
        for item in self.tblLayers.selectedItems():
            if item.column() == 1: # It's the layer name item
                self.msg.show( "ID " + item.data( Qt.UserRole ), 'info', True ) # Get layer id
                layer = QgsMapLayerRegistry.instance().mapLayer( item.data( Qt.UserRole ) )
                geometryTypeSet.add( layer.geometryType() ) 
                tmpFields = [field.name() for field in layer.dataProvider().fields()] # Get field names stored in the provider
                if bFirstFlag: # Initialize commonFields
                    commonFields = tmpFields
                    bFirstFlag = False
                else: # Intersect fields
                    if commonFields: # Avoid intersecting if no common fields 
                        commonFields = list( set( commonFields ) & set( tmpFields ) ) 
                    
        commonFields.sort()
        self.msg.show( "FIELDS: "+ str(commonFields), 'info', True)

        self.cboField.clear()
        if not commonFields:
            self.optExistingField.setEnabled( False )
            self.optNewField.setChecked( True )
        else:
            self.optExistingField.setEnabled( True )
            self.cboField.addItems( commonFields )

        return geometryTypeSet


    def newFieldToggled( self ):
        """ Alternate between controls of new field and existing field """
        newIsChecked = self.optNewField.isChecked()

        self.cboField.setEnabled( not newIsChecked )
        
        self.lblFieldName.setEnabled( newIsChecked )
        self.lblFieldType.setEnabled( newIsChecked )
        self.txtFieldName.setEnabled( newIsChecked )
        self.cboFieldType.setEnabled( newIsChecked )

        if newIsChecked:
            self.fieldTypeChanged( self.cboFieldType.currentIndex() )
        else:
            self.lblFieldLength.setEnabled( newIsChecked )
            self.lblFieldPrecision.setEnabled( newIsChecked )
            self.txtFieldLength.setEnabled( newIsChecked )
            self.txtFieldPrecision.setEnabled( newIsChecked )
            
        self.expressionDlg = None # Initialize the dialog
        

    def fieldTypeChanged( self, idx ):
        """ Update field length and field precision controls' state and values """
        text = self.fieldTypesDict[idx]
        if text == 'Integer':
            self.txtFieldLength.setRange( 1, 10 )
            self.txtFieldLength.setEnabled( True )
            self.txtFieldPrecision.setEnabled( False )
            self.lblFieldLength.setEnabled( True )
            self.lblFieldPrecision.setEnabled( False )            
        elif text == 'Real':
            self.txtFieldLength.setRange( 1, 20 )          
            self.txtFieldPrecision.setRange( 0, 15 ) 
            self.txtFieldLength.setEnabled( True )
            self.txtFieldPrecision.setEnabled( True )
            self.lblFieldLength.setEnabled( True )
            self.lblFieldPrecision.setEnabled( True )    
        elif text == 'String':
            self.txtFieldLength.setRange( 1, 255 )           
            self.txtFieldLength.setEnabled( True )
            self.txtFieldPrecision.setEnabled( False )
            self.lblFieldLength.setEnabled( True )
            self.lblFieldPrecision.setEnabled( False )    
        else: # Date      
            self.txtFieldLength.setEnabled( False )
            self.txtFieldPrecision.setEnabled( False )
            self.lblFieldLength.setEnabled( False )
            self.lblFieldPrecision.setEnabled( False )
        
        
    def fieldChanged( self, idx ):
        """ Just to initialize the expression dialog if selected field changes """
        self.expressionDlg = None # Initialize the dialog
        
        
    def saveAutoField( self ):
        """ Do some validation and then call AutoFieldManager """
        
        # Check layers
        if not self.tblLayers.selectedItems():
            self.msg.show( QApplication.translate( "AutoFieldsDockWidgetPy", 
                "[Warning] Please first select a layer." ), 'warning' )
            return
        
        # Check expression
        expression = u''
        if self.optXCoord.isChecked():
            expression = u'$x'
        elif self.optYCoord.isChecked():
            expression = u'$y'
        elif self.optLength.isChecked():
            expression = u'$length'
        elif self.optPerimeter.isChecked():
            expression = u'$perimeter'
        elif self.optArea.isChecked():
            expression = u'$area'
        elif self.optDate.isChecked():
            expression = u'now()'
        elif self.optCustomExpression.isChecked():
            if self.expressionDlg:
                expression = self.expressionDlg.expression
            if not self.expressionDlg or not expression:
                self.msg.show( QApplication.translate( "AutoFieldsDockWidgetPy",
                    "[Warning] Please first set a valid custom expression." ),
                    'warning' )
                return
        else: # optSpatialValue
            pass
        
        # Check fields
        fieldName = ''
        if self.optNewField.isChecked():
            if self.txtFieldName.text():
                
                fieldName = self.txtFieldName.text().strip()
                newField = QgsField( fieldName, 
                    self.cboFieldType.itemData( self.cboFieldType.currentIndex(), Qt.UserRole) )
                
                length = self.txtFieldLength.value()
                precision = self.txtFieldPrecision.value()
                # Ensure length and precision are valid values when dealing with Real numbers
                if self.fieldTypesDict[self.cboFieldType.currentIndex()] == 'Real':
                    if precision > length:
                        precision = length
                newField.setLength( length )
                newField.setPrecision( precision )
                
                for item in self.tblLayers.selectedItems():
                    if item.column() == 1: # It's the layer name item
                        layer = QgsMapLayerRegistry.instance().mapLayer( item.data( Qt.UserRole ) )
                        if layer.fieldNameIndex( fieldName ) != -1:
                            self.msg.show( 
                                QApplication.translate( "AutoFieldsDockWidgetPy", 
                                    "[Error] The field " ) + fieldName + \
                                QApplication.translate( "AutoFieldsDockWidgetPy",
                                    " already exists in layer " ) + layer.name() + ". " + \
                                QApplication.translate( "AutoFieldsDockWidgetPy", 
                                    " If you want to create an AutoField on it, you need to choose it from 'Existing Field' list." ), 
                                'warning' )
                        else:                            
                            res = layer.dataProvider().addAttributes( [ newField ] )                            
                            if res: 
                                layer.updateFields()
                                
                                # Check if fieldName is preserved by the provider after field creation.
                                if layer.fieldNameIndex( fieldName ) == -1:
                                    self.msg.show( 
                                        QApplication.translate( "AutoFieldsDockWidgetPy", 
                                            "[Error] The field " ) + fieldName + \
                                        QApplication.translate( "AutoFieldsDockWidgetPy",
                                            " was probably created with another name by the layer (" ) + \
                                        layer.name() + \
                                        QApplication.translate( "AutoFieldsDockWidgetPy", 
                                            ") provider. " ) + \
                                        QApplication.translate( "AutoFieldsDockWidgetPy", 
                                            " If you want to create an AutoField on it, you need to choose it from 'Existing Field' list." ), 
                                        'warning' )
                                else:                

                                    self.doSaveAutoField( layer, fieldName, expression )
                                    
                            else:                            
                                self.msg.show( QApplication.translate( "AutoFieldsDockWidgetPy",
                                    "[Error] Couldn't create " ) + newField.name() + \
                                    QApplication.translate( "AutoFieldsDockWidgetPy", 
                                        " field in " ) + layer.name() + \
                                    QApplication.translate( "AutoFieldsDockWidgetPy", " layer." ), 
                                    'warning' )
            
                # Some fields might have been created, update the field list once
                self.updateFieldList()
                
            else: 
                self.msg.show( QApplication.translate( "AutoFieldsDockWidgetPy",
                    "[Warning] Please first set a name for the new field." ), 'warning' )
                return        
        else:
            fieldName = self.cboField.currentText()
                
            for item in self.tblLayers.selectedItems():
                if item.column() == 1: # It's the layer name item
                    layer = QgsMapLayerRegistry.instance().mapLayer( item.data( Qt.UserRole ) )
                    self.doSaveAutoField( layer, fieldName, expression )
        

    def doSaveAutoField( self, layer, fieldName, expression ): 
        """ Repetitive logic to save or overwrite an AutoField """
        # Check if the field is an AutoField and ask if we should overwrite it
        res = True
        if self.autoFieldManager.isFieldAnAutoField( layer, fieldName ):                                        
            reply = QMessageBox.question( self.iface.mainWindow(), 
                QApplication.translate( "AutoFieldsDockWidgetPy", "Confirmation" ),
                QApplication.translate( "AutoFieldsDockWidgetPy", "The field '" ) + \
                fieldName + QApplication.translate( "AutoFieldsDockWidgetPy", 
                    "' from layer '" ) + layer.name() + \
                QApplication.translate( "AutoFieldsDockWidgetPy",
                    "' is already an AutoField.\nDo you want to overwrite it?" ),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No )
            
            if reply == QMessageBox.Yes:
                res = self.autoFieldManager.overwriteAutoField( layer, fieldName, expression )

        else:
            res = self.autoFieldManager.createAutoField( layer, fieldName, expression )

        if not res: 
            # res will only be False if create/overwriteAutoField return False
            self.msg.show( "[Error] The AutoField for layer '" + layer.name() + \
                "' and field '" + fieldName + "' couldn't be created.", 'warning', True )

        
    def setCustomExpression( self ):
        """ Initialize and show the expression builder dialog """
        layer = None
        if len( self.tblLayers.selectedItems() ) / 3 == 1: # Single layer selected?
            for item in self.tblLayers.selectedItems():
                if item.column() == 1: # It's the layer name item
                    layer = QgsMapLayerRegistry.instance().mapLayer( item.data( Qt.UserRole ) )

        if not self.expressionDlg:        
            self.expressionDlg = ExpressionBuilderDialog( self.iface.mainWindow() )            
            context = QgsExpressionContext()
            context.appendScope( QgsExpressionContextUtils.globalScope() )
            context.appendScope( QgsExpressionContextUtils.projectScope() )
            
            # Initialize dialog with layer-based names and variables if single layer selected
            if len( self.tblLayers.selectedItems() ) / 3 == 1:
                context.appendScope( QgsExpressionContextUtils.layerScope( layer ) )  
                self.expressionDlg.expressionBuilderWidget.setLayer( layer )
                self.expressionDlg.expressionBuilderWidget.loadFieldNames()
                
                # This block was borrowed from QGIS/python/plugins/processing/algs/qgis/FieldsCalculator.py 
                da = QgsDistanceArea()
                da.setSourceCrs( layer.crs().srsid() )
                da.setEllipsoidalMode( self.iface.mapCanvas().mapSettings().hasCrsTransformEnabled() )
                da.setEllipsoid( QgsProject.instance().readEntry( 'Measure', '/Ellipsoid', GEO_NONE )[0] )
                self.expressionDlg.expressionBuilderWidget.setGeomCalculator( da )

                # If this layer-field is an AutoField, get its expression
                if self.optExistingField.isChecked():      
                    fieldName = self.cboField.currentText()   
                    expression = self.autoFieldManager.getFieldExpression( layer, fieldName )
                    self.expressionDlg.expressionBuilderWidget.setExpressionText( expression )
                    self.expressionDlg.expression = expression # To remember it when closing/opening
            
            self.expressionDlg.expressionBuilderWidget.setExpressionContext( context )          
        
        self.expressionDlg.show()
        
        
    def updateExpressionControls( self, button ):
        """ Enable/disable push buttons when appropriate """
        if button.objectName() == 'optCustomExpression':
            self.btnNewCustomExpression.setEnabled( True )
            #self.btnNewSpatialValue.setEnabled( False )
        #elif button.objectName() == 'optSpatialValue':
            #self.btnNewCustomExpression.setEnabled( False )
            #self.btnNewSpatialValue.setEnabled( True )
        else:
            self.btnNewCustomExpression.setEnabled( False )
            #self.btnNewSpatialValue.setEnabled( False )
        
        
    def populateAutoFieldsTable( self, autoFieldId=None ):
        """ Listens to any modification on AutoFields to update the list """
        dictAutoFields = self.autoFieldManager.listAutoFields()
        if autoFieldId: # Just update this one
            if not autoFieldId in dictAutoFields: # AutoField removed
                self.msg.show( "[Info] Removing AutoField from table.", 'info', True )
                # Iterate through AF rows and remove row where data matches AFID
                deleteRow = self.findRowOfItemDataInAutoFieldsTable( autoFieldId, 0)
                if deleteRow != -1:
                    self.tblAutoFields.removeRow( deleteRow )
            else: 
                # if it's in the table: remove it and re-add it (from new dict)
                deleteRow = self.findRowOfItemDataInAutoFieldsTable( autoFieldId, 0)
                if deleteRow != -1:
                    self.msg.show( "[Info] Refreshing AutoField status in table.", 'info', True )
                    self.tblAutoFields.removeRow( deleteRow )
                    self.addAutoFieldToAutoFieldsTable( autoFieldId, dictAutoFields[autoFieldId] )  
                else: # New AutoField, just add it to table
                    self.msg.show( "[Info] Adding new AutoField to table.", 'info', True )
                    self.addAutoFieldToAutoFieldsTable( autoFieldId, dictAutoFields[autoFieldId] )  
        else:
            # Initialize AutoFields Table
            self.tblAutoFields.clearContents()
            self.tblAutoFields.setRowCount( 0 )
            
            #self.tblAutoFields.setRowCount( len( dictAutoFields ) )
            self.tblAutoFields.setColumnCount( 4 )

            self.tblAutoFields.setSortingEnabled( False )
            for key in dictAutoFields.keys():
                autoField = dictAutoFields[key]
                self.addAutoFieldToAutoFieldsTable( key, autoField, False )

            self.tblAutoFields.setSortingEnabled( True )


    def findRowOfItemDataInAutoFieldsTable( self, data, col ):
        """ Get the row number that matches its data to a given data (check only the given column) """
        for numRow in range( self.tblAutoFields.rowCount() ):
            item = self.tblAutoFields.item( numRow, col )
            if item.data( Qt.UserRole ) == data:
                return numRow
        return -1


    def addAutoFieldToAutoFieldsTable( self, autoFieldId, autoField, freezeSorting=True ):
        """ Add a whole row to the AutoFields table """
        if freezeSorting:
            self.tblAutoFields.setSortingEnabled( False )
    
        row = self.tblAutoFields.rowCount()
        self.tblAutoFields.insertRow( row )
        name = autoField['layer']
        if 'layerId' in autoField:
            lyr = QgsMapLayerRegistry.instance().mapLayer( autoField['layerId'] )
            name = lyr.name()
        item = QTableWidgetItem( name )
        item.setData( Qt.UserRole, autoFieldId )
        item.setData( Qt.ToolTipRole, autoField['layer'] )
        if not autoField['enabled']: 
            item.setForeground( QBrush( Qt.gray ) )
        self.tblAutoFields.setItem( row, 0, item )
        item = QTableWidgetItem( autoField['field'] )
        if not autoField['enabled']: 
            item.setForeground( QBrush( Qt.gray ) )
        self.tblAutoFields.setItem( row, 1, item )
        item = QTableWidgetItem( autoField['expression'] )
        if not autoField['enabled']: 
            item.setForeground( QBrush( Qt.gray ) )
        self.tblAutoFields.setItem( row, 2, item )
        item = QTableWidgetItem( QApplication.translate( "AutoFieldsDockWidgetPy", 
            "Enabled" ) if autoField['enabled'] else QApplication.translate( "AutoFieldsDockWidgetPy", "Disabled" ) )
        if not autoField['enabled']: 
            item.setForeground( QBrush( Qt.gray ) )        
        self.tblAutoFields.setItem( row, 3, item )
        
        if freezeSorting:
            self.tblAutoFields.setSortingEnabled( True )
        
        
    def updateRemoveAutoFieldButton( self ):
        """ Enable/disable button to remove AutoFields when appropriate """
        self.btnRemoveAutoFields.setEnabled( len( self.tblAutoFields.selectedItems() ) / 4 )
    
    
    def removeAutoFieldFromTable( self ):
        """ Show a confirmation dialog for all AutoFields selected.
            If confirmed, remove AutoFields from table.
        """
        # Column 0 has the AutoField id
        autoFieldsToRemove = [ item.data( Qt.UserRole ) for item in self.tblAutoFields.selectedItems() if item.column() == 0 ]
        
        reply = QMessageBox.question( self.iface.mainWindow(), 
            QApplication.translate( "AutoFieldsDockWidgetPy", "Confirmation" ),
            QApplication.translate( "AutoFieldsDockWidgetPy", 
                "Do you really want to remove " ) + \
            str(len( autoFieldsToRemove )) + \
            (" AutoFields?" if len( autoFieldsToRemove ) > 1 else " AutoField?"), 
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No )

        if reply == QMessageBox.Yes:
            for autoFieldId in autoFieldsToRemove:
                self.autoFieldManager.removeAutoField( autoFieldId )
    
    
    def disconnectAll( self ):
        """ Terminates all SIGNAL/SLOT connections created by this class """
        QgsMapLayerRegistry.instance().legendLayersAdded.disconnect( self.populateLayersTable )
        QgsMapLayerRegistry.instance().layersRemoved.disconnect( self.populateLayersTable )
        self.tblLayers.itemSelectionChanged.disconnect( self.updateFieldAndExpressionControls )
        self.optNewField.toggled.disconnect( self.newFieldToggled )                
        self.cboField.currentIndexChanged.disconnect( self.fieldChanged )
        self.cboFieldType.currentIndexChanged.disconnect( self.fieldTypeChanged )
        self.btnSaveAutoField.clicked.disconnect( self.saveAutoField )
        self.btnNewCustomExpression.clicked.disconnect( self.setCustomExpression )        
        self.btnGroup.buttonClicked.disconnect( self.updateExpressionControls )      
        
        self.autoFieldManager.autoFieldCreated.disconnect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldRemoved.disconnect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldEnabled.disconnect( self.populateAutoFieldsTable )
        self.autoFieldManager.autoFieldDisabled.disconnect( self.populateAutoFieldsTable )
        self.tblAutoFields.itemSelectionChanged.disconnect( self.updateRemoveAutoFieldButton )
        self.btnRemoveAutoFields.clicked.disconnect( self.removeAutoFieldFromTable )
