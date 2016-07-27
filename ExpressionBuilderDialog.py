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

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QDialog, QDialogButtonBox

from Ui_ExpressionBuilder import Ui_ExpressionDialog

class ExpressionBuilderDialog( QDialog, Ui_ExpressionDialog ):

    def __init__( self, parent ): 
        QDialog.__init__( self, parent ) 
        self.setupUi( self )
        self.setModal( True )
        self.expressionBuilderWidget.loadRecent( 'fieldcalc' )
        self.buttonBox.button( QDialogButtonBox.Ok ).setEnabled( False )
        self.expression = ''
        self.expressionBuilderWidget.expressionParsed.connect( self.expressionChanged )
        
    def expressionChanged( self, valid ):
        self.buttonBox.button( QDialogButtonBox.Ok ).setEnabled( valid )
    
    def keyPressEvent( self, event ):
        if event.key() == Qt.Key_Escape:
            self.reject()
    
    def accept( self ):
        self.expression = self.expressionBuilderWidget.expressionText().strip()        
        self.expressionBuilderWidget.saveToRecent( 'fieldcalc' )
        self.done( 1 )

    def reject( self ):
        self.expressionBuilderWidget.setExpressionText( self.expression )
        self.done( 0 )

