
all: Ui_AutoFields_dock.py Ui_ExpressionBuilder.py Ui_Export_AutoFields.py Ui_Import_AutoFields.py Ui_Assign_AutoField_to_Layer.py resources_rc.py i18n/AutoFields_es.qm

clean:
	rm -f Ui_AutoFields_dock.py Ui_ExpressionBuilder.py Ui_Export_AutoFields.py Ui_Import_AutoFields.py Ui_Assign_AutoField_to_Layer.py
	rm -f resources_rc.py
	rm -f i18n/AutoFields_es.qm
	rm -f *.pyc *~

resources_rc.py: resources.qrc
	pyrcc4 -o resources_rc.py resources.qrc

Ui_AutoFields_dock.py: Ui_AutoFields_dock.ui
	pyuic4 -o Ui_AutoFields_dock.py Ui_AutoFields_dock.ui

Ui_ExpressionBuilder.py: Ui_ExpressionBuilder.ui
	pyuic4 -o Ui_ExpressionBuilder.py Ui_ExpressionBuilder.ui

Ui_Export_AutoFields.py: Ui_Export_AutoFields.ui
	pyuic4 -o Ui_Export_AutoFields.py Ui_Export_AutoFields.ui

Ui_Import_AutoFields.py: Ui_Import_AutoFields.ui
	pyuic4 -o Ui_Import_AutoFields.py Ui_Import_AutoFields.ui

Ui_Assign_AutoField_to_Layer.py: Ui_Assign_AutoField_to_Layer.ui
	pyuic4 -o Ui_Assign_AutoField_to_Layer.py Ui_Assign_AutoField_to_Layer.ui

i18n/AutoFields_es.qm: i18n/AutoFields_es.ts
	lrelease i18n/AutoFields.pro
