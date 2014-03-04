#!/usr/bin/env python
#
# License: BSD
#   https://raw.github.com/robotics-in-concert/rocon_qt_gui/license/LICENSE
#
##############################################################################
# Imports
##############################################################################

import os
import subprocess
import string
import uuid
import time

from PyQt4 import uic
from PyQt4.QtCore import QString  # pyqtSlot, SIGNAL, SLOT, QPoint, QEvent
from PyQt4.QtCore import Qt, QSize  # QFile, QIODevice, QAbstractListModel, pyqtSignal, QStringList
from PyQt4.QtGui import QIcon, QWidget, QLabel  # QFileDialog, QGraphicsScene, QImage, QPainter, QComboBox
from PyQt4.QtGui import QSizePolicy, QTextEdit, QPushButton, QDialog  # QCompleter, QBrush, QColor, QPen
from PyQt4.QtGui import QMainWindow, QCheckBox

from PyQt4.QtGui import QGridLayout, QVBoxLayout, QHBoxLayout  # QMessageBox, QTabWidget, QPlainTextEdit
#from PyQt4.QtSvg import QSvgGenerator

from rocon_console import console

from .remocon_info import RemoconInfo
from . import utils

##############################################################################
# Remocon
##############################################################################


class RemoconSub(QMainWindow):
    def __init__(self, parent, title, application, rocon_master_index="", rocon_master_name="", rocon_master_uri='localhost', host_name='localhost'):
        self.rocon_master_index = rocon_master_index
        self.rocon_master_uri = rocon_master_uri
        self.rocon_master_name = rocon_master_name
        self.host_name = host_name
        self._context = parent
        self.application = application

        super(RemoconSub, self).__init__(parent)
        self.initialised = False

        self._widget_app_list = QWidget()
        self._widget_role_list = QWidget()

        self.rocon_master_list = {}
        self.role_list = {}
        self.cur_selected_role = 0

        self.app_list = {}
        self.cur_selected_app = None

        self.remocon_info = RemoconInfo(stop_app_postexec_fn=self._set_stop_app_button)

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../ui/applist.ui")
        uic.loadUi(path, self._widget_app_list)

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../ui/rolelist.ui")
        uic.loadUi(path, self._widget_role_list)

        utils.setup_home_dirs()
        self.rocon_master_list_cache_path = os.path.join(utils.get_settings_cache_home(), "rocon_master.cache")
        self.scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts/")

        #role list widget
        self._widget_role_list.role_list_widget.setIconSize(QSize(50, 50))
        self._widget_role_list.role_list_widget.itemDoubleClicked.connect(self._select_role_list)
        self._widget_role_list.back_btn.pressed.connect(self._back_role_list)
        self._widget_role_list.refresh_btn.pressed.connect(self._refresh_role_list)
        #app list widget
        self._widget_app_list.app_list_widget.setIconSize(QSize(50, 50))
        self._widget_app_list.app_list_widget.itemDoubleClicked.connect(self._start_app)
        self._widget_app_list.back_btn.pressed.connect(self._uninit_app_list)
        self._widget_app_list.app_list_widget.itemClicked.connect(self._select_app_list)  # rocon master item click event
        self._widget_app_list.stop_app_btn.pressed.connect(self._stop_app)
        self._widget_app_list.refresh_btn.pressed.connect(self._refresh_app_list)
        self._widget_app_list.stop_app_btn.setDisabled(True)

        #init
        self._init()

    def _init(self):
        self._read_cache()
        self._init_role_list()
        # Ugly Hack : our window manager is not graying out the button when an app closes itself down and the appropriate
        # callback (_set_stop_app_button) is fired. It does otherwise though so it looks like the window manager
        # is getting confused when the original program doesn't have the focus.
        #
        # Taking control of it ourselves works...
        self._widget_app_list.stop_app_btn.setStyleSheet(QString.fromUtf8("QPushButton:disabled { color: gray }"))
        self._widget_role_list.show()
        self.initialised = True

################################################################################################################
##role list widget
################################################################################################################

    def _init_role_list(self):

        if not self.remocon_info._connect(self.rocon_master_name, self.rocon_master_uri, self.host_name):
            return False
        self._refresh_role_list()
        return True

    def _uninit_role_list(self):
        print "[RemoconSub]_uninit_role_list"
        self.remocon_info._shutdown()
        self.cur_selected_role = 0

    def _select_role_list(self, Item):
        print '_select_role_list: ' + Item.text()
        self.cur_selected_role = str(Item.text())

        self.remocon_info._select_role(self.cur_selected_role)

        self._widget_app_list.show()
        self._widget_app_list.move(self._widget_role_list.pos())
        self._widget_role_list.hide()
        self._init_app_list()
        pass

    def _back_role_list(self):
        self._uninit_role_list()
        execute_path = self.scripts_path + 'rocon_remocon'  # command
        execute_path += " " + "'" + self.host_name + "'"  # arg1
        os.execv(self.scripts_path + 'rocon_remocon', ['', self.host_name])
        print "Spawning: %s" % (execute_path)

    def _refresh_role_list(self):
        self.role_list = {}
        self._widget_role_list.role_list_widget.clear()

        #get role list
        self.role_list = self.remocon_info._get_role_list()

        #set list widget item
        for k in self.role_list.values():
            self._widget_role_list.role_list_widget.insertItem(0, k['name'])
            #setting the list font
            font = self._widget_role_list.role_list_widget.item(0).font()
            font.setPointSize(13)
            self._widget_role_list.role_list_widget.item(0).setFont(font)

        ##get rocon master info
        rocon_master_info = self.remocon_info._get_rocon_master_info()

        if 'name' in rocon_master_info.keys():
            self.rocon_master_list[self.rocon_master_index]['name'] = rocon_master_info['name']
        if 'description' in rocon_master_info.keys():
            self.rocon_master_list[self.rocon_master_index]['description'] = rocon_master_info['description']
        if 'icon' in rocon_master_info.keys():
            self.rocon_master_list[self.rocon_master_index]['icon'] = rocon_master_info['icon']

        self.rocon_master_list[self.rocon_master_index]['flag'] = '1'
        self._write_cache()

################################################################################################################
##app list widget
################################################################################################################

    def _init_app_list(self):
        self._refresh_app_list()

    def _uninit_app_list(self):
        self._widget_role_list.show()
        self._widget_role_list.move(self._widget_app_list.pos())
        self._widget_app_list.hide()

    def _refresh_app_list(self):
        self.app_list = {}
        self.app_list = self.remocon_info._get_app_list()
        self._widget_app_list.app_list_widget.clear()

        index = 0
        for k in self.app_list.values():
            k['index'] = index
            index = index + 1

            self._widget_app_list.app_list_widget.insertItem(0, k['display_name'])
            #setting the list font
            font = self._widget_app_list.app_list_widget.item(0).font()
            font.setPointSize(13)
            self._widget_app_list.app_list_widget.item(0).setFont(font)
            #setting the icon

            app_icon = k['icon']
            if len(app_icon) and app_icon == "Unknown.png":
                icon = QIcon(self.icon_path + app_icon)
                self._widget_app_list.app_list_widget.item(0).setIcon(icon)
            elif len(app_icon):
                icon = QIcon(os.path.join(utils.get_icon_cache_home(), app_icon))
                self._widget_app_list.app_list_widget.item(0).setIcon(icon)
            else:
                print self.rocon_master_name + ': No icon'
            pass

    def _select_app_list(self, Item):
        list_widget = Item.listWidget()
        cur_index = list_widget.count() - list_widget.currentRow() - 1
        for k in self.app_list.values():
            if(k['index'] == cur_index):
                self.cur_selected_app = k
                break
        self._widget_app_list.app_info.clear()
        info_text = "<html>"
        info_text += "<p>-------------------------------------------</p>"
        info_text += "<p><b>name: </b>" + self.cur_selected_app['name'] + "</p>"
        info_text += "<p><b>  ---------------------</b>" + "</p>"
        info_text += "<p><b>compatibility: </b>" + self.cur_selected_app['compatibility'] + "</p>"
        info_text += "<p><b>display name: </b>" + self.cur_selected_app['display_name'] + "</p>"
        info_text += "<p><b>description: </b>" + self.cur_selected_app['description'] + "</p>"
        info_text += "<p><b>namespace: </b>" + self.cur_selected_app['namespace'] + "</p>"
        info_text += "<p><b>max: </b>" + str(self.cur_selected_app['max']) + "</p>"
        info_text += "<p><b>  ---------------------</b>" + "</p>"
        info_text += "<p><b>remappings: </b>" + str(self.cur_selected_app['remappings']) + "</p>"
        info_text += "<p><b>parameters: </b>" + str(self.cur_selected_app['parameters']) + "</p>"
        info_text += "</html>"

        self._widget_app_list.app_info.appendHtml(info_text)
        self._set_stop_app_button()

    def _set_stop_app_button(self):
        '''
          This can be used by the underlying listeners to check, and if needed,
          toggle the state of the stop app button whenever a running app
          terminates itself.
        '''
        if not self.app_list:
            return
        try:
            if self.cur_selected_app["launch_list"]:
                console.logdebug("Remocon : enabling stop app button")
                self._widget_app_list.stop_app_btn.setDisabled(False)
            else:
                console.logdebug("Remocon : disabling stop app button")
                self._widget_app_list.stop_app_btn.setEnabled(False)
        except KeyError:
            pass  # do nothing

    def _stop_app(self):
        print "Stop app: " + str(self.cur_selected_app['name'])
        if self.remocon_info._stop_app(self.cur_selected_app['hash']):
            self._set_stop_app_button()
            #self._widget_app_list.stop_app_btn.setDisabled(True)

    def _start_app(self):
        print "Start app: " + str(self.cur_selected_app['name'])
        if self.remocon_info._start_app(self.cur_selected_app['hash']):
            self._widget_app_list.stop_app_btn.setDisabled(False)

    def _write_cache(self):
        try:
            cache_rocon_master_info_list = open(self.rocon_master_list_cache_path, 'w')
        except:
            print "No directory or file: %s" % (self.rocon_master_list_cache_path)
            return

        for k in self.rocon_master_list.values():
            rocon_master_index = k['index']
            rocon_master_name = k['name']
            rocon_master_uri = k['master_uri']
            rocon_master_host_name = k['host_name']
            rocon_master_icon = k['icon']
            rocon_master_description = k['description']
            rocon_master_flag = k['flag']

            rocon_master_elem = '['
            rocon_master_elem += 'index=' + str(rocon_master_index) + ','
            rocon_master_elem += 'name=' + str(rocon_master_name) + ','
            rocon_master_elem += 'master_uri=' + str(rocon_master_uri) + ','
            rocon_master_elem += 'host_name=' + str(rocon_master_host_name) + ','
            rocon_master_elem += 'description=' + str(rocon_master_description) + ','
            rocon_master_elem += 'icon=' + rocon_master_icon + ','
            rocon_master_elem += 'flag=' + rocon_master_flag
            rocon_master_elem += ']\n'

            cache_rocon_master_info_list.write(rocon_master_elem)

        cache_rocon_master_info_list.close()

    def _read_cache(self):
        #read cache and display the rocon_master list
        try:
            cache_rocon_master_info_list = open(self.rocon_master_list_cache_path, 'r')
        except:
            print "No directory or file: %s" % (self.rocon_master_list_cache_path)
            return
        lines = cache_rocon_master_info_list.readlines()

        for line in lines:
            if line.count("[index="):
                rocon_master_index = line[string.find(line, "[index=") + len("[index="):string.find(line, ",name=")]
                rocon_master_name = line[string.find(line, "name=") + len("name="):string.find(line, ",master_uri=")]
                rocon_master_uri = line[string.find(line, ",master_uri=") + len(",master_uri="):string.find(line, ",host_name")]
                rocon_master_host_name = line[string.find(line, ",host_name=") + len(",host_name="):string.find(line, ",description=")]
                rocon_master_description = line[string.find(line, ",description=") + len(",description="):string.find(line, ",icon=")]
                rocon_master_icon = line[string.find(line, ",icon=") + len(",icon="):string.find(line, ",flag=")]
                rocon_master_flag = line[string.find(line, ",flag=") + len(",flag="):string.find(line, "]")]

                self.rocon_master_list[rocon_master_index] = {}
                self.rocon_master_list[rocon_master_index]['index'] = rocon_master_index
                self.rocon_master_list[rocon_master_index]['name'] = rocon_master_name
                self.rocon_master_list[rocon_master_index]['master_uri'] = rocon_master_uri
                self.rocon_master_list[rocon_master_index]['host_name'] = rocon_master_host_name
                self.rocon_master_list[rocon_master_index]['icon'] = rocon_master_icon
                self.rocon_master_list[rocon_master_index]['description'] = rocon_master_description
                self.rocon_master_list[rocon_master_index]['flag'] = rocon_master_flag
        cache_rocon_master_info_list.close()

#################################################################
##Remocon Main
#################################################################


class RemoconMain(QMainWindow):
    def __init__(self, parent, title, application):
        self._context = parent

        super(RemoconMain, self).__init__()
        self.initialised = False
        self.setObjectName('Remocon')

        self.host_name = "localhost"
        self.master_uri = "http://%s:11311" % (self.host_name)

        self.env_host_name = os.getenv("ROS_HOSTNAME")
        self.env_master_uri = os.getenv("ROS_MASTER_URI")
        if self.env_host_name == None:
            self.env_host_name = 'localhost'
        if self.env_master_uri == None:
            self.env_master_uri = "http://%s:11311" % (self.env_host_name)

        self.application = application
        self._widget_main = QWidget()

        self.rocon_master_list = {}
        self.cur_selected_rocon_master = None
        self.is_init = False

        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../ui/remocon.ui")
        uic.loadUi(path, self._widget_main)

        utils.setup_home_dirs()
        self.rocon_master_list_cache_path = os.path.join(utils.get_settings_cache_home(), "rocon_master.cache")

        self.icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../resources/images/")
        self.scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../scripts/")

        #main widget
        self._widget_main.list_widget.setIconSize(QSize(50, 50))
        self._widget_main.list_widget.itemDoubleClicked.connect(self._connect_rocon_master)  # list item double click event
        self._widget_main.list_widget.itemClicked.connect(self._select_rocon_master)  # list item double click event

        self._widget_main.add_concert_btn.pressed.connect(self._set_add_rocon_master)  # add button event
        self._widget_main.delete_btn.pressed.connect(self._delete_rocon_master)  # delete button event
        self._widget_main.delete_all_btn.pressed.connect(self._delete_all_rocon_masters)  # delete all button event
        self._widget_main.refresh_btn.pressed.connect(self._refresh_rocon_master_list)  # refresh all button event

        #init
        self._init()
        self._widget_main.show()
        self._widget_main.activateWindow()  # give it the focus
        self._widget_main.raise_()          # make sure it is on top

    def __del__(self):
        print '[RemoconMain]: Destroy'

    def _init(self):

        self._connect_dlg_isValid = False
        self.cur_selected_rocon_master = None
        self._refresh_rocon_master_list()
        self.is_init = True
        pass

    def _check_up(self):
        for k in self.rocon_master_list.values():
            print("Concert: %s" % k)
            rocon_master_uri = k['master_uri']
            host_name = k['host_name']
            print "[_check_up]:MASTER_URI[%s], HOST_NAME[%s]" % (rocon_master_uri, host_name)

            output = subprocess.Popen([self.scripts_path + "rocon_remocon_check_up", rocon_master_uri, host_name], stdout=subprocess.PIPE)
            time_out_cnt = 0
            while True:
                print "checking: " + rocon_master_uri
                result = output.poll()
                if time_out_cnt > 30:
                    print "timeout: " + rocon_master_uri
                    try:
                        output.terminate()
                    except:
                        print "Error: output.terminate()"

                    k['name'] = "Unknown"
                    k['description'] = "Unknown."
                    k['icon'] = "Unknown.png"
                    k['flag'] = '0'
                    break

                elif result == 0:
                    args = output.communicate()[0]
                    k['name'] = args.split('\n')[0]
                    k['description'] = args.split('\n')[1]
                    k['icon'] = args.split('\n')[2]

                    if k['name'] == "Unknown":
                        k['flag'] = '0'
                    else:
                        k['flag'] = '1'
                    break

                time.sleep(0.1)
                time_out_cnt += 1

    def _read_cache(self):
        #read cache and display the rocon master list
        try:
            cache_rocon_master_info_list = open(self.rocon_master_list_cache_path, 'r')
        except:
            console.logdebug("Remocon : no cached settings found, moving on.")
            return
        lines = cache_rocon_master_info_list.readlines()
        for line in lines:
            if line.count("[index="):
                rocon_master_index = line[string.find(line, "[index=") + len("[index="):string.find(line, ",name=")]
                rocon_master_name = line[string.find(line, "name=") + len("name="):string.find(line, ",master_uri=")]
                rocon_master_uri = line[string.find(line, ",master_uri=") + len(",master_uri="):string.find(line, ",host_name=")]
                rocon_master_host_name = line[string.find(line, ",host_name=") + len(",host_name="):string.find(line, ",description=")]
                rocon_master_description = line[string.find(line, ",description=") + len(",description="):string.find(line, ",icon=")]
                rocon_master_icon = line[string.find(line, ",icon=") + len(",icon="):string.find(line, ",flag=")]
                rocon_master_flag = line[string.find(line, ",flag=") + len(",flag="):string.find(line, "]")]

                self.rocon_master_list[rocon_master_index] = {}
                self.rocon_master_list[rocon_master_index]['index'] = rocon_master_index
                self.rocon_master_list[rocon_master_index]['name'] = rocon_master_name
                self.rocon_master_list[rocon_master_index]['master_uri'] = rocon_master_uri
                self.rocon_master_list[rocon_master_index]['host_name'] = rocon_master_host_name
                self.rocon_master_list[rocon_master_index]['icon'] = rocon_master_icon
                self.rocon_master_list[rocon_master_index]['description'] = rocon_master_description
                self.rocon_master_list[rocon_master_index]['flag'] = rocon_master_flag
        cache_rocon_master_info_list.close()

    def _delete_all_rocon_masters(self):
        for k in self.rocon_master_list.values():
            del self.rocon_master_list[k["index"]]
        self._update_rocon_master_list()

    def _delete_rocon_master(self):
        if self.cur_selected_rocon_master in self.rocon_master_list.keys():
            del self.rocon_master_list[self.cur_selected_rocon_master]
        self._update_rocon_master_list()

    def _add_rocon_master(self, params):
        rocon_master_uri = str(params['param1'].toPlainText())
        rocon_master_host_name = str(params['param2'].toPlainText())
        rocon_master_index = str(uuid.uuid4())
        self.rocon_master_list[rocon_master_index] = {}
        self.rocon_master_list[rocon_master_index]['index'] = rocon_master_index
        self.rocon_master_list[rocon_master_index]['name'] = "Unknown"
        self.rocon_master_list[rocon_master_index]['master_uri'] = rocon_master_uri
        self.rocon_master_list[rocon_master_index]['host_name'] = rocon_master_host_name
        self.rocon_master_list[rocon_master_index]['icon'] = "Unknown.png"
        self.rocon_master_list[rocon_master_index]['description'] = ""
        self.rocon_master_list[rocon_master_index]['flag'] = "0"

        self._update_rocon_master_list()
        self._refresh_rocon_master_list()

    def _set_add_rocon_master(self):
        print '_add_rocon_master'
        if self._connect_dlg_isValid:
            print "Dialog is live!!"
            self._connect_dlg.done(0)

        #dialog
        self._connect_dlg = QDialog(self._widget_main)
        self._connect_dlg.setWindowTitle("Add Concert")
        self._connect_dlg.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        self._connect_dlg.setMinimumSize(350, 0)
        # dlg_rect = self._connect_dlg.geometry()

        #dialog layout
        ver_layout = QVBoxLayout(self._connect_dlg)
        ver_layout.setContentsMargins(9, 9, 9, 9)

        #param layout
        text_grid_sub_widget = QWidget()
        text_grid_layout = QGridLayout(text_grid_sub_widget)
        text_grid_layout.setColumnStretch(1, 0)
        text_grid_layout.setRowStretch(2, 0)

        #param 1
        title_widget1 = QLabel("MASTER_URI: ")
        context_widget1 = QTextEdit()
        context_widget1.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        context_widget1.setMinimumSize(0, 30)
        context_widget1.append(self.master_uri)

        #param 2
        title_widget2 = QLabel("HOST_NAME: ")
        context_widget2 = QTextEdit()
        context_widget2.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Ignored)
        context_widget2.setMinimumSize(0, 30)
        context_widget2.append(self.host_name)

        #add param
        text_grid_layout.addWidget(title_widget1)
        text_grid_layout.addWidget(context_widget1)
        text_grid_layout.addWidget(title_widget2)
        text_grid_layout.addWidget(context_widget2)

        #add param layout
        ver_layout.addWidget(text_grid_sub_widget)

        #button layout
        button_hor_sub_widget = QWidget()
        button_hor_layout = QHBoxLayout(button_hor_sub_widget)

        params = {}
        params['param1'] = context_widget1
        params['param2'] = context_widget2

        #check box
        use_env_var_check = QCheckBox("Use environment variables")
        use_env_var_check.setCheckState(Qt.Unchecked)

        def set_use_env_var(data, text_widget1, text_widget2):
            if data == Qt.Unchecked:
                text_widget1.setText(self.master_uri)
                text_widget2.setText(self.host_name)
            elif data == Qt.Checked:
                self.master_uri = str(text_widget1.toPlainText())
                self.host_name = str(text_widget2.toPlainText())
                text_widget1.setText(self.env_master_uri)
                text_widget2.setText(self.env_host_name)

        def check_event(data):
            set_use_env_var(data, context_widget1, context_widget2)

        use_env_var_check.stateChanged.connect(check_event)
        ver_layout.addWidget(use_env_var_check)

        #button
        btn_call = QPushButton("Add")
        btn_cancel = QPushButton("Cancel")

        btn_call.clicked.connect(lambda: self._connect_dlg.done(0))
        btn_call.clicked.connect(lambda: self._add_rocon_master(params))

        btn_cancel.clicked.connect(lambda: self._connect_dlg.done(0))

        #add button
        button_hor_layout.addWidget(btn_call)
        button_hor_layout.addWidget(btn_cancel)

        #add button layout
        ver_layout.addWidget(button_hor_sub_widget)
        self._connect_dlg.setVisible(True)
        self._connect_dlg.finished.connect(self._destroy_connect_dlg)
        self._connect_dlg_isValid = True

    def _refresh_rocon_master_list(self):
        print '_refresh_rocon_master_list'
        if self.is_init:
            self._update_rocon_master_list()
        self._read_cache()
        self._widget_main.list_info_widget.clear()
        self._check_up()
        self._update_rocon_master_list()

    def _update_rocon_master_list(self):

        print '_update_rocon_master_list'
        self._widget_main.list_widget.clear()
        try:
            cache_rocon_master_info_list = open(self.rocon_master_list_cache_path, 'w')
        except:
            print "No directory or file: %s" % (self.rocon_master_list_cache_path)
            return
        for k in self.rocon_master_list.values():
            self._add_rocon_master_list_item(k)
            rocon_master_index = k['index']
            rocon_master_name = k['name']
            rocon_master_uri = k['master_uri']
            rocon_master_host_name = k['host_name']
            rocon_master_icon = k['icon']
            rocon_master_description = k['description']
            rocon_master_flag = k['flag']

            rocon_master_elem = '['
            rocon_master_elem += 'index=' + str(rocon_master_index) + ','
            rocon_master_elem += 'name=' + str(rocon_master_name) + ','
            rocon_master_elem += 'master_uri=' + str(rocon_master_uri) + ','
            rocon_master_elem += 'host_name=' + str(rocon_master_host_name) + ','
            rocon_master_elem += 'description=' + str(rocon_master_description) + ','
            rocon_master_elem += 'icon=' + rocon_master_icon + ','
            rocon_master_elem += 'flag=' + rocon_master_flag
            rocon_master_elem += ']\n'

            cache_rocon_master_info_list.write(rocon_master_elem)
        cache_rocon_master_info_list.close()

    def _add_rocon_master_list_item(self, rocon_master):
        print('_add_rocon_master_list_item [%s]' % rocon_master['name'])
        rocon_master_index = rocon_master['index']
        rocon_master_name = rocon_master['name']
        rocon_master_uri = rocon_master['master_uri']
        rocon_master_host_name = rocon_master['host_name']
        rocon_master_icon = rocon_master['icon']
        rocon_master_description = rocon_master['description']
        rocon_master['cur_row'] = str(self._widget_main.list_widget.count())

        display_name = str(rocon_master_name) + "\n" + "[" + str(rocon_master_uri) + "]"
        self._widget_main.list_widget.insertItem(self._widget_main.list_widget.count(), display_name)

        #setting the list font

        font = self._widget_main.list_widget.item(self._widget_main.list_widget.count() - 1).font()
        font.setPointSize(13)
        self._widget_main.list_widget.item(self._widget_main.list_widget.count() - 1).setFont(font)

        #setToolTip
        rocon_master_info = ""
        rocon_master_info += "rocon_master_index: " + str(rocon_master_index) + "\n"
        rocon_master_info += "rocon_master_name: " + str(rocon_master_name) + "\n"
        rocon_master_info += "master_uri:  " + str(rocon_master_uri) + "\n"
        rocon_master_info += "host_name:  " + str(rocon_master_host_name) + "\n"
        rocon_master_info += "description:  " + str(rocon_master_description)
        self._widget_main.list_widget.item(self._widget_main.list_widget.count() - 1).setToolTip(rocon_master_info)

        #set icon
        if len(rocon_master_icon) and rocon_master_icon == "Unknown.png":
            icon = QIcon(self.icon_path + rocon_master_icon)
            self._widget_main.list_widget.item(self._widget_main.list_widget.count() - 1).setIcon(icon)
        elif len(rocon_master_icon):
            icon = QIcon(os.path.join(utils.get_icon_cache_home(), rocon_master_icon))
            self._widget_main.list_widget.item(self._widget_main.list_widget.count() - 1).setIcon(icon)
        else:
            print rocon_master_name + ': No icon'
        pass

    def _select_rocon_master(self, Item):
        list_widget = Item.listWidget()
        for k in self.rocon_master_list.values():
            if k["cur_row"] == str(list_widget.currentRow()):
                self.cur_selected_rocon_master = k['index']
                break
        self._widget_main.list_info_widget.clear()
        info_text = "<html>"
        info_text += "<p>-------------------------------------------</p>"
        info_text += "<p><b>name: </b>" + str(self.rocon_master_list[self.cur_selected_rocon_master]['name']) + "</p>"
        info_text += "<p><b>master_uri: </b>" + str(self.rocon_master_list[self.cur_selected_rocon_master]['master_uri']) + "</p>"
        info_text += "<p><b>host_name: </b>" + str(self.rocon_master_list[self.cur_selected_rocon_master]['host_name']) + "</p>"
        info_text += "<p><b>description: </b>" + str(self.rocon_master_list[self.cur_selected_rocon_master]['description']) + "</p>"
        info_text += "<p>-------------------------------------------</p>"
        info_text += "</html>"
        self._widget_main.list_info_widget.appendHtml(info_text)

    def _destroy_connect_dlg(self):
        print "[Dialog] Destroy!!!"
        self._connect_dlg_isValid = False

    def _connect_rocon_master(self):
        rocon_master_name = str(self.rocon_master_list[self.cur_selected_rocon_master]['name'])
        rocon_master_uri = str(self.rocon_master_list[self.cur_selected_rocon_master]['master_uri'])
        rocon_master_host_name = str(self.rocon_master_list[self.cur_selected_rocon_master]['host_name'])

        rocon_master_index = str(self.cur_selected_rocon_master)

        if self.rocon_master_list[rocon_master_index]['flag'] == '0':
            # DJS: unused reply box?
            # reply = QMessageBox.warning(self, 'ERROR', "YOU SELECT NO CONCERT", QMessageBox.Ok|QMessageBox.Ok)
            return

        execute_path = self.scripts_path + 'rocon_remocon_sub'  # command
        execute_path += " " + "'" + rocon_master_index + "'"  # arg1
        execute_path += " " + "'" + rocon_master_name + "'"  # arg2
        execute_path += " " + "'" + rocon_master_uri + "'"  # arg3
        execute_path += " " + "'" + rocon_master_host_name + "'"  # arg4

        self._widget_main.hide()
        os.execv(self.scripts_path + 'rocon_remocon_sub', ["", rocon_master_index, rocon_master_name, rocon_master_uri, rocon_master_host_name])
        print "Spawning: %s" % (execute_path)
