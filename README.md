# Unified Motion Control System - Documentation

## Overview
The Unified Motion Control System provides a comprehensive GUI for controlling both Thorlabs LTS linear stages and a Pi Pico W stepper motor. It supports manual control, automated path execution from CSV files, and multi-axis coordination.

---

## Table of Contents
1. [Hardware Setup](#hardware-setup)
2. [Software Installation](#software-installation)
3. [GUI Overview](#gui-overview)
4. [Connection Setup](#connection-setup)
5. [Manual Control](#manual-control)
6. [Path Execution](#path-execution)
7. [CSV File Format](#csv-file-format)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## Hardware Setup

### Required Hardware
- **Pi Pico W** with stepper motor driver (for rotation axis)
- **Thorlabs LTS Series** linear stages (up to 3 axes: X, Y, Z)
- USB cables for each device
- Proper power supplies for all motors

**Hardware Note**: Do the microstepping, baudrate, driver configurations according to stepper/driver configuration. Example Pi Pico script is given for RS PRO stepper and CW230 stepper driver.

### Connections
1. Connect Pi Pico W via USB to computer
2. Connect each Thorlabs LTS stage via USB
3. Ensure all power supplies are connected and turned on
4. Verify all stages are mechanically assembled and limit switches functional

---

## Software Installation

### Prerequisites
```bash
pip install PyQt5
pip install pyserial
```

### File Structure
```
project/
├── stepper_controller.py          # Pico W stepper controller
├── lts_controller.py              # Thorlabs LTS controller
├── unified_motion_control.py      # Main GUI application
└── paths/                         # CSV path files directory
    ├── linear_scan_x.csv
    ├── grid_pattern_xy.csv
    └── full_motion.csv
```

### Running the Application
```bash
python unified_motion_control.py
```

---

## GUI Overview

The application has 4 main tabs:

### 1. **Connection Tab**
- Connect/disconnect all devices
- Configure which axes are active
- Home linear stages

### 2. **Manual Control Tab**
- Direct control of individual axes
- Quick jog buttons
- Emergency stop

### 3. **Path Execution Tab**
- Load CSV path files
- Preview motion paths
- Execute automated sequences
- Monitor progress

### 4. **Status & Monitoring Tab**
- Real-time device status
- Event logging
- System diagnostics

---

## Connection Setup

### Step-by-Step Connection

#### 1. Connect Stepper Motor (Rotation Axis)
1. Go to **Connection** tab
2. Select the Pi Pico W port from dropdown (e.g., `COM3` or `/dev/ttyACM0`)
3. Click **Connect**
4. Click **Enable** to power the motor
5. Status should show "Connected" in green

#### 2. Connect Linear Stages
For each axis (X, Y, Z):
1. Select the appropriate port for the stage
2. Click **Connect** next to the axis
3. Click **Home** to initialize the stage (moves to home position)
4. Check **Enable for Path** if you want to use this axis in automated paths

#### 3. Verify Connections
- Go to **Status & Monitoring** tab
- All connected devices should show "Connected" status
- Check the event log for any errors

---

## Manual Control

### Linear Axes (X/Y/Z)

#### Absolute Move
1. Enter target position in mm (e.g., `25.5`)
2. Click **Move Absolute**
3. Stage moves to exact position

#### Relative Move
1. Enter distance to move (e.g., `5.0` or `-10.0`)
2. Click **Move Relative**
3. Stage moves that distance from current position

#### Quick Jog
- Use jog buttons for precise positioning:
  - **±0.1 mm**: Fine adjustment
  - **±1 mm**: Medium steps
  - **±10 mm**: Large movements

#### Current Position
- Real-time position displayed in mm
- Updated 10 times per second

### Rotation Axis (Stepper Motor)

#### Speed Control
- **Target Speed**: Enter desired speed in RPS (revolutions per second)
  - Positive = clockwise
  - Negative = counter-clockwise
- Click **Set Speed** to apply
- Current speed ramps smoothly to target

#### Quick Speed Buttons
- **Stop**: Immediately ramp to zero
- **±1, ±2, ±5, ±10**: Preset speeds in RPS

### Emergency Stop
- **EMERGENCY STOP ALL** button stops ALL axes immediately
- Use in case of collision or unexpected behavior
- All motors halt but remain powered

---

## Path Execution

### Loading a Path File

1. Go to **Path Execution** tab
2. Click **Browse CSV**
3. Select your path file
4. Preview shows first 10 steps in table

### Configuring Execution

#### Repeat Count
- Set how many times to execute the path
- Default: 1 (single execution)
- Range: 1-1000

#### Step Delay
- Time to wait at each step (in milliseconds)
- Default: 100 ms
- Use longer delays for settling time or observations

### Executing the Path

1. Ensure required axes are connected and enabled
2. Click **Execute Path**
3. Progress bar shows completion percentage
4. **Pause** button temporarily halts execution (resume by clicking again)
5. **Stop Path** button aborts execution

### Path Execution Behavior

- **Linear Axes**: Moves to absolute positions specified in CSV
- **Rotation Axis**: Sets speed to value specified in CSV
- System waits for moves to complete before proceeding to next step
- Thread-based execution keeps GUI responsive

---

## CSV File Format

### General Rules

1. **Header Row**: First row contains axis names
2. **Data Rows**: Each row is one motion step
3. **Delimiters**: Use commas (`,`)
4. **Decimal Point**: Use period (`.`) not comma
5. **Axis Names**: Must exactly match: `X`, `Y`, `Z`, `Rotation`
6. **Missing Axes**: Only include axes you want to control

### Single Axis Example
```csv
X
0.0
10.0
20.0
30.0
```
- Moves X-axis through 4 positions
- Other axes remain stationary

### Multi-Axis Example
```csv
X,Y,Z
0.0,0.0,0.0
10.0,5.0,2.0
20.0,10.0,4.0
```
- Coordinates all three axes
- Each row executed simultaneously

### Including Rotation
```csv
X,Y,Rotation
0.0,0.0,0.0
10.0,0.0,2.5
20.0,10.0,5.0
```
- Linear stages move to X,Y positions
- Stepper motor sets speed to Rotation value (RPS)

### Units
- **X, Y, Z**: Millimeters (mm)
- **Rotation**: Revolutions per second (RPS)
  - Positive values = forward rotation
  - Negative values = reverse rotation
  - Zero = stop

### Common Patterns

#### Grid Scan
```csv
X,Y
0,0
10,0
20,0
0,10
10,10
20,10
```

#### Z-Stack
```csv
Z
0.0
1.0
2.0
3.0
4.0
```

#### Spiral
```csv
X,Y
5,0
3.5,3.5
0,5
-3.5,3.5
-5,0
```

---

## Troubleshooting

### Connection Issues

**Problem**: "Could not find Pico W" or port not detected
- **Solution**: 
  - Check USB cable connection
  - Try different USB port
  - Click "Refresh All Ports"
  - Verify device appears in Device Manager (Windows) or `ls /dev/tty*` (Linux/Mac)

**Problem**: "Failed to connect" error
- **Solution**:
  - Close other programs using the port (Arduino IDE, other serial monitors)
  - Restart the device
  - Check baud rate is 115200

### Motion Issues

**Problem**: Stage doesn't move
- **Solution**:
  - Verify stage is connected (green status)
  - Check if motor is enabled
  - Ensure no mechanical obstructions
  - Check power supply to motor driver
  - Verify limit switches not triggered

**Problem**: Stepper motor not rotating
- **Solution**:
  - Click "Enable" button for stepper
  - Check EN_PIN connection (should be LOW to enable)
  - Verify power supply to stepper driver
  - Check if speed is non-zero

**Problem**: Motion is jerky or stuttering
- **Solution**:
  - Reduce acceleration rate
  - Check for loose wiring
  - Verify adequate power supply current
  - Reduce maximum speed

### Path Execution Issues

**Problem**: "Controller not connected" when executing path
- **Solution**:
  - Enable required axes in Connection tab
  - Verify all needed controllers are connected
  - Check "Enable for Path" checkbox for each axis

**Problem**: Path stops mid-execution
- **Solution**:
  - Check event log for errors
  - Verify no limit switches hit
  - Ensure positions are within stage travel range
  - Check CSV file format is correct

**Problem**: Wrong axis moves or unexpected behavior
- **Solution**:
  - Verify CSV column headers exactly match axis names
  - Check axis configuration in Connection tab
  - Ensure correct controller assigned to each axis

### CSV File Issues

**Problem**: "Failed to load file" error
- **Solution**:
  - Check file is valid CSV format
  - Verify no extra commas or special characters
  - Use UTF-8 encoding
  - Check file is not open in another program

**Problem**: Some steps skipped
- **Solution**:
  - Check all rows have same number of columns
  - No empty rows in CSV file
  - Verify numeric values (no text in data rows)

---

## API Reference

### PicoStepperController

```python
controller = PicoStepperController(port='COM3', baudrate=115200)
```

#### Methods
- `enable_motor()`: Power on motor driver
- `disable_motor()`: Power off motor driver
- `set_speed_rps(rps)`: Set rotation speed (revolutions per second)
- `set_speed_steps(steps_per_sec)`: Set speed in steps/second
- `stop()`: Ramp down to zero speed
- `set_ramp_rate(rate)`: Set acceleration (steps/sec²)
- `get_status()`: Returns `(current_rps, target_rps, position)`
- `close()`: Close serial connection

### ThorlabsLTSController

```python
controller = ThorlabsLTSController(port='COM4')
```

#### Methods
- `home()`: Move to home position
- `move_absolute(position)`: Move to absolute position (mm)
- `move_relative(distance)`: Move relative distance (mm)
- `get_position()`: Returns current position (mm)
- `stop()`: Halt motion immediately
- `is_moving()`: Returns True if stage is moving
- `close()`: Close connection

### GUI Customization

#### Adding Custom Axes
Edit `axes_config` in `__init__`:
```python
self.axes_config = {
    'X': {'controller': 'lts_x', 'type': 'linear', 'enabled': False},
    'Custom': {'controller': 'custom', 'type': 'linear', 'enabled': False}
}
```

#### Modifying Speed Limits
In stepper sections, change:
```python
self.rotation_target_input.setRange(-50, 50)  # Change to your limits
```

#### Adjusting Update Rate
```python
self.update_timer.start(100)  # Change 100 to desired ms
```

---

## Safety Considerations

### Before Operation
1. ✅ Verify all mechanical assemblies are secure
2. ✅ Check emergency stop button is accessible
3. ✅ Ensure workspace is clear of obstructions
4. ✅ Verify limit switches are functional
5. ✅ Test with slow speeds first

### During Operation
- Monitor motion in real-time
- Keep hands clear of moving parts
- Use emergency stop if anything unexpected occurs
- Stay within stage travel limits

### Emergency Procedures
1. Click **EMERGENCY STOP ALL** button
2. Physically turn off power if needed
3. Check for mechanical damage
4. Re-home stages before resuming

---

## Best Practices

### Path Design
- Start and end at safe positions (e.g., 0,0,0)
- Use gradual speed changes for rotation
- Keep moves within stage limits
- Test paths with small movements first
- Add adequate step delays for settling

### Performance Optimization
- Reduce update rate if CPU usage high
- Use relative moves for small adjustments
- Batch similar operations together
- Close unused programs during operation

### Maintenance
- Regularly clean linear stage rails
- Check cable connections periodically
- Lubricate stages per manufacturer recommendations
- Update firmware as available
- Back up important path files

---

## Support & Additional Resources

### Documentation Links
- Thorlabs LTS Manual: Check manufacturer website
- Pi Pico W: https://www.raspberrypi.com/documentation/
- PyQt5 Docs: https://www.riverbankcomputing.com/static/Docs/PyQt5/

### Common Commands Quick Reference
| Action | Command | Example |
|--------|---------|---------|
| Move X absolute | Enter value, click Move Absolute | `25.5` mm |
| Jog Y axis | Click jog button | `+1.0` mm |
| Set rotation | Enter RPS, click Set Speed | `3.5` RPS |
| Stop all | Click Emergency Stop | N/A |
| Load path | Browse CSV | `my_path.csv` |
| Execute | Click Execute Path | N/A |

---

## Version History
- **v1.0** - Initial release with basic functionality
- Multi-axis support (X, Y, Z, Rotation)
- CSV path execution
- Real-time monitoring
- Manual and automated control modes

---

## License & Credits
Created for motion control applications using Thorlabs LTS stages and Pi Pico W stepper motors.

For questions or issues, check the event log in the Status tab for diagnostic information.
