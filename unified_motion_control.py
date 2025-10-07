import sys
import time
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGroupBox, QPushButton, QLabel, 
                             QLineEdit, QComboBox, QSlider, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QStatusBar, QGridLayout, QTabWidget,
                             QTableWidget, QTableWidgetItem, QFileDialog, QCheckBox,
                             QProgressBar, QTextEdit)
from PyQt5.QtCore import QTimer, Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor
import serial.tools.list_ports

# Import your controller classes
from stepper_controller import PicoStepperController
from lts_controller import ThorlabsLTSController

# Mock controllers for demonstration
class PicoStepperController:
    def __init__(self, port=None, baudrate=115200, timeout=1.0):
        self.port = port or "COM3"
        self._current_rps = 0.0
        self._target_rps = 0.0
        self._position = 0
    def enable_motor(self): return True
    def disable_motor(self): return True
    def set_speed_rps(self, rps): self._target_rps = rps; return True
    def stop(self): self._target_rps = 0; return True
    def set_ramp_rate(self, rate): return True
    def get_status(self):
        if self._current_rps < self._target_rps: self._current_rps += 0.1
        elif self._current_rps > self._target_rps: self._current_rps -= 0.1
        self._position += int(self._current_rps * 200 / 10)
        return (self._current_rps, self._target_rps, self._position)
    def close(self): pass

class ThorlabsLTSController:
    def __init__(self, port=None):
        self.port = port or "COM4"
        self._position = 0.0
        self._target = 0.0
    def home(self): self._position = 0.0; return True
    def move_absolute(self, pos): self._target = pos; return True
    def move_relative(self, dist): self._target = self._position + dist; return True
    def get_position(self): 
        if abs(self._position - self._target) > 0.1:
            self._position += 0.1 if self._target > self._position else -0.1
        return self._position
    def stop(self): self._target = self._position; return True
    def is_moving(self): return abs(self._position - self._target) > 0.1
    def close(self): pass


class PathExecutionThread(QThread):
    """Thread for executing motion paths"""
    progress_update = pyqtSignal(int, str)
    path_complete = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, path_data, controllers, axes_config):
        super().__init__()
        self.path_data = path_data
        self.controllers = controllers
        self.axes_config = axes_config
        self.running = True
        
    def run(self):
        try:
            total_steps = len(self.path_data)
            for i, step in enumerate(self.path_data):
                if not self.running:
                    break
                
                # Execute motion for each axis
                for axis_name, value in step.items():
                    if axis_name in self.axes_config:
                        controller = self.controllers[self.axes_config[axis_name]['controller']]
                        axis_type = self.axes_config[axis_name]['type']
                        
                        if axis_type == 'linear':
                            controller.move_absolute(float(value))
                        elif axis_type == 'rotary':
                            controller.set_speed_rps(float(value))
                
                # Wait for motion to complete
                self.progress_update.emit(int((i + 1) / total_steps * 100), 
                                         f"Step {i+1}/{total_steps}")
                time.sleep(0.1)  # Adjust based on your motion timing
                
            self.path_complete.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def stop(self):
        self.running = False


class UnifiedMotionControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.stepper_controller = None
        self.lts_controllers = {}  # Support multiple LTS stages
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.path_thread = None
        
        # Axis configuration
        self.axes_config = {
            'X': {'controller': 'lts_x', 'type': 'linear', 'enabled': False},
            'Y': {'controller': 'lts_y', 'type': 'linear', 'enabled': False},
            'Z': {'controller': 'lts_z', 'type': 'linear', 'enabled': False},
            'Rotation': {'controller': 'stepper', 'type': 'rotary', 'enabled': False}
        }
        
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle('Unified Motion Control System')
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_connection_tab(), "Connection")
        self.tabs.addTab(self.create_manual_control_tab(), "Manual Control")
        self.tabs.addTab(self.create_path_control_tab(), "Path Execution")
        self.tabs.addTab(self.create_status_tab(), "Status Monitoring")
        
        main_layout.addWidget(self.tabs)
        
        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('System Disconnected')
        
        self.apply_style()
        
    def create_connection_tab(self):
        """Tab for device connections"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Stepper Motor Connection
        stepper_group = QGroupBox("Stepper Motor (Rotation Axis)")
        stepper_layout = QHBoxLayout()
        
        stepper_layout.addWidget(QLabel("Port:"))
        self.stepper_port_combo = QComboBox()
        stepper_layout.addWidget(self.stepper_port_combo)
        
        self.stepper_connect_btn = QPushButton("Connect")
        self.stepper_connect_btn.clicked.connect(lambda: self.toggle_connection('stepper'))
        stepper_layout.addWidget(self.stepper_connect_btn)
        
        self.stepper_enable_btn = QPushButton("Enable")
        self.stepper_enable_btn.clicked.connect(lambda: self.toggle_motor('stepper'))
        self.stepper_enable_btn.setEnabled(False)
        stepper_layout.addWidget(self.stepper_enable_btn)
        
        stepper_layout.addStretch()
        stepper_group.setLayout(stepper_layout)
        layout.addWidget(stepper_group)
        
        # Linear Stage Connections (X, Y, Z)
        for axis in ['X', 'Y', 'Z']:
            axis_group = QGroupBox(f"{axis}-Axis Linear Stage (Thorlabs LTS)")
            axis_layout = QHBoxLayout()
            
            axis_layout.addWidget(QLabel("Port:"))
            port_combo = QComboBox()
            setattr(self, f'lts_{axis.lower()}_port_combo', port_combo)
            axis_layout.addWidget(port_combo)
            
            connect_btn = QPushButton("Connect")
            connect_btn.clicked.connect(lambda checked, a=axis: self.toggle_connection(f'lts_{a.lower()}'))
            setattr(self, f'lts_{axis.lower()}_connect_btn', connect_btn)
            axis_layout.addWidget(connect_btn)
            
            home_btn = QPushButton("Home")
            home_btn.clicked.connect(lambda checked, a=axis: self.home_axis(a))
            home_btn.setEnabled(False)
            setattr(self, f'lts_{axis.lower()}_home_btn', home_btn)
            axis_layout.addWidget(home_btn)
            
            enable_check = QCheckBox("Enable for Path")
            enable_check.stateChanged.connect(lambda state, a=axis: self.toggle_axis_enable(a, state))
            setattr(self, f'axis_{axis.lower()}_enable', enable_check)
            axis_layout.addWidget(enable_check)
            
            axis_layout.addStretch()
            axis_group.setLayout(axis_layout)
            layout.addWidget(axis_group)
        
        # Refresh ports button
        refresh_btn = QPushButton("Refresh All Ports")
        refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(refresh_btn)
        
        # Initialize ports after all combo boxes are created
        self.refresh_ports()
        
        layout.addStretch()
        return widget
    
    def create_manual_control_tab(self):
        """Tab for manual axis control"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Linear Axes Control
        linear_group = QGroupBox("Linear Axes Control")
        linear_layout = QGridLayout()
        
        for i, axis in enumerate(['X', 'Y', 'Z']):
            # Axis label
            linear_layout.addWidget(QLabel(f"{axis}-Axis:"), i, 0)
            
            # Current position
            pos_label = QLabel("0.00 mm")
            pos_label.setStyleSheet("font-weight: bold;")
            setattr(self, f'{axis.lower()}_pos_label', pos_label)
            linear_layout.addWidget(pos_label, i, 1)
            
            # Target position
            linear_layout.addWidget(QLabel("Target:"), i, 2)
            target_input = QDoubleSpinBox()
            target_input.setRange(-150, 150)
            target_input.setSingleStep(0.1)
            target_input.setDecimals(3)
            target_input.setSuffix(" mm")
            setattr(self, f'{axis.lower()}_target_input', target_input)
            linear_layout.addWidget(target_input, i, 3)
            
            # Move buttons
            move_abs_btn = QPushButton("Move Absolute")
            move_abs_btn.clicked.connect(lambda checked, a=axis: self.move_absolute(a))
            move_abs_btn.setEnabled(False)
            setattr(self, f'{axis.lower()}_move_abs_btn', move_abs_btn)
            linear_layout.addWidget(move_abs_btn, i, 4)
            
            move_rel_btn = QPushButton("Move Relative")
            move_rel_btn.clicked.connect(lambda checked, a=axis: self.move_relative(a))
            move_rel_btn.setEnabled(False)
            setattr(self, f'{axis.lower()}_move_rel_btn', move_rel_btn)
            linear_layout.addWidget(move_rel_btn, i, 5)
            
            # Quick jog buttons
            jog_layout = QHBoxLayout()
            for dist in [-10, -1, -0.1, 0.1, 1, 10]:
                jog_btn = QPushButton(f"{dist:+.1f}")
                jog_btn.setMaximumWidth(60)
                jog_btn.clicked.connect(lambda checked, a=axis, d=dist: self.jog_axis(a, d))
                jog_btn.setEnabled(False)
                jog_layout.addWidget(jog_btn)
                if not hasattr(self, f'{axis.lower()}_jog_buttons'):
                    setattr(self, f'{axis.lower()}_jog_buttons', [])
                getattr(self, f'{axis.lower()}_jog_buttons').append(jog_btn)
            linear_layout.addLayout(jog_layout, i, 6)
        
        linear_group.setLayout(linear_layout)
        layout.addWidget(linear_group)
        
        # Rotary Axis Control
        rotary_group = QGroupBox("Rotation Control (Stepper Motor)")
        rotary_layout = QGridLayout()
        
        rotary_layout.addWidget(QLabel("Current Speed:"), 0, 0)
        self.rotation_speed_label = QLabel("0.00 RPS")
        self.rotation_speed_label.setStyleSheet("font-weight: bold;")
        rotary_layout.addWidget(self.rotation_speed_label, 0, 1)
        
        rotary_layout.addWidget(QLabel("Target Speed:"), 1, 0)
        self.rotation_target_input = QDoubleSpinBox()
        self.rotation_target_input.setRange(-50, 50)
        self.rotation_target_input.setSingleStep(0.1)
        self.rotation_target_input.setDecimals(2)
        self.rotation_target_input.setSuffix(" RPS")
        rotary_layout.addWidget(self.rotation_target_input, 1, 1)
        
        self.rotation_set_btn = QPushButton("Set Speed")
        self.rotation_set_btn.clicked.connect(self.set_rotation_speed)
        self.rotation_set_btn.setEnabled(False)
        rotary_layout.addWidget(self.rotation_set_btn, 1, 2)
        
        # Quick rotation speeds
        rotary_layout.addWidget(QLabel("Quick Speeds:"), 2, 0)
        quick_layout = QHBoxLayout()
        for speed in [0, 1, 2, 5, 10, -1, -2, -5]:
            btn = QPushButton(f"{speed:+.0f}" if speed != 0 else "Stop")
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda checked, s=speed: self.quick_rotation(s))
            btn.setEnabled(False)
            if not hasattr(self, 'rotation_quick_buttons'):
                self.rotation_quick_buttons = []
            self.rotation_quick_buttons.append(btn)
            quick_layout.addWidget(btn)
        rotary_layout.addLayout(quick_layout, 2, 1, 1, 2)
        
        rotary_group.setLayout(rotary_layout)
        layout.addWidget(rotary_group)
        
        # Emergency Stop
        self.estop_btn = QPushButton("EMERGENCY STOP ALL")
        self.estop_btn.clicked.connect(self.emergency_stop_all)
        self.estop_btn.setStyleSheet("""
            background-color: #f44336; 
            color: white; 
            font-weight: bold; 
            font-size: 16px;
            min-height: 50px;
        """)
        self.estop_btn.setEnabled(False)
        layout.addWidget(self.estop_btn)
        
        layout.addStretch()
        return widget
    
    def create_path_control_tab(self):
        """Tab for CSV path execution"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # File loading
        file_group = QGroupBox("Path File")
        file_layout = QHBoxLayout()
        
        self.path_file_input = QLineEdit()
        self.path_file_input.setPlaceholderText("No file loaded")
        self.path_file_input.setReadOnly(True)
        file_layout.addWidget(self.path_file_input)
        
        browse_btn = QPushButton("Browse CSV")
        browse_btn.clicked.connect(self.load_path_file)
        file_layout.addWidget(browse_btn)
        
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        
        # Path preview
        preview_group = QGroupBox("Path Preview")
        preview_layout = QVBoxLayout()
        
        self.path_table = QTableWidget()
        self.path_table.setMaximumHeight(200)
        preview_layout.addWidget(self.path_table)
        
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        
        # Execution controls
        exec_group = QGroupBox("Execution Control")
        exec_layout = QGridLayout()
        
        exec_layout.addWidget(QLabel("Repeat Count:"), 0, 0)
        self.repeat_count = QSpinBox()
        self.repeat_count.setRange(1, 1000)
        self.repeat_count.setValue(1)
        exec_layout.addWidget(self.repeat_count, 0, 1)
        
        exec_layout.addWidget(QLabel("Step Delay (ms):"), 0, 2)
        self.step_delay = QSpinBox()
        self.step_delay.setRange(0, 10000)
        self.step_delay.setValue(100)
        exec_layout.addWidget(self.step_delay, 0, 3)
        
        self.execute_btn = QPushButton("Execute Path")
        self.execute_btn.clicked.connect(self.execute_path)
        self.execute_btn.setEnabled(False)
        self.execute_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; min-height: 40px;")
        exec_layout.addWidget(self.execute_btn, 1, 0, 1, 2)
        
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.clicked.connect(self.pause_path)
        self.pause_btn.setEnabled(False)
        exec_layout.addWidget(self.pause_btn, 1, 2)
        
        self.stop_path_btn = QPushButton("Stop Path")
        self.stop_path_btn.clicked.connect(self.stop_path)
        self.stop_path_btn.setEnabled(False)
        self.stop_path_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        exec_layout.addWidget(self.stop_path_btn, 1, 3)
        
        exec_group.setLayout(exec_layout)
        layout.addWidget(exec_group)
        
        # Progress
        progress_group = QGroupBox("Execution Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("No path running")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        layout.addStretch()
        return widget
    
    def create_status_tab(self):
        """Tab for system status and logs"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # System status
        status_group = QGroupBox("System Status")
        status_layout = QGridLayout()
        
        status_layout.addWidget(QLabel("Stepper Motor:"), 0, 0)
        self.stepper_status_label = QLabel("Disconnected")
        status_layout.addWidget(self.stepper_status_label, 0, 1)
        
        for i, axis in enumerate(['X', 'Y', 'Z'], 1):
            status_layout.addWidget(QLabel(f"{axis}-Axis Stage:"), i, 0)
            label = QLabel("Disconnected")
            setattr(self, f'lts_{axis.lower()}_status_label', label)
            status_layout.addWidget(label, i, 1)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Event log
        log_group = QGroupBox("Event Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(300)
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
    
    def refresh_ports(self):
        """Refresh available serial ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        
        self.stepper_port_combo.clear()
        self.stepper_port_combo.addItems(ports if ports else ["No ports found"])
        
        for axis in ['x', 'y', 'z']:
            combo = getattr(self, f'lts_{axis}_port_combo')
            combo.clear()
            combo.addItems(ports if ports else ["No ports found"])
    
    def toggle_connection(self, device):
        """Connect/disconnect devices"""
        if device == 'stepper':
            if self.stepper_controller is None:
                try:
                    port = self.stepper_port_combo.currentText()
                    self.stepper_controller = PicoStepperController(port=port)
                    self.stepper_connect_btn.setText("Disconnect")
                    self.stepper_enable_btn.setEnabled(True)
                    self.stepper_status_label.setText("Connected")
                    self.stepper_status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.log_event(f"Stepper motor connected on {port}")
                    self.update_timer.start(100)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to connect stepper: {e}")
            else:
                self.stepper_controller.close()
                self.stepper_controller = None
                self.stepper_connect_btn.setText("Connect")
                self.stepper_enable_btn.setEnabled(False)
                self.stepper_status_label.setText("Disconnected")
                self.stepper_status_label.setStyleSheet("color: red;")
                self.log_event("Stepper motor disconnected")
        
        elif device.startswith('lts_'):
            axis = device.split('_')[1].upper()
            controller_key = f'lts_{axis.lower()}'
            
            if controller_key not in self.lts_controllers:
                try:
                    port = getattr(self, f'lts_{axis.lower()}_port_combo').currentText()
                    self.lts_controllers[controller_key] = ThorlabsLTSController(port=port)
                    getattr(self, f'lts_{axis.lower()}_connect_btn').setText("Disconnect")
                    getattr(self, f'lts_{axis.lower()}_home_btn').setEnabled(True)
                    getattr(self, f'lts_{axis.lower()}_status_label').setText("Connected")
                    getattr(self, f'lts_{axis.lower()}_status_label').setStyleSheet("color: green; font-weight: bold;")
                    
                    # Enable manual controls
                    getattr(self, f'{axis.lower()}_move_abs_btn').setEnabled(True)
                    getattr(self, f'{axis.lower()}_move_rel_btn').setEnabled(True)
                    for btn in getattr(self, f'{axis.lower()}_jog_buttons'):
                        btn.setEnabled(True)
                    
                    self.log_event(f"{axis}-axis stage connected on {port}")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to connect {axis}-axis: {e}")
            else:
                self.lts_controllers[controller_key].close()
                del self.lts_controllers[controller_key]
                getattr(self, f'lts_{axis.lower()}_connect_btn').setText("Connect")
                getattr(self, f'lts_{axis.lower()}_home_btn').setEnabled(False)
                getattr(self, f'lts_{axis.lower()}_status_label').setText("Disconnected")
                getattr(self, f'lts_{axis.lower()}_status_label').setStyleSheet("color: red;")
                
                # Disable manual controls
                getattr(self, f'{axis.lower()}_move_abs_btn').setEnabled(False)
                getattr(self, f'{axis.lower()}_move_rel_btn').setEnabled(False)
                for btn in getattr(self, f'{axis.lower()}_jog_buttons'):
                    btn.setEnabled(False)
                
                self.log_event(f"{axis}-axis stage disconnected")
    
    def toggle_motor(self, device):
        """Enable/disable motors"""
        if device == 'stepper' and self.stepper_controller:
            if self.stepper_enable_btn.text() == "Enable":
                self.stepper_controller.enable_motor()
                self.stepper_enable_btn.setText("Disable")
                self.rotation_set_btn.setEnabled(True)
                self.estop_btn.setEnabled(True)
                for btn in self.rotation_quick_buttons:
                    btn.setEnabled(True)
                self.log_event("Stepper motor enabled")
            else:
                self.stepper_controller.disable_motor()
                self.stepper_enable_btn.setText("Enable")
                self.rotation_set_btn.setEnabled(False)
                for btn in self.rotation_quick_buttons:
                    btn.setEnabled(False)
                self.log_event("Stepper motor disabled")
    
    def toggle_axis_enable(self, axis, state):
        """Enable/disable axis for path execution"""
        self.axes_config[axis]['enabled'] = (state == Qt.Checked)
        self.log_event(f"{axis}-axis {'enabled' if state == Qt.Checked else 'disabled'} for path execution")
    
    def home_axis(self, axis):
        """Home a linear stage"""
        controller_key = f'lts_{axis.lower()}'
        if controller_key in self.lts_controllers:
            self.lts_controllers[controller_key].home()
            self.log_event(f"{axis}-axis homing initiated")
    
    def move_absolute(self, axis):
        """Move axis to absolute position"""
        controller_key = f'lts_{axis.lower()}'
        if controller_key in self.lts_controllers:
            target = getattr(self, f'{axis.lower()}_target_input').value()
            self.lts_controllers[controller_key].move_absolute(target)
            self.log_event(f"{axis}-axis moving to {target:.3f} mm (absolute)")
    
    def move_relative(self, axis):
        """Move axis by relative distance"""
        controller_key = f'lts_{axis.lower()}'
        if controller_key in self.lts_controllers:
            distance = getattr(self, f'{axis.lower()}_target_input').value()
            self.lts_controllers[controller_key].move_relative(distance)
            self.log_event(f"{axis}-axis moving {distance:+.3f} mm (relative)")
    
    def jog_axis(self, axis, distance):
        """Quick jog axis by small amount"""
        controller_key = f'lts_{axis.lower()}'
        if controller_key in self.lts_controllers:
            self.lts_controllers[controller_key].move_relative(distance)
            self.log_event(f"{axis}-axis jogged {distance:+.3f} mm")
    
    def set_rotation_speed(self):
        """Set stepper rotation speed"""
        if self.stepper_controller:
            speed = self.rotation_target_input.value()
            self.stepper_controller.set_speed_rps(speed)
            self.log_event(f"Rotation speed set to {speed:.2f} RPS")
    
    def quick_rotation(self, speed):
        """Quick rotation speed preset"""
        self.rotation_target_input.setValue(speed)
        self.set_rotation_speed()
    
    def emergency_stop_all(self):
        """Emergency stop all axes"""
        if self.stepper_controller:
            self.stepper_controller.stop()
        for controller in self.lts_controllers.values():
            controller.stop()
        self.log_event("EMERGENCY STOP - All axes halted")
        QMessageBox.warning(self, "Emergency Stop", "All axes have been stopped!")
    
    def load_path_file(self):
        """Load CSV path file"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Path File", "", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    reader = csv.DictReader(f)
                    self.path_data = list(reader)
                
                self.path_file_input.setText(file_path)
                self.display_path_preview()
                self.execute_btn.setEnabled(True)
                self.log_event(f"Loaded path file: {file_path} ({len(self.path_data)} steps)")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")
    
    def display_path_preview(self):
        """Display path data in table"""
        if not hasattr(self, 'path_data') or not self.path_data:
            return
        
        headers = list(self.path_data[0].keys())
        self.path_table.setColumnCount(len(headers))
        self.path_table.setHorizontalHeaderLabels(headers)
        self.path_table.setRowCount(min(10, len(self.path_data)))
        
        for i, row in enumerate(self.path_data[:10]):
            for j, header in enumerate(headers):
                self.path_table.setItem(i, j, QTableWidgetItem(str(row[header])))
        
        self.path_table.resizeColumnsToContents()
    
    def execute_path(self):
        """Execute the loaded path"""
        if not hasattr(self, 'path_data') or not self.path_data:
            QMessageBox.warning(self, "No Path", "Please load a path file first")
            return
        
        # Check which axes are enabled and connected
        active_controllers = {}
        for axis, config in self.axes_config.items():
            if config['enabled']:
                controller_key = config['controller']
                if controller_key == 'stepper' and self.stepper_controller:
                    active_controllers[controller_key] = self.stepper_controller
                elif controller_key.startswith('lts_') and controller_key in self.lts_controllers:
                    active_controllers[controller_key] = self.lts_controllers[controller_key]
                else:
                    QMessageBox.warning(self, "Controller Error", 
                                      f"{axis} axis is enabled but controller is not connected")
                    return
        
        if not active_controllers:
            QMessageBox.warning(self, "No Axes", "Please enable at least one axis for path execution")
            return
        
        # Start path execution thread
        self.path_thread = PathExecutionThread(self.path_data, active_controllers, self.axes_config)
        self.path_thread.progress_update.connect(self.update_path_progress)
        self.path_thread.path_complete.connect(self.path_execution_complete)
        self.path_thread.error_occurred.connect(self.path_execution_error)
        
        self.path_thread.start()
        
        self.execute_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_path_btn.setEnabled(True)
        self.log_event("Path execution started")
    
    def pause_path(self):
        """Pause/resume path execution"""
        # Implementation depends on your needs
        self.log_event("Path execution paused")
    
    def stop_path(self):
        """Stop path execution"""
        if self.path_thread and self.path_thread.isRunning():
            self.path_thread.stop()
            self.path_thread.wait()
        
        self.execute_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_path_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Path stopped")
        self.log_event("Path execution stopped")
    
    def update_path_progress(self, progress, message):
        """Update path execution progress"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)
    
    def path_execution_complete(self):
        """Handle path execution completion"""
        self.execute_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_path_btn.setEnabled(False)
        self.progress_bar.setValue(100)
        self.progress_label.setText("Path completed successfully")
        self.log_event("Path execution completed")
        QMessageBox.information(self, "Complete", "Path execution finished!")
    
    def path_execution_error(self, error_msg):
        """Handle path execution error"""
        self.execute_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_path_btn.setEnabled(False)
        self.log_event(f"Path execution error: {error_msg}")
        QMessageBox.critical(self, "Execution Error", f"Path execution failed:\n{error_msg}")
    
    def update_status(self):
        """Update real-time status displays"""
        # Update stepper status
        if self.stepper_controller:
            status = self.stepper_controller.get_status()
            if status:
                current, target, pos = status
                self.rotation_speed_label.setText(f"{current:.2f} RPS")
        
        # Update linear stage positions
        for axis in ['X', 'Y', 'Z']:
            controller_key = f'lts_{axis.lower()}'
            if controller_key in self.lts_controllers:
                pos = self.lts_controllers[controller_key].get_position()
                getattr(self, f'{axis.lower()}_pos_label').setText(f"{pos:.3f} mm")
    
    def log_event(self, message):
        """Add event to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def apply_style(self):
        """Apply custom styling"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 3px;
                padding: 5px 10px;
                background-color: #e0e0e0;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 3px;
            }
        """)
    
    def closeEvent(self, event):
        """Handle window close"""
        # Stop path execution if running
        if self.path_thread and self.path_thread.isRunning():
            self.path_thread.stop()
            self.path_thread.wait()
        
        # Stop all controllers
        if self.stepper_controller:
            self.stepper_controller.stop()
            self.stepper_controller.close()
        
        for controller in self.lts_controllers.values():
            controller.stop()
            controller.close()
        
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    gui = UnifiedMotionControlGUI()
    gui.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()