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
def name(): 
  return "AutoFields" 

def description():
  return "Automatic vector field updates when modifying or creating features"

def version(): 
  return "Version 0.2.5" 

def qgisMinimumVersion():
  return "2.0"

def icon():
    return "icon.png"

def authorName():
  return "Germán Carrillo"

def classFactory( iface ): 
  from AutoFields import AutoFields
  return AutoFields( iface )


