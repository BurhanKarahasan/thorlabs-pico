import serial
import serial.tools.list_ports
import time
from typing import Optional, Tuple

class PicoStepperController:
    """
    Interface for controlling Pi Pico W stepper motor via serial.
    
    Protocol:
    - Commands are sent as text strings ending with newline
    - Responses start with OK:, ERROR:, or STATUS:
    """
    
    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0):
        """
        Initialize connection to Pico W.
        
        Args:
            port: Serial port (e.g., 'COM3' or '/dev/ttyACM0'). If None, auto-detect.
            baudrate: Serial baudrate (default 115200)
            timeout: Read timeout in seconds
        """
        if port is None:
            port = self._find_pico()
            if port is None:
                raise ConnectionError("Could not find Pico W. Please specify port manually.")
        
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Wait for Arduino to reset
        
        # Wait for READY signal
        ready = False
        start_time = time.time()
        while time.time() - start_time < 5:
            if self.ser.in_waiting:
                line = self.ser.readline().decode('utf-8').strip()
                if line == "READY":
                    ready = True
                    break
        
        if not ready:
            print("Warning: Did not receive READY signal from Pico")
        
        print(f"Connected to Pico W on {port}")
    
    def _find_pico(self) -> Optional[str]:
        """Auto-detect Pico W serial port."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            # Pico W typically shows up with these identifiers
            if "USB Serial" in port.description or "Pico" in port.description:
                return port.device
        return None
    
    def _send_command(self, command: str) -> str:
        """
        Send command and wait for response.
        
        Args:
            command: Command string (newline will be added automatically)
            
        Returns:
            Response string from Pico
        """
        self.ser.write(f"{command}\n".encode('utf-8'))
        response = self.ser.readline().decode('utf-8').strip()
        return response
    
    def set_speed_rps(self, rps: float) -> bool:
        """
        Set motor speed in revolutions per second.
        
        Args:
            rps: Speed in revolutions per second (can be negative for reverse)
            
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command(f"SPEED_RPS:{rps}")
        return response.startswith("OK")
    
    def set_speed_steps(self, steps_per_sec: float) -> bool:
        """
        Set motor speed in steps per second.
        
        Args:
            steps_per_sec: Speed in steps per second
            
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command(f"SPEED_STEPS:{steps_per_sec}")
        return response.startswith("OK")
    
    def stop(self) -> bool:
        """
        Stop the motor (ramp down to zero speed).
        
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command("STOP")
        return response.startswith("OK")
    
    def enable_motor(self) -> bool:
        """
        Enable the stepper motor driver.
        
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command("ENABLE")
        return response.startswith("OK")
    
    def disable_motor(self) -> bool:
        """
        Disable the stepper motor driver (cuts power).
        
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command("DISABLE")
        return response.startswith("OK")
    
    def set_ramp_rate(self, rate: float) -> bool:
        """
        Set acceleration/deceleration rate.
        
        Args:
            rate: Ramp rate in steps/sec^2
            
        Returns:
            True if successful, False otherwise
        """
        response = self._send_command(f"RAMP:{rate}")
        return response.startswith("OK")
    
    def get_status(self) -> Optional[Tuple[float, float, int]]:
        """
        Get current motor status.
        
        Returns:
            Tuple of (current_rps, target_rps, position) or None if error
        """
        response = self._send_command("STATUS")
        if response.startswith("STATUS:"):
            try:
                data = response.split(":")[1]
                current, target, pos = data.split(",")
                return (float(current), float(target), int(pos))
            except:
                return None
        return None
    
    def close(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ======== Example Usage ========
if __name__ == "__main__":
    # Connect to Pico (auto-detect port)
    with PicoStepperController() as controller:
        print("Motor controller ready!")
        
        # Enable motor
        controller.enable_motor()
        
        # Set speed to 2 revolutions per second
        print("Setting speed to 2 RPS...")
        controller.set_speed_rps(2.0)
        time.sleep(3)
        
        # Check status
        status = controller.get_status()
        if status:
            current, target, pos = status
            print(f"Current: {current:.2f} RPS, Target: {target:.2f} RPS, Position: {pos} steps")
        
        # Change speed
        print("Setting speed to 5 RPS...")
        controller.set_speed_rps(5.0)
        time.sleep(3)
        
        # Reverse direction
        print("Reversing direction...")
        controller.set_speed_rps(-3.0)
        time.sleep(3)
        
        # Stop motor
        print("Stopping motor...")
        controller.stop()
        time.sleep(2)
        
        # Disable motor
        controller.disable_motor()
        print("Done!")