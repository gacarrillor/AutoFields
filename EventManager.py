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

from qgis.core import ( QgsMapLayerRegistry, QgsFeatureRequest, QgsVectorLayer, 
    QgsExpression, QgsExpressionContext, QgsVectorDataProvider, QgsDistanceArea,
    QgsProject, GEO_NONE, QGis, QgsExpressionContextUtils, NULL )
from PyQt4.QtCore import QObject, QSettings, pyqtSignal, QVariant
from PyQt4.QtGui import QApplication

from functools import partial


class EventManager( QObject ):
    """ Class in charge of all SIGNAL/SLOT connections for AutoFields. 
        It creates and removes connections when appropriate.
    """

    layersAddedCheckIfAutoFields = pyqtSignal( list ) 
    autoFieldsReadyToBeDisabled = pyqtSignal( str )
    attributesAddedCheckIfAutoFields = pyqtSignal( str, list )
    attributesDeletedCheckIfAutoFields = pyqtSignal( str ) 
  
    def __init__( self, messageManager, iface, settingsPrefix ):
        QObject.__init__( self )
        self.iface = iface
        self.msg = messageManager
        self.settingsPrefix = settingsPrefix
        
        self.dictPartialSLOTs = {}   
        self.listProviderExpressions = ['$id'] # Expressions that work when data is saved to provider
        QgsMapLayerRegistry.instance().layersAdded.connect( self.layersAddedSetAttributesAddedEvent )
        QgsMapLayerRegistry.instance().layersAdded.connect( self.layersAddedEnableAutoFields )
        
        # For any unknown reason, connecting to the SIGNAL layersRemoved gives segfault
        # In the meantime, using layerRemoved instead
        # To test layersRemoved, change pyqtSignal( str ) argument to list, 
        # change AFM.disableAutoFields argument to layerIds and put its code into a for loop
        QgsMapLayerRegistry.instance().layerRemoved.connect( self.layersRemovedDisableAutoFields )

        # Set AttributesAdded event for already existing layers 
        self.layersAddedSetAttributesAddedEvent( QgsMapLayerRegistry.instance().mapLayers().values() )
        
        self.afm = None 

        
    def setEventsForAutoField( self, autoFieldId, dictProperties ):
        """ Set all events for updating an AutoField's value """
        if not dictProperties['enabled']:
            return
          
        if not 'layerId' in dictProperties:
            self.msg.show( "[Warning] Could not set events for AutoField " + \
                autoFieldId + ". Layer id was not found in dictionary.", 
                'warning', True )
            return
        
        layer = QgsMapLayerRegistry.instance().mapLayer( dictProperties['layerId'] )
        capabilities = layer.dataProvider().capabilities()

        # Create SIGNAL/SLOT connections to update AutoField
        if dictProperties['expression'].startswith("spatial:"):
            layer.featureAdded.connect( self.spatialUpdate )
            layer.geometryChanged.connect( self.spatialUpdate )
        else:
            expression = QgsExpression( dictProperties['expression'] )
            self.dictPartialSLOTs[autoFieldId] = {}
            self.dictPartialSLOTs[autoFieldId]['layer'] = partial( self.expressionBasedUpdate, layer, dictProperties )
            
            if capabilities & QgsVectorDataProvider.AddFeatures:
                # TODO when bug #15311 is fixed, this block should work better
                # Special case because $id is assigned by the provider when new feature is saved
                #if dictProperties['expression'] in self.listProviderExpressions: 
                #    self.dictPartialSLOTs[autoFieldId]['provider'] = partial( self.providerExpressionBasedUpdate, layer, dictProperties )
                #    layer.committedFeaturesAdded.connect( self.dictPartialSLOTs[autoFieldId]['provider'] )
                #else:
                #    layer.featureAdded.connect( self.dictPartialSLOTs[autoFieldId]['layer'] )
            
                # Workaround
                self.dictPartialSLOTs[autoFieldId]['provider'] = partial( self.providerExpressionBasedUpdate, layer, dictProperties )
                layer.committedFeaturesAdded.connect( self.dictPartialSLOTs[autoFieldId]['provider'] )
                
                # We need to warn users about addFeatures updating only when saving
                self.dictPartialSLOTs[autoFieldId]['featureAddedMessage'] = partial( self.printFeatureAddedMessage, layer )
                layer.featureAdded.connect( self.dictPartialSLOTs[autoFieldId]['featureAddedMessage'] )
            
            if capabilities & QgsVectorDataProvider.ChangeGeometries:   
                layer.geometryChanged.connect( self.dictPartialSLOTs[autoFieldId]['layer'] )
                    
            if capabilities & QgsVectorDataProvider.ChangeAttributeValues:
                layer.attributeValueChanged.connect( self.dictPartialSLOTs[autoFieldId]['layer'] )

        # If a field participating in an AutoField is removed, the AutoField should be disabled
        if capabilities & QgsVectorDataProvider.DeleteAttributes:
            layer.committedAttributesDeleted.connect( self.attributesDeletedDisableAutoFields ) #lyrId, [idx]
        
        
    def removeEventsForAutoField( self, autoFieldId, layer, expression ):
        """ Disconnect SIGNALS/SLOTS created by the plugin on this layer.
            Since there seems to be impossible to get a list of connected 
            functions to every SIGNAL, try to disconnect all SLOTs this plugin 
            connects to, from all SIGNALs this plugin uses.
            Additionally, use dict of SLOTs to disconnect partial SLOTs.
        """
        try:
            # TODO when bug #15311 is fixed, this block should work better
            #if expression in self.listProviderExpressions:
            #    layer.committedFeaturesAdded.disconnect( self.dictPartialSLOTs[autoFieldId]['provider'] ) 
            #else:
            #    layer.featureAdded.disconnect( self.dictPartialSLOTs[autoFieldId]['layer'] )
            
            # Workaround
            layer.committedFeaturesAdded.disconnect( self.dictPartialSLOTs[autoFieldId]['provider'] ) 
            layer.featureAdded.disconnect( self.dictPartialSLOTs[autoFieldId]['featureAddedMessage'] ) 
        except TypeError:
            pass
        try:
            layer.geometryChanged.disconnect( self.dictPartialSLOTs[autoFieldId]['layer'] ) 
        except TypeError:
            pass 
        try: 
            layer.attributeValueChanged.disconnect( self.dictPartialSLOTs[autoFieldId]['layer'] )
        except TypeError:
            pass 
        try: 
            layer.committedAttributesDeleted.disconnect( self.attributesDeletedDisableAutoFields )
        except TypeError:
            pass 
            
        del self.dictPartialSLOTs[autoFieldId]
                    

    def setAFM( self, afm ): # Hack to avoid a QGIS bug
        self.afm = afm
        
        
    def printFeatureAddedMessage( self, layer, featureId ):        
        """ SLOT to print a warning message letting the users know they must 
            save in order to see calculated values when a feature is added.        
        """
        if self.iface:
            settings = QSettings()
            showMessage = settings.value( self.settingsPrefix + "/showMessageFeatureAdded", True, type=bool )         
            if showMessage:
                self.msg.showWithButton( QApplication.translate( "EventManager", 
                        "When adding NEW features, you'll only see AutoField updates AFTER you SAVE your edits." ), 
                    QApplication.translate( "EventManager", "Don't show this anymore" ),
                    self.featureAddedMessageButtonAction,
                    'info' )

    
    def featureAddedMessageButtonAction( self ):
        """ SLOT (logic) for the pressed SIGNAL button of a messagebar. """
        self.msg.show( "[Info] 'Don't show this anymore' button was clicked. This logging message should only be seen once.", 'info', True )        
        settings = QSettings()
        settings.setValue( self.settingsPrefix + "/showMessageFeatureAdded", False )
    
        
    def providerExpressionBasedUpdate( self, layer, dictProperties, layerId, features ):
        """ SLOT for expressions that make sense only after new features are saved 
            to the provider. 
        """
        for feature in features:
            self.expressionBasedUpdate( layer, dictProperties, feature.id() )

 
    def expressionBasedUpdate( self, layer, dictProperties, featureId, index=None, value=None ):
        """ Defines the logic of the expression-based update to be applied.
            This SLOT listens to featureAdded, geometryChanged, and attributeValueChanged SIGNALS.
        """
        # Check if AutoField is there, otherwise return
        fieldIndex = layer.fieldNameIndex( dictProperties['field'] )
        if fieldIndex == -1:
            self.msg.show(
                QApplication.translate( "EventManager", "[Error] Updating AutoField " ) + \
                dictProperties['field'] + \
                QApplication.translate( "EventManager", " in layer " ) + \
                layer.name() + QApplication.translate( "EventManager", " was NOT possible." ) + \
                QApplication.translate( "EventManager", " Perhaps you just removed it but haven't saved the changes yet?" ),
                'warning' )
            return

        event = ""
        result = None

        expression = QgsExpression( dictProperties['expression'] )
        if expression.hasParserError():
            self.msg.show( QApplication.translate( "EventManager", "[Error] (Parsing) " ) + \
                expression.parserErrorString(), 'critical' )
            result = NULL

        # Avoid infinite recursion (changing the same attribute value infinitely).
        if not index is None: # Filters out the featureAdded SIGNAL       
            if type( index ) == int: # Filters out the geometryChanged SIGNAL
                
                if index == fieldIndex: # This call comes from the same AutoField, so return
                    return
                
                if self.afm.isFieldAnAutoField( layer, layer.fields()[index].name() ): # Call from AutoField, don't listen
                    # This is to prevent corrupting the layerEditBuffer and being bitten by:
                    #   Fatal: ASSERT: "mChangedAttributeValues.isEmpty()" in file /tmp/buildd/qgis-2.14.2+20trusty/src/core/qgsvectorlayereditbuffer.cpp, line 585
                    return 
                
                #if type(value)==QPyNullVariant: 
                    # Vector layers with numeric field whose value for 1st feature is NULL
                    #   trigger an attributeValueChanged SIGNAL when start editing from the
                    #   attribute table window. We use this conditional to avoid such SIGNAL.
                    #   The ideal case is that such NULL valued SIGNAL shouldn't be emitted by QGIS.
                #    return  
                # While the previous block reduces the number of times attributeValueChanged
                #   is called from the attribute table, it leads to a QGIS bug:
                #   Fatal: ASSERT: "mChangedAttributeValues.isEmpty()" in file /tmp/buildd/qgis-2.14.2+20trusty/src/core/qgsvectorlayereditbuffer.cpp, line 585
                #   I prefer the attributeValueChanged to be called multiple 
                #   times (inefficient) than to open the possibility to a bug. 
                # As soon as QGIS bug #15272 is solved, the number of calls will be reduced!
                
                event = "attributeValueChanged"
            else:
                event = "geometryChanged"
        else:
            event = "featureAdded"
            
        feature = layer.getFeatures( QgsFeatureRequest( featureId ) ).next()
        
        if result is None:
            context = QgsExpressionContext()
            context.appendScope( QgsExpressionContextUtils.globalScope() )
            context.appendScope( QgsExpressionContextUtils.projectScope() )
            context.appendScope( QgsExpressionContextUtils.layerScope( layer ) )
            context.setFields( feature.fields() )
            context.setFeature( feature )

            if expression.needsGeometry():
                if self.iface:
                    # This block was borrowed from QGIS/python/plugins/processing/algs/qgis/FieldsCalculator.py 
                    da = QgsDistanceArea()
                    da.setSourceCrs( layer.crs().srsid() )
                    da.setEllipsoidalMode( self.iface.mapCanvas().mapSettings().hasCrsTransformEnabled() )
                    da.setEllipsoid( QgsProject.instance().readEntry( 'Measure', '/Ellipsoid', GEO_NONE )[0] )
                    expression.setGeomCalculator( da )
                    if QGis.QGIS_VERSION_INT >= 21400: # Methods added in QGIS 2.14
                        expression.setDistanceUnits( QgsProject.instance().distanceUnits() ) 
                        expression.setAreaUnits( QgsProject.instance().areaUnits() )
            
            expression.prepare( context )
            result = expression.evaluate( context )
            
            if expression.hasEvalError():
                self.msg.show( QApplication.translate( "EventManager", "[Error] (Evaluating) " ) + \
                    expression.evalErrorString(), 'critical' )
                result = NULL
        
        field = layer.fields()[fieldIndex]
        res = field.convertCompatible( result )
        # If result is None, res will be None, but even in that case, QGIS knows
        #   what to do with it while saving, it seems it's treated as NULL.
        

        # TODO when bug #15311 is fixed, this block should work better
        #if dictProperties['expression'] in self.listProviderExpressions: 
        #    # Save directly to provider
        #    layer.dataProvider().changeAttributeValues( { featureId : { fieldIndex : res } } )
        #else: # Save to layer
        #    layer.changeAttributeValue( featureId, fieldIndex, res )
         
        # Workaround 
        if event == 'featureAdded': # Save directly to the provider
            layer.dataProvider().changeAttributeValues( { featureId : { fieldIndex : res } } )
        else: # Save to layer
            layer.changeAttributeValue( featureId, fieldIndex, res )
        
        self.msg.show( "[Info] * AutoField's value updated to " + unicode(res) + \
            ", (" + layer.name() + "." + dictProperties['field'] + ") by " + event +".", 'info', True )
        
        
    def spatialUpdate( self ):
        pass
        

    def layersAddedEnableAutoFields( self, mapLayers ): # QgsMapLayer
        """ Some layers were added, check if some AutoFields should be enabled """
        # As the enabled status must be updated in both QSettings and dict, 
        # let proper module know it's time to do so.
        self.layersAddedCheckIfAutoFields.emit( mapLayers )
        
        
    def layersRemovedDisableAutoFields( self, layerIds ):
        """ Some layers were removed, disable all their AutoFields. 
            Since the layers objects are being destroyed, no need to disconnect 
            AutoFields events.
        """       
        # As the disabled status must be updated in both QSettings and dict, 
        # let the proper module know it's time to do so.
        self.autoFieldsReadyToBeDisabled.emit( layerIds )
        
        
    def attributesAddedEnableAutoFields( self, layerId, fields ): 
        """ Some fields on this layer were added, enable AutoFields if needed """
        self.attributesAddedCheckIfAutoFields.emit( layerId, fields )
    
        
    def attributesDeletedDisableAutoFields( self, layerId, listFieldIndexes ):
        """ Some fields on this layer were removed, disable AutoFields if needed """           
        self.attributesDeletedCheckIfAutoFields.emit( layerId )        
        
        
    def layersAddedSetAttributesAddedEvent( self, mapLayers ): # QgsMapLayer
        """ Set event to listen to attributes added in each of the mapLayers.
            If an attribute added 'completes' an AutoField, the latter should be enabled.
            This connection is not disconnected manually. It ends when layer is removed.
        """
        for layer in mapLayers:
            if type( layer ) is QgsVectorLayer:
                if layer.dataProvider().capabilities() & QgsVectorDataProvider.AddAttributes:
                    layer.committedAttributesAdded.connect( self.attributesAddedEnableAutoFields ) #lyrId, list
    
        
    def disconnectAll( self ):
        """ Terminates all SIGNAL/SLOT connections created by this class """
        QgsMapLayerRegistry.instance().layersAdded.disconnect( self.layersAddedSetAttributesAddedEvent )
        QgsMapLayerRegistry.instance().layersAdded.disconnect( self.layersAddedEnableAutoFields )
        QgsMapLayerRegistry.instance().layerRemoved.disconnect( self.layersRemovedDisableAutoFields )
        
