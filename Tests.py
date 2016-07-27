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
import os.path
import unittest

from qgis.core import ( QgsApplication, QgsMapLayerRegistry, QgsVectorLayer, 
    QgsField, QgsFeature, QgsGeometry, QgsPoint )

from PyQt4.QtCore import QSettings, QVariant

from AutoFieldManager import AutoFieldManager
from MessageManager import MessageManager

class AutoFieldsTests( unittest.TestCase ):

    @classmethod
    def setUpClass( self ):
        self.msg = MessageManager( 'debug', None ) 
        self.msg.show( "Info! SetUp started", 'info', True )
        #Initialize QGIS app
        app = QgsApplication([], True)
        QgsApplication.setPrefixPath("/usr", True)
        QgsApplication.initQgis()
        
        #Configure QSettings (organization and application name)
        self.settings = QSettings("GeoTux", "QGIS-Plugin-Test") 

        #Load layer, add field f1, and add layer to Registry
        baseDir = os.path.dirname( os.path.realpath( __file__ ) )
        self.layerPath = os.path.join( baseDir, 'test_data', 'test_points.shp' )
        self.layer = QgsVectorLayer( self.layerPath, 'puntos', 'ogr' )   
        self.layer.dataProvider().addAttributes([QgsField('f1', QVariant.Double)])
        self.layer.updateFields()
        QgsMapLayerRegistry.instance().addMapLayer( self.layer )  
        
        #Instantiate AutoFieldManager
        self.autoFieldManager = AutoFieldManager( self.msg, None, '/AutoFieldsTest', 'GeoTux', 'QGIS-Plugin-Test' )
        
            
    def readStoredSettings( self, layer, fieldName ):
        """ Helper function to get a dictionary of stored QSettings for an AutoField """
        dictTmpProperties = {}
        autoFieldId = self.autoFieldManager.buildAutoFieldId( layer, fieldName )
        self.settings.beginGroup('/AutoFieldsTest/data/' + autoFieldId)
        dictTmpProperties['layer'] = self.settings.value( "layer", "", type=str )
        dictTmpProperties['field'] = self.settings.value( "field", u"", type=unicode )
        dictTmpProperties['expression'] = self.settings.value( "expression", u"", type=unicode )
        dictTmpProperties['layer2'] = self.settings.value( "layer2", "", type=str )
        dictTmpProperties['field2'] = self.settings.value( "field2", "", type=str )            
        dictTmpProperties['enabled'] = self.settings.value( "enabled", False, type=bool )
        self.settings.endGroup()
                
        return dictTmpProperties

    def test01CreateEnabledAutoField( self ):
        """ QSettings should be properly stored, AutoField should be enabled """
        self.msg.show( "Info! Test 1 started", 'info', True )

        self.autoFieldManager.createAutoField(
            layer=self.layer, 
            fieldName=u'f1', 
            expression=u'$x'
        )

        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' )      
        dictExpectedProperties = {
            'layer':self.layerPath,
            'field':u'f1',
            'expression':u'$x',
            'layer2':"",
            'field2':"",
            'enabled':True
        }
        
        self.assertEqual( dictTmpProperties, dictExpectedProperties )
        
        
    def test02AvoidTwoAutoFieldsOnSameField( self ):
        """ AutoField should not be created if another one already exists on the same field."""
        self.msg.show( "Info! Test 2 started", 'info', True )

        res = self.autoFieldManager.createAutoField(
            layer=self.layer, 
            fieldName=u'f1', 
            expression=u'$y'
        )
        
        self.assertFalse( res )
        
        
    def test03EditAutoFieldLayer( self ):
        """ AutoField value should be updated if a feature is added.
            Note: It cannot handle the case when writing directly to the provider,
              as QGIS doesn't have a SIGNAL for that.
              self.layer.dataProvider().addFeatures( [ tmpFeature ] )        
         """
        self.msg.show( "Info! Test 3 started", 'info', True )

        tmpFeature = QgsFeature( self.layer.pendingFields() )
        tmpFeature.setGeometry( QgsGeometry.fromPoint( QgsPoint(-74.4, 4.5) ) )

        # Either 1:
        self.layer.startEditing()
        self.layer.addFeature( tmpFeature )
        self.layer.commitChanges()
        
        # Or 2:
        #with edit( self.layer ):
        #    self.layer.addFeature( tmpFeature )
            
        addedFeature = self.layer.getFeatures().next()
        self.assertEquals( addedFeature['f1'], -74.4 )


    def test04ChangeAttributeValue( self ):
        """ AutoField value should be updated if another AutoField value is changed """
        self.msg.show( "Info! Test 4 started", 'info', True )

        res = self.autoFieldManager.createAutoField(
            layer=self.layer, 
            fieldName=u'modified', 
            expression=u'\'now: \' + to_string("f1")'
        )

        self.layer.startEditing()
        self.layer.changeAttributeValue( 0, self.layer.fieldNameIndex( u'id' ), 1 )
        self.layer.commitChanges()
            
        feature = self.layer.getFeatures().next()
        self.assertEquals( feature['modified'], 'now: -74.4' )

    
    def test05FieldRemovedThenDisableAutoField( self ):
        """ AutoField should be disabled if its base field is removed """
        self.msg.show( "Info! Test 5 started", 'info', True )

        fieldIndex = self.layer.fieldNameIndex( u'f1' )
        self.layer.startEditing()
        self.layer.deleteAttribute( fieldIndex )
        self.layer.commitChanges()
        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' )    
        
        self.assertFalse( dictTmpProperties['enabled'] )        
            

    def test06MissingFieldAddedThenEnableAutoField( self ):
        """ AutoField should be enabled if missing field is added """
        self.msg.show( "Info! Test 6 started", 'info', True )    

        self.layer.startEditing()
        self.layer.addAttribute( QgsField( 'f1', QVariant.Double, len=10, prec=2 ) )
        self.layer.commitChanges()
        
        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' )    
        
        self.assertTrue( dictTmpProperties['enabled'] )   

        
    def test07LayerRemovedThenDisableAutoField( self ):
        """ AutoField should be disabled if its base layer is removed """
        self.msg.show( "Info! Test 7 started", 'info', True )

        QgsMapLayerRegistry.instance().removeMapLayer( self.layer.id() )

        # removeMapLayer deletes the underlying object, so create it again
        self.layer = QgsVectorLayer( self.layerPath, 'puntos', 'ogr' )   
        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' )    
        
        self.assertFalse( dictTmpProperties['enabled'] )
        
     
    def test08MissingLayerAddedThenEnableAutoField( self ):
        """ AutoField should be enabled if missing layer is added """
        self.msg.show( "Info! Test 8 started", 'info', True )

        # test07 deletes the layer object, so create it again
        self.layer = QgsVectorLayer( self.layerPath, 'puntos', 'ogr' )
        QgsMapLayerRegistry.instance().addMapLayer( self.layer )  
        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' )    
        
        self.assertTrue( dictTmpProperties['enabled'] )
           
        
    def test09RemoveAutoField( self ):
        """ QSettings should be deleted for the removed AutoField """
        self.msg.show( "Info! Test 9 started", 'info', True )

        # test07 deletes the layer object, so create it again
        self.layer = QgsVectorLayer( self.layerPath, 'puntos', 'ogr' )
        autoFieldId = self.autoFieldManager.buildAutoFieldId( self.layer, u'f1')
        self.autoFieldManager.removeAutoField( autoFieldId )
        dictTmpProperties = self.readStoredSettings( self.layer, u'f1' ) 
        
        self.assertEqual( dictTmpProperties, {'layer':"",'field':"",'expression':"",'layer2':"",'field2':"",'enabled':False} )
        

    @classmethod    
    def tearDownClass( self ):   
        self.msg.show( "Info! TearDown started", 'info', True )
    
        # test07 deletes the layer object, so create it again
        self.layer = QgsVectorLayer( self.layerPath, 'puntos', 'ogr' )

        #Remove AutoField modified
        autoFieldId = self.autoFieldManager.buildAutoFieldId( self.layer, u'modified' )
        self.autoFieldManager.removeAutoField( autoFieldId )

        #Delete field f1
        fieldIndex = self.layer.fieldNameIndex('f1')
        self.layer.dataProvider().deleteAttributes( [fieldIndex] )
        self.layer.updateFields()
        
        #Delete features from test layer
        fIds = self.layer.allFeatureIds()
        self.layer.dataProvider().deleteFeatures( fIds )
        
        #Remove layer from Registry
        QgsMapLayerRegistry.instance().removeMapLayer( self.layer.id() )
        self.msg.show( "Info! TearDown finished", 'info', True )

        QgsApplication.exitQgis()
               
if __name__ == "__main__":
    unittest.main()
    
