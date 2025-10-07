"""
Thorlabs LTS Linear Stage Controller using Kinesis API
Supports serial number-based connection
"""

# Option 1: Using pylablib (recommended - easier to use)
try:
    from pylablib.devices import Thorlabs
    PYLABLIB_AVAILABLE = True
except ImportError:
    PYLABLIB_AVAILABLE = False
    print("Warning: pylablib not installed. Install with: pip install pylablib")

# Option 2: Using Thorlabs Kinesis DLLs directly
try:
    import clr
    import sys
    # Add path to Kinesis DLLs (adjust path as needed)
    sys.path.append(r'C:\Program Files\Thorlabs\Kinesis')
    clr.AddReference("Thorlabs.MotionControl.DeviceManagerCLI")
    clr.AddReference("Thorlabs.MotionControl.GenericMotorCLI")
    clr.AddReference("Thorlabs.MotionControl.IntegratedStepperMotorsCLI")
    
    from Thorlabs.MotionControl.DeviceManagerCLI import DeviceManagerCLI
    from Thorlabs.MotionControl.GenericMotorCLI import MotorDirection
    from Thorlabs.MotionControl.IntegratedStepperMotorsCLI import LongTravelStage
    
    KINESIS_DLL_AVAILABLE = True
except:
    KINESIS_DLL_AVAILABLE = False
    print("Warning: Thorlabs Kinesis DLLs not found")


class ThorlabsLTSController:
    """
    Controller for Thorlabs Long Travel Stage (LTS) series using Kinesis.
    
    Can use either pylablib or native Kinesis DLLs.
    """
    
    def __init__(self, serial_number: str, use_pylablib: bool = True):
        """
        Initialize connection to Thorlabs LTS stage.
        
        Args:
            serial_number: Device serial number (e.g., "45123456")
            use_pylablib: If True, use pylablib; if False, use Kinesis DLLs
        """
        self.serial_number = serial_number
        self.device = None
        self.use_pylablib = use_pylablib and PYLABLIB_AVAILABLE
        
        if self.use_pylablib:
            self._init_pylablib()
        elif KINESIS_DLL_AVAILABLE:
            self._init_kinesis_dll()
        else:
            raise RuntimeError("Neither pylablib nor Kinesis DLLs are available")
    
    def _init_pylablib(self):
        """Initialize using pylablib"""
        try:
            self.device = Thorlabs.KinesisMotor(self.serial_number)
            print(f"Connected to {self.serial_number} via pylablib")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.serial_number}: {e}")
    
    def _init_kinesis_dll(self):
        """Initialize using Kinesis DLLs"""
        try:
            DeviceManagerCLI.BuildDeviceList()
            self.device = LongTravelStage.CreateLongTravelStage(self.serial_number)
            
            if self.device is None:
                raise ConnectionError(f"Could not create device for {self.serial_number}")
            
            self.device.Connect(self.serial_number)
            
            # Wait for device to be ready
            if not self.device.IsSettingsInitialized():
                self.device.WaitForSettingsInitialized(5000)
            
            # Start polling
            self.device.StartPolling(250)
            
            # Enable device
            self.device.EnableDevice()
            
            print(f"Connected to {self.serial_number} via Kinesis DLLs")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.serial_number}: {e}")
    
    def home(self) -> bool:
        """
        Home the stage (move to home position).
        
        Returns:
            True if successful
        """
        try:
            if self.use_pylablib:
                self.device.home()
                self.device.wait_for_home()
            else:
                self.device.Home(60000)  # 60 second timeout
            return True
        except Exception as e:
            print(f"Homing error: {e}")
            return False
    
    def move_absolute(self, position: float) -> bool:
        """
        Move to absolute position.
        
        Args:
            position: Target position in mm
            
        Returns:
            True if successful
        """
        try:
            if self.use_pylablib:
                self.device.move_to(position)
            else:
                # Convert mm to device units (typically 34304 counts per mm for LTS)
                device_units = int(position * 34304)
                self.device.MoveTo(device_units, 60000)
            return True
        except Exception as e:
            print(f"Move error: {e}")
            return False
    
    def move_relative(self, distance: float) -> bool:
        """
        Move relative distance from current position.
        
        Args:
            distance: Distance to move in mm (positive or negative)
            
        Returns:
            True if successful
        """
        try:
            if self.use_pylablib:
                self.device.move_by(distance)
            else:
                device_units = int(distance * 34304)
                self.device.MoveRelative(MotorDirection.Forward if distance > 0 else MotorDirection.Backward, 
                                        abs(device_units), 60000)
            return True
        except Exception as e:
            print(f"Move error: {e}")
            return False
    
    def get_position(self) -> float:
        """
        Get current position.
        
        Returns:
            Current position in mm
        """
        try:
            if self.use_pylablib:
                return self.device.get_position()
            else:
                device_units = self.device.Position
                return device_units / 34304.0  # Convert to mm
        except Exception as e:
            print(f"Position read error: {e}")
            return 0.0
    
    def stop(self) -> bool:
        """
        Stop motion immediately.
        
        Returns:
            True if successful
        """
        try:
            if self.use_pylablib:
                self.device.stop()
            else:
                self.device.Stop(60000)
            return True
        except Exception as e:
            print(f"Stop error: {e}")
            return False
    
    def is_moving(self) -> bool:
        """
        Check if stage is currently moving.
        
        Returns:
            True if moving, False if stationary
        """
        try:
            if self.use_pylablib:
                return self.device.is_moving()
            else:
                return self.device.Status.IsInMotion
        except:
            return False
    
    def wait_for_motion_complete(self, timeout: float = 60.0):
        """
        Wait for motion to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        import time
        start_time = time.time()
        
        while self.is_moving():
            if time.time() - start_time > timeout:
                self.stop()
                raise TimeoutError("Motion timeout")
            time.sleep(0.05)
    
    def close(self):
        """Close connection to device."""
        try:
            if self.device:
                if self.use_pylablib:
                    self.device.close()
                else:
                    self.device.StopPolling()
                    self.device.Disconnect()
                print(f"Disconnected from {self.serial_number}")
        except Exception as e:
            print(f"Close error: {e}")
    
    @staticmethod
    def list_devices():
        """
        List all available Kinesis devices.
        
        Returns:
            List of tuples: [(serial_number, device_type), ...]
        """
        devices = []
        
        if PYLABLIB_AVAILABLE:
            try:
                device_list = Thorlabs.list_kinesis_devices()
                for serial, dev_info in device_list:
                    devices.append((serial, dev_info))
            except Exception as e:
                print(f"Error listing devices with pylablib: {e}")
        
        elif KINESIS_DLL_AVAILABLE:
            try:
                DeviceManagerCLI.BuildDeviceList()
                device_list = DeviceManagerCLI.GetDeviceList()
                
                for serial in device_list:
                    # Get device type
                    device_info = DeviceManagerCLI.GetDeviceInfo(serial)
                    devices.append((serial, device_info.Description))
            except Exception as e:
                print(f"Error listing devices with Kinesis DLLs: {e}")
        
        return devices
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Example usage
if __name__ == "__main__":
    # List available devices
    print("Available Kinesis devices:")
    devices = ThorlabsLTSController.list_devices()
    for serial, dev_type in devices:
        print(f"  {serial}: {dev_type}")
    
    # Connect to a specific device
    if devices:
        serial_number = devices[0][0]  # Use first device
        
        with ThorlabsLTSController(serial_number) as stage:
            print(f"\nConnected to {serial_number}")
            
            # Home the stage
            print("Homing...")
            stage.home()
            
            # Move to position
            print("Moving to 10mm...")
            stage.move_absolute(10.0)
            stage.wait_for_motion_complete()
            
            # Get position
            pos = stage.get_position()
            print(f"Current position: {pos:.3f} mm")
            
            # Move relative
            print("Moving +5mm...")
            stage.move_relative(5.0)
            stage.wait_for_motion_complete()
            
            pos = stage.get_position()
            print(f"Current position: {pos:.3f} mm")
            
            # Return to zero
            print("Returning to zero...")
            stage.move_absolute(0.0)
            stage.wait_for_motion_complete()
            
            print("Done!")
    else:
        print("\nNo devices found. Make sure:")
        print("  1. Devices are connected via USB")
        print("  2. Kinesis software is closed")
        print("  3. Drivers are installed")