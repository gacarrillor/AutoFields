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
#from qgis.core import QgsMessageLog
from qgis.gui import QgsMessageBar
from PyQt4.QtGui import QPushButton

class MessageManager():

    def __init__( self, mode='production', iface=None ):
        self.mode = mode # 'production' or 'debug'
        self.iface = iface
        self.levelList = ['info', 'warning', 'critical', 'success']
            
    
    def show( self, message, type='info', justForDebug=False ):
        """ Prints the message to the appropriate output """        
        if self.mode == 'production':
            if not justForDebug:
                self.iface.messageBar().pushMessage( "AutoFields", message, 
                    level=self.levelList.index(type), duration=15 )
        else: # Print all to console
            print "[AutoFields]", message 
            #QgsMessageLog.instance().logMessage( "AutoFields: "+message,"", QgsMessageLog.WARNING )
            
    
    def showWithButton( self, message, buttonText, slot, type='info' ):
        """ Prints a message with a button. 
        """
        widget = self.iface.messageBar().createMessage( "AutoFields", message )
        button = QPushButton( widget  )
        button.setText( buttonText )
        button.pressed.connect( slot )
        widget.layout().addWidget( button )
        self.iface.messageBar().pushWidget( widget, level=self.levelList.index(type), duration=15 )
        
