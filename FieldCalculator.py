# -*- coding:utf-8 -*-
"""
/***************************************************************************
AutoFields
A QGIS plugin
Automatic attribute updates when creating or modifying vector features
                             -------------------
begin                : 2016-09-08 
copyright            : (C) 2016 by Germán Carrillo (GeoTux)
email                : gcarrillo@linuxmail.org 
Adapted from         : https://github.com/qgis/QGIS/blob/322da8b2cf522bc0d6e5d1ba03f4f0597cdf09d2/python/plugins/processing/algs/qgis/FieldsCalculator.py
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

from qgis.core import ( QgsExpression, QgsExpressionContext,
    QgsExpressionContextUtils, QgsDistanceArea, QgsProject, QGis, GEO_NONE )
from PyQt4.QtGui import QApplication

class FieldCalculator():
    """ Class to perform field calculations on existing features. 
        Not the core of the plugin, but a helpful option.
        Adapted from QGIS/python/plugins/processing/algs/qgis/FieldsCalculator.py 
    """     

    def __init__( self, messageManager, iface ):
        self.msg = messageManager
        self.iface = iface
    
        
    def calculate( self, layer, fieldName, expression ):
        if ( layer.featureCount() == 0 ):
            self.msg.show( "[Info] * No existing features on layer " + layer.name() + " to calculate expression.", 'info', True )
            return

        expression = QgsExpression( expression )
        if expression.hasParserError():
            self.msg.show( QApplication.translate( "AutoFields-FieldCalculator", "[Error] (Parsing) " ) + \
                expression.parserErrorString(), 'critical' )
            return
        
        context = QgsExpressionContext()
        context.appendScope( QgsExpressionContextUtils.globalScope() )
        context.appendScope( QgsExpressionContextUtils.projectScope() )
        context.appendScope( QgsExpressionContextUtils.layerScope( layer ) )
        context.setFields( layer.fields() )

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

        fieldIndex = layer.fieldNameIndex( fieldName )
        if fieldIndex == -1:
            return           
        field = layer.fields()[fieldIndex]
        
        dictResults = {}
        for feature in layer.getFeatures():
            context.setFeature( feature )
            result = expression.evaluate( context )
            if expression.hasEvalError():
                self.msg.show( QApplication.translate( "AutoFields-FieldCalculator", "[Error] (Evaluating) " ) + \
                    expression.evalErrorString(), 'critical' )
                return
                
            dictResults[feature.id()] = { fieldIndex: field.convertCompatible( result ) }
            

        layer.dataProvider().changeAttributeValues( dictResults )
        
        self.msg.show( "[Info] * An expression was calculated on existing features of layer " + layer.name() + ", field " + fieldName + ".", 'info', True )
        
    
    
    
    
