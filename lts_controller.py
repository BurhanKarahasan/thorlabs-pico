import clr
import os
import time
from System import Decimal, Convert


class ThorlabsLTSController:
    def __init__(self, serial_number):
        self.serial_number = serial_number
        self.device = None
        self.connected = False

        self._load_dotnet_libs()

    def _load_dotnet_libs(self):
        dll_path = "C:\\Program Files\\Thorlabs\\Kinesis\\"

        try:
            clr.AddReference(os.path.join(dll_path, "Thorlabs.MotionControl.DeviceManagerCLI.dll"))
            clr.AddReference(os.path.join(dll_path, "Thorlabs.MotionControl.GenericMotorCLI.dll"))
            clr.AddReference(os.path.join(dll_path, "Thorlabs.MotionControl.IntegratedStepperMotorsCLI.dll"))

            global DeviceManagerCLI, LongTravelStage
            from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
            from Thorlabs.MotionControl.IntegratedStepperMotorsCLI import LongTravelStage

            # Optional: preload shared motor interfaces if needed
            # from Thorlabs.MotionControl.GenericMotorCLI import VelocityParameters

        except Exception as e:
            raise ImportError(f"Failed to load Thorlabs Kinesis DLLs: {e}")

    def connect(self):
        try:
            print("[INFO] Building device list...")
            DeviceManagerCLI.BuildDeviceList()

            print(f"[INFO] Connecting to device {self.serial_number}...")
            self.device = LongTravelStage.CreateLongTravelStage(self.serial_number)
            self.device.Connect(self.serial_number)
            
            self.device.LoadMotorConfiguration(self.serial_number)

            if not self.device.IsSettingsInitialized():
                self.device.WaitForSettingsInitialized(10000)

            self.device.StartPolling(250)
            time.sleep(0.25)
            self.device.EnableDevice()
            time.sleep(0.25)

            self.connected = True
            print(f"[INFO] Connected to: {self.device.GetDeviceInfo().Description}")
        except Exception as e:
            raise RuntimeError(f"Connection failed: {e}")

    def home(self, velocity=10.0):
        if not self.connected:
            raise RuntimeError("Device not connected.")

        try:
            print("[INFO] Homing device...")
            params = self.device.GetHomingParams()
            params.Velocity = Decimal(velocity)
            self.device.SetHomingParams(params)
            self.device.Home(60000)
            print("[INFO] Homing complete.")
        except Exception as e:
            raise RuntimeError(f"Homing failed: {e}")

    def move_to(self, position_mm):
        if not self.connected:
            raise RuntimeError("Device not connected.")

        try:
            print(f"[INFO] Moving to {position_mm} mm...")
            self.device.MoveTo(Decimal(position_mm), 60000)
            print("[INFO] Movement complete.")
        except Exception as e:
            raise RuntimeError(f"Movement failed: {e}")
    
    def get_position(self):
        if not self.connected:
            raise RuntimeError("Device not connected.")

        try:
            dotnet_decimal = self.device.Position
            pos = float(str(dotnet_decimal))  # Correct casting
            #print(f"[INFO] Current Position: {pos:.2f} mm")
            return pos
        except Exception as e:
            raise RuntimeError(f"Could not read position: {e}")    
    
    def set_velocity(self, velocity_mm_s):
        if not self.connected:
            raise RuntimeError("Device not connected.")

        try:
            print(f"[INFO] Setting max velocity to {velocity_mm_s} mm/s...")
            vel_params = self.device.GetVelocityParams()
            vel_params.MaxVelocity = Decimal(velocity_mm_s)
            self.device.SetVelocityParams(vel_params)
        except Exception as e:
            raise RuntimeError(f"Failed to set velocity: {e}")

    def disconnect(self):
        if self.device:
            try:
                print("[INFO] Disconnecting device...")
                self.device.StopPolling()
                self.device.Disconnect()
                self.connected = False
                print("[INFO] Device disconnected.")
            except Exception as e:
                raise RuntimeError(f"Failed to disconnect: {e}")
