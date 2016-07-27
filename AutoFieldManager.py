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

from qgis.core import QgsMapLayerRegistry, QgsVectorLayer, QgsVectorDataProvider
from PyQt4.QtCore import QObject, QSettings, pyqtSignal
from PyQt4.QtGui import QApplication

from EventManager import EventManager

class AutoFieldManager( QObject ):
    """ Class in charge of the AutoFields administration. 
        Main class of the plugin, as AutoFields can only be created, removed, 
          and overwritten from it.
    """    
    
    autoFieldCreated = pyqtSignal( str ) 
    autoFieldRemoved = pyqtSignal( str )
    autoFieldEnabled = pyqtSignal( str )
    autoFieldDisabled = pyqtSignal( str ) 

    def __init__( self, messageManager, iface, settingsPrefix="/AutoFields", organizationName=None, applicationName=None ):
        QObject.__init__( self )
        self.msg = messageManager
        self.settings = QSettings( organizationName, applicationName ) if organizationName and applicationName else QSettings()
        self.dictAutoFields = {}
        self.settingsPrefix = settingsPrefix
        self.eventManager = EventManager( self.msg, iface, settingsPrefix )
        self.eventManager.layersAddedCheckIfAutoFields.connect( self.checkAndEnableAutoFieldsForLayers )
        self.eventManager.autoFieldsReadyToBeDisabled.connect( self.disableAutoFields )
        self.eventManager.attributesAddedCheckIfAutoFields.connect( self.checkAndEnableAutoFieldsForLayerFields )
        self.eventManager.attributesDeletedCheckIfAutoFields.connect( self.checkAndDisableAutoFieldsForLayer )
        
        self.eventManager.setAFM( self )
    
    
    def createAutoField( self, layer, fieldName, expression, layer2="", field2="" ):
        """ Add AutoField properties to both QSettings and dictAutoFields """    
        if not layer or not type(layer) is QgsVectorLayer:
            self.msg.show( 
                QApplication.translate( "AutoFieldManager", "[Error] A 'layer' parameter of type QgsVectorLayer must be given." ),
                'warning' )
            return False
        if not layer.hasGeometryType(): 
            self.msg.show( QApplication.translate( "AutoFieldManager", 
                "[Error] The layer has an unknown geometry, but AutoFieds does not support alphanumeric tables." ),
            'warning' )
            return False       
        
        capabilities = layer.dataProvider().capabilities()
        if not ( capabilities & QgsVectorDataProvider.ChangeAttributeValues ):
            self.msg.show( QApplication.translate( "AutoFieldManager",
                "[Error] The vector layer provider does not allow to change attribute values.\nYou would need to export the data to another format for adding AutoFields." ), 
                'warning' )
            return False    
        if not ( capabilities & QgsVectorDataProvider.AddFeatures ):
            self.msg.show( "[Warning] The vector layer provider does not allow to add features.", 'warning', True ) 
        if not ( capabilities & QgsVectorDataProvider.ChangeGeometries ):
            self.msg.show( "[Warning] The vector layer provider does not allow to change geometries.", 'warning', True )
        
        if layer.isReadOnly():
            self.msg.show( QApplication.translate( "AutoFieldManager", 
                "[Error] The vector layer is read only, so no AutoFields can be created on it." ),
                'warning' )
            return False       
            
        if not fieldName or type(fieldName) != unicode:
            self.msg.show( QApplication.translate( "AutoFieldManager",
                "[Error] A 'fieldName' parameter of type unicode must be given." ), 
                'warning' )
            return False
        if not fieldName.strip():
            self.msg.show( QApplication.translate( "AutoFieldManager", 
                "[Error] 'fieldName' variable has not a valid value." ), 'warning' )
            return False
            
        if layer.fieldNameIndex( fieldName ) == -1:
            self.msg.show( QApplication.translate( "AutoFieldManager", 
                "[Error] Layer " ) + layer.name() + \
                QApplication.translate( "AutoFieldManager", " has no field called " ) + \
                fieldName + QApplication.translate( "AutoFieldManager",
                ". You need to create it beforehand." ), 'warning' )
            return False
            
        #if layer.fields[layer.fieldNameIndex( field )].isEditable():
        #    print "Error: Field",field,"is not editable! It won't be possible to write in it."
        #    return False
            
        if not expression or type(expression) != unicode:
            self.msg.show( QApplication.translate( "AutoFieldManager",
                "[Error] An 'expression' parameter of type unicode must be given." ),
                'warning' )
            return False
        elif not expression.strip():
            self.msg.show( QApplication.translate( "AutoFieldManager",
                "[Error] 'expression' variable has not a valid value." ),
                'warning' )
            return False
        
        autoFieldId = self.buildAutoFieldId( layer, fieldName )
        
        self.msg.show( "Create AutoField with Id: " + autoFieldId, 'info', True )

        if self.isFieldAnAutoField( layer, fieldName ):
            self.msg.show( QApplication.translate( "AutoFieldManager", 
                "[Error] This field is already an AutoField. You cannot create another AutoField on the same field, but you can use overwriteAutoField(), which supports the same parameters." ),
                'warning' )
            return False
        
        # Create AutoField in dictionary
        self.dictAutoFields[autoFieldId] = { 'layer':layer.publicSource(), 
            'field':fieldName, 'expression':expression, 'layer2':layer2, 
            'field2':field2, 'layerId': layer.id() }
        self.dictAutoFields[autoFieldId]['enabled'] = self.validateAutoField( self.dictAutoFields[autoFieldId] )
               
        # Create AutoField in QSettings and set corresponding events
        self.writeAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )
        self.eventManager.setEventsForAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )

        self.msg.show( QApplication.translate( "AutoFieldManager", "The AutoField (" ) + \
            layer.name() + "." + fieldName + ": " + expression + \
            QApplication.translate( "AutoFieldManager", ") was created properly!" ), 'info' )
        self.autoFieldCreated.emit( autoFieldId )
        return True
    
    
    def overwriteAutoField( self, layer, fieldName, expression, layer2="", field2="" ):
        """ Logic to overwrite an existing AutoField in both QSettings and dictAutoFields """ 
        autoFieldId = self.buildAutoFieldId( layer, fieldName ) 
        if autoFieldId in self.dictAutoFields:
            self.removeAutoField( autoFieldId )        
            return self.createAutoField( layer, fieldName, expression, layer2, field2 )

        return False
        
    
    def removeAutoField( self, autoFieldId ):
        """ Get rid of AutoField from both QSettings and dictAutoFields """
        self.settings.beginGroup( self.settingsPrefix + "/data" )
        self.settings.remove( autoFieldId )
        self.settings.endGroup()
        self.settings.sync()
        
        # Disconnect SIGNAL/SLOTS for this AutoField
        if 'layerId' in self.dictAutoFields[autoFieldId]:
            if self.dictAutoFields[autoFieldId]['enabled']:
                layer = QgsMapLayerRegistry.instance().mapLayer( self.dictAutoFields[autoFieldId]['layerId'] )
                self.eventManager.removeEventsForAutoField( autoFieldId, layer, self.dictAutoFields[autoFieldId]['expression'] )
        
        del self.dictAutoFields[autoFieldId]
        self.autoFieldRemoved.emit( autoFieldId )
       
       
    def readAutoFields( self ):
        """ Read AutoFields from QSettings, ovewriting dictAutoFields """
        self.dictAutoFields = {}
        self.settings.beginGroup( self.settingsPrefix + "/data" )
        autoFieldsIds = self.settings.childGroups()
        self.settings.endGroup()
        for autoFieldId in autoFieldsIds:
            dictTmpProperties = {}
            self.settings.beginGroup( self.settingsPrefix + "/data/" + autoFieldId )
            dictTmpProperties['layer'] = self.settings.value( "layer", u"", type=unicode )
            dictTmpProperties['field'] = self.settings.value( "field", u"", type=unicode )
            dictTmpProperties['expression'] = self.settings.value( "expression", u"", type=unicode )
            dictTmpProperties['layer2'] = self.settings.value( "layer2", "", type=str )
            dictTmpProperties['field2'] = self.settings.value( "field2", "", type=str )            
            self.settings.endGroup()
            
            # Check whether the AutoField must be enabled or not
            layer = self.getLayer( dictTmpProperties['layer'] )
            if layer:
                dictTmpProperties['layerId'] = layer.id()

            dictTmpProperties['enabled'] = self.validateAutoField( dictTmpProperties )
            
            self.dictAutoFields[autoFieldId] = dictTmpProperties
            
        for autoFieldId in self.dictAutoFields.keys():
            self.eventManager.setEventsForAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )
    
    
    def writeAutoField( self, autoFieldId, dictProperties ):
        """ Write an AutoField from dictAutoFields to QSettings """
        self.settings.beginGroup( self.settingsPrefix + "/data/" + autoFieldId )
        self.settings.setValue( "layer", dictProperties['layer'] )
        self.settings.setValue( "field", dictProperties['field'] )
        self.settings.setValue( "expression", dictProperties['expression'] )
        self.settings.setValue( "layer2", dictProperties['layer2'] )
        self.settings.setValue( "field2", dictProperties['field2'] )
        self.settings.setValue( "enabled", dictProperties['enabled'] )
        self.settings.endGroup()
        self.settings.sync()
    
    
    def listAutoFields( self ):
        return self.dictAutoFields
    
    
    def validateAutoField( self, dictProperties ):
        """ Check whether this AutoField is ready or if there is something missing """
        if not 'layerId' in dictProperties:
            self.msg.show( "[Warning] A layer that is part of an AutoField was not found in QGIS registry.", 'warning', True )
            return False
            
        layer = QgsMapLayerRegistry.instance().mapLayer( dictProperties['layerId'] )
        if not layer:
            self.msg.show( "[Warning] Layer id " + dictProperties['layerId'] + " was not found in QGIS registry.", 'warning', True )
            return False
            
        if layer.fieldNameIndex( dictProperties['field'] ) == -1:
            self.msg.show( "[Warning] Field was not found in layer "+layer.name()+".", 'warning', True )
            return False
            
        # TODO add checks for layer2 and field2
            
        return True        
        
        
    def normalizeSource( self, source ):
        """ Avoid issues with spaces and other weird characters in AutoField ids """
        return source.replace(" ","").replace("\"","").replace("'","").replace("/","|").replace("\\","|")
           
           
    def buildAutoFieldId( self, layer, fieldName ):
        """ Centralizes the definition of AutoField identifiers """
        if not layer or not type(layer) is QgsVectorLayer:
            self.msg.show( "[Error] A 'layer' parameter of type QgsVectorLayer must be given.", 'warning', True )
            return None
        if not fieldName or type(fieldName) != unicode:
            self.msg.show( "[Error] A 'fieldName' parameter of type unicode must be given.", 'warning', True )
            return None
        
        return self.normalizeSource( layer.publicSource() ) + '@@' + fieldName


    def isFieldAnAutoField( self, layer, fieldName ):
        """ Returns whether a layer field is an AutoField or not """
        autoFieldId = self.buildAutoFieldId( layer, fieldName )
        return autoFieldId in self.dictAutoFields

        # Check if this AutoField already exists
        #self.settings.beginGroup( self.settingsPrefix + "/data" )
        #settingsChildGroups = self.settings.childGroups()
        #self.settings.endGroup()
        #if autoFieldId in settingsChildGroups:

        #def isFieldAutoField( self, layer, fieldName ):
        #    """ Hack to avoid a QGIS bug on eventManager.expressionBasedUpdate() """
        #    for autoFieldId in self.dictAutoFields:
        #        if self.dictAutoFields[autoFieldId]['layer'] == layer.publicSource():
        #            if self.dictAutoFields[autoFieldId]['field'] == fieldName:
        #                return True
        #    return False

                 
    def getFieldExpression( self, layer, fieldName ):
        """ If the given field is an AutoField, it returns its expression """
        autoFieldId = self.buildAutoFieldId( layer, fieldName ) 
        if autoFieldId in self.dictAutoFields:
            return self.dictAutoFields[autoFieldId]['expression']

        return ''
           
            
    def getLayer( self, autoFieldLayerSource ):
        """ Iterate layers and get one comparing sources """
        for tmpLayer in QgsMapLayerRegistry.instance().mapLayers().values():
            if self.compareLayersPublicSources( tmpLayer.publicSource(), autoFieldLayerSource ):
                return tmpLayer
        return None 
            
            
    def compareLayersPublicSources( self, source1, source2 ):
        """ Normalize sources before comparing them.
            On Windows, adding a layer from the Add Layer button and from 
              QGIS Browser give different directory separators (/ vs \\), which 
              hampers comparison.            
        """
        return self.normalizeSource( source1 ) == self.normalizeSource( source2 )
    
    
                   
    def checkAndEnableAutoFieldsForLayers( self, mapLayers ):
        """ After a notification on layers being added, check and enable AutoFields if needed.
            1. Check if added layers are part of currently disabled AutoFields
            2. Enable it in Dict
            3. Enable it in QSettings
            4. Connect its SIGNALS / SLOTS
        """
        for layer in mapLayers:
            for autoFieldId in self.dictAutoFields:
                if self.dictAutoFields[autoFieldId]['enabled'] == False: # Don't check enabled AutoFields
                    if self.compareLayersPublicSources( layer.publicSource(), self.dictAutoFields[autoFieldId]['layer'] ): #1
                        self.dictAutoFields[autoFieldId]['layerId'] = layer.id()
                        if self.validateAutoField( self.dictAutoFields[autoFieldId] ):
                            self.dictAutoFields[autoFieldId]['enabled'] = True #2
                            self.writeAutoField( autoFieldId, self.dictAutoFields[autoFieldId] ) #3
                            self.eventManager.setEventsForAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )#4   
                            self.autoFieldEnabled.emit( autoFieldId )
        
        
    def disableAutoFields( self, layerId ):
        """ After a notification on layers being removed, disable all their AutoFields """ 
        #for layerId in layerIds:
        for autoFieldId in self.dictAutoFields:
            if 'layerId' in self.dictAutoFields[autoFieldId]: 
                if layerId == self.dictAutoFields[autoFieldId]['layerId']:       
                    self.dictAutoFields[autoFieldId]['enabled'] = False
                    self.writeAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )
                    del self.dictAutoFields[autoFieldId]['layerId'] # layerId is meaningless now
                    self.autoFieldDisabled.emit( autoFieldId )
               
                   
    def checkAndEnableAutoFieldsForLayerFields( self, layerId, fields ):
        """ After a notification on fields being added, check and enable AutoFields if needed.
            1. Check if added fields are part of currently disabled AutoFields
            2. Enable it in Dict
            3. Enable it in QSettings
            4. Connect its SIGNALS / SLOTS 
        """
        for autoFieldId in self.dictAutoFields: 
            if self.dictAutoFields[autoFieldId]['enabled'] == False: # Don't check enabled AutoFields
                if 'layerId' in self.dictAutoFields[autoFieldId]: 
                    if layerId == self.dictAutoFields[autoFieldId]['layerId']: #1
                        for field in fields:
                            if field.name() == self.dictAutoFields[autoFieldId]['field']: 
                                if self.validateAutoField( self.dictAutoFields[autoFieldId] ):
                                    self.dictAutoFields[autoFieldId]['enabled'] = True #2
                                    self.writeAutoField( autoFieldId, self.dictAutoFields[autoFieldId] ) #3
                                    self.eventManager.setEventsForAutoField( autoFieldId, self.dictAutoFields[autoFieldId] )#4   
                                    self.autoFieldEnabled.emit( autoFieldId )
        
                   
    def checkAndDisableAutoFieldsForLayer( self, layerId ):
        """ After a notification on fields being removed, check and disable AutoFields if needed.
            1. Check if any field is missing in AutoFields set for this layer.
            2. Disable it in Dict
            3. Disable it in QSettings
            4. Disconnect its SIGNAL / SLOTS   
         """
        for autoFieldId in self.dictAutoFields:
            if self.dictAutoFields[autoFieldId]['enabled'] == True: # Don't check disabled AutoFields
                if layerId == self.dictAutoFields[autoFieldId]['layerId']:       
                    layer = QgsMapLayerRegistry.instance().mapLayer( layerId )    
                    if layer.fieldNameIndex( self.dictAutoFields[autoFieldId]['field'] ) == -1: #1
                        self.dictAutoFields[autoFieldId]['enabled'] = False #2
                        self.writeAutoField( autoFieldId, self.dictAutoFields[autoFieldId] ) #3
                        self.eventManager.removeEventsForAutoField( autoFieldId, layer, self.dictAutoFields[autoFieldId]['expression'] ) #4
                        self.autoFieldDisabled.emit( autoFieldId )


    def disconnectAll( self ):
        """ Terminates all SIGNAL/SLOT connections created by this class """
        self.eventManager.layersAddedCheckIfAutoFields.disconnect( self.checkAndEnableAutoFieldsForLayers )
        self.eventManager.autoFieldsReadyToBeDisabled.disconnect( self.disableAutoFields )
        self.eventManager.attributesAddedCheckIfAutoFields.disconnect( self.checkAndEnableAutoFieldsForLayerFields )
        self.eventManager.attributesDeletedCheckIfAutoFields.disconnect( self.checkAndDisableAutoFieldsForLayer )
        
        # Disconnect all SIGNAL/SLOT connections created by eventManager
        self.eventManager.disconnectAll()
        
        # Disconnect all events for each enabled AutoField
        for autoFieldId in self.dictAutoFields:
            if self.dictAutoFields[autoFieldId]['enabled'] == True: # Don't check disabled AutoFields
                layerId = self.dictAutoFields[autoFieldId]['layerId']
                layer = QgsMapLayerRegistry.instance().mapLayer( layerId )
                self.eventManager.removeEventsForAutoField( autoFieldId, layer, self.dictAutoFields[autoFieldId]['expression'] )
            
