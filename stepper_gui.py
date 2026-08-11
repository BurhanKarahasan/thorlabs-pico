import sys
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                              QComboBox, QGroupBox, QDoubleSpinBox, QSpinBox,
                              QMessageBox)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont


class StepperControlGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.serial_connection = None
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.request_status)
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Stepper Motor Controller")
        self.setGeometry(100, 100, 500, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Connection Group
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout()
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.refresh_ports()
        port_layout.addWidget(self.port_combo)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)
        conn_layout.addLayout(port_layout)
        
        connect_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.toggle_connection)
        connect_layout.addWidget(self.connect_btn)
        
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        connect_layout.addWidget(self.connection_status)
        conn_layout.addLayout(connect_layout)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # Configuration Group
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout()
        
        steps_layout = QHBoxLayout()
        steps_layout.addWidget(QLabel("Steps per Revolution:"))
        self.steps_spin = QSpinBox()
        self.steps_spin.setRange(1, 10000)
        self.steps_spin.setValue(200)
        steps_layout.addWidget(self.steps_spin)
        
        set_steps_btn = QPushButton("Set")
        set_steps_btn.clicked.connect(self.set_steps_per_rev)
        steps_layout.addWidget(set_steps_btn)
        config_layout.addLayout(steps_layout)
        
        ramp_layout = QHBoxLayout()
        ramp_layout.addWidget(QLabel("Acceleration (steps/s²):"))
        self.ramp_spin = QDoubleSpinBox()
        self.ramp_spin.setRange(1, 10000)
        self.ramp_spin.setValue(100)
        ramp_layout.addWidget(self.ramp_spin)
        
        set_ramp_btn = QPushButton("Set")
        set_ramp_btn.clicked.connect(self.set_ramp_rate)
        ramp_layout.addWidget(set_ramp_btn)
        config_layout.addLayout(ramp_layout)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # Speed Control Group
        speed_group = QGroupBox("Speed Control")
        speed_layout = QVBoxLayout()
        
        rpm_layout = QHBoxLayout()
        rpm_layout.addWidget(QLabel("Target RPM:"))
        self.rpm_spin = QDoubleSpinBox()
        self.rpm_spin.setRange(-1000, 1000)
        self.rpm_spin.setDecimals(2)
        self.rpm_spin.setValue(0)
        rpm_layout.addWidget(self.rpm_spin)
        
        set_rpm_btn = QPushButton("Set RPM")
        set_rpm_btn.clicked.connect(self.set_rpm)
        rpm_layout.addWidget(set_rpm_btn)
        speed_layout.addLayout(rpm_layout)
        
        # Quick speed buttons
        quick_layout = QHBoxLayout()
        speeds = [-100, -50, -10, 0, 10, 50, 100]
        for speed in speeds:
            btn = QPushButton(f"{speed:+d}")
            btn.clicked.connect(lambda checked, s=speed: self.quick_set_rpm(s))
            quick_layout.addWidget(btn)
        speed_layout.addLayout(quick_layout)
        
        speed_group.setLayout(speed_layout)
        main_layout.addWidget(speed_group)
        
        # Control Buttons
        control_layout = QHBoxLayout()
        
        self.enable_btn = QPushButton("Enable")
        self.enable_btn.clicked.connect(self.enable_motor)
        self.enable_btn.setEnabled(False)
        control_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("Disable")
        self.disable_btn.clicked.connect(self.disable_motor)
        self.disable_btn.setEnabled(False)
        control_layout.addWidget(self.disable_btn)
        
        stop_btn = QPushButton("STOP")
        stop_btn.clicked.connect(self.stop_motor)
        stop_btn.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        stop_btn.setEnabled(False)
        self.stop_btn = stop_btn
        control_layout.addWidget(stop_btn)
        
        main_layout.addLayout(control_layout)
        
        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()
        
        self.current_rpm_label = QLabel("Current RPM: 0.00")
        self.current_rpm_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        status_layout.addWidget(self.current_rpm_label)
        
        self.target_rpm_label = QLabel("Target RPM: 0.00")
        status_layout.addWidget(self.target_rpm_label)
        
        self.position_label = QLabel("Position: 0 steps")
        status_layout.addWidget(self.position_label)
        
        self.steps_config_label = QLabel("Steps/Rev: 200")
        status_layout.addWidget(self.steps_config_label)
        
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
        
        main_layout.addStretch()
        
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")
            
    def toggle_connection(self):
        if self.serial_connection and self.serial_connection.is_open:
            self.disconnect()
        else:
            self.connect()
            
    def connect(self):
        port_text = self.port_combo.currentText()
        if not port_text:
            QMessageBox.warning(self, "Error", "No port selected")
            return
            
        port = port_text.split(" - ")[0]
        
        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            import time
            
            # Clear any existing data in buffer
            time.sleep(0.5)
            self.serial_connection.reset_input_buffer()
            
            # Try to get status to verify connection
            max_attempts = 3
            for attempt in range(max_attempts):
                self.serial_connection.write(b"STATUS\n")
                time.sleep(0.2)
                
                if self.serial_connection.in_waiting:
                    response = self.serial_connection.readline().decode().strip()
                    if response.startswith("STATUS:") or response == "READY":
                        # Connection successful
                        self.connection_status.setText("Connected")
                        self.connection_status.setStyleSheet("color: green; font-weight: bold;")
                        self.connect_btn.setText("Disconnect")
                        self.enable_btn.setEnabled(True)
                        self.disable_btn.setEnabled(True)
                        self.stop_btn.setEnabled(True)
                        self.status_timer.start(500)  # Update status every 500ms
                        
                        # Clear buffer again and request initial status
                        time.sleep(0.1)
                        self.serial_connection.reset_input_buffer()
                        self.request_status()
                        return
            
            raise Exception("No response from device after multiple attempts")
            
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect: {str(e)}")
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
                
    def disconnect(self):
        self.status_timer.stop()
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
        self.connection_status.setText("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.connect_btn.setText("Connect")
        self.enable_btn.setEnabled(False)
        self.disable_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        
    def send_command(self, command):
        if not self.serial_connection or not self.serial_connection.is_open:
            QMessageBox.warning(self, "Error", "Not connected")
            return None
            
        try:
            self.serial_connection.write(f"{command}\n".encode())
            response = self.serial_connection.readline().decode().strip()
            return response
        except Exception as e:
            QMessageBox.critical(self, "Communication Error", f"Failed to send command: {str(e)}")
            return None
            
    def set_rpm(self):
        rpm = self.rpm_spin.value()
        response = self.send_command(f"RPM:{rpm}")
        if response and response.startswith("OK"):
            self.target_rpm_label.setText(f"Target RPM: {rpm:.2f}")
            
    def quick_set_rpm(self, rpm):
        self.rpm_spin.setValue(rpm)
        self.set_rpm()
        
    def set_steps_per_rev(self):
        steps = self.steps_spin.value()
        response = self.send_command(f"STEPS_PER_REV:{steps}")
        if response and response.startswith("OK"):
            self.steps_config_label.setText(f"Steps/Rev: {steps}")
            
    def set_ramp_rate(self):
        ramp = self.ramp_spin.value()
        self.send_command(f"RAMP:{ramp}")
        
    def enable_motor(self):
        self.send_command("ENABLE")
        
    def disable_motor(self):
        self.send_command("DISABLE")
        
    def stop_motor(self):
        self.send_command("STOP")
        self.rpm_spin.setValue(0)
        
    def request_status(self):
        if not self.serial_connection or not self.serial_connection.is_open:
            return
            
        try:
            self.serial_connection.write(b"STATUS\n")
            response = self.serial_connection.readline().decode().strip()
            
            if response.startswith("STATUS:"):
                data = response.split(":")[1].split(",")
                if len(data) >= 4:
                    current_rpm = float(data[0])
                    target_rpm = float(data[1])
                    position = int(data[2])
                    steps_per_rev = int(data[3])
                    
                    self.current_rpm_label.setText(f"Current RPM: {current_rpm:.2f}")
                    self.target_rpm_label.setText(f"Target RPM: {target_rpm:.2f}")
                    self.position_label.setText(f"Position: {position} steps")
                    self.steps_config_label.setText(f"Steps/Rev: {steps_per_rev}")
        except Exception as e:
            print(f"Status update error: {e}")
            
    def closeEvent(self, event):
        if self.serial_connection and self.serial_connection.is_open:
            self.send_command("STOP")
            self.disconnect()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = StepperControlGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()