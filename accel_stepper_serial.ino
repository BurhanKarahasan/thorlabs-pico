#include <AccelStepper.h>

// ======== Stepper Config ========
#define EN_PIN  11
#define DIR_PIN 12
#define STEP_PIN 13
#define STEPS_PER_REV 200

AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

float currentSpeed = 0;      // current speed in steps/sec
float targetSpeed = 0;       // desired speed in steps/sec
float rampRate = 10;        // steps/sec^2 (acceleration)

// ======== Serial Protocol ========
String inputBuffer = "";
bool stringComplete = false;

void setup() {
  Serial.begin(115200);
  while (!Serial) { ; } // Wait for serial port to connect
  
  pinMode(EN_PIN, OUTPUT);
  digitalWrite(EN_PIN, LOW);
  
  // Stepper settings
  stepper.setMaxSpeed(10000);
  stepper.setAcceleration(rampRate);
  
  Serial.println("READY"); // Signal to Python that we're ready
  inputBuffer.reserve(64);
}

void loop() {
  // Handle incoming serial commands
  processSerialCommands();
  
  // Smooth speed control
  if (currentSpeed != targetSpeed) {
    if (abs(currentSpeed - targetSpeed) < 10) {
      currentSpeed = targetSpeed;
    } else if (currentSpeed < targetSpeed) {
      currentSpeed += 10;
    } else {
      currentSpeed -= 10;
    }
    stepper.setSpeed(currentSpeed);
  }
  
  stepper.runSpeed();
}

void processSerialCommands() {
  while (Serial.available() > 0) {
    char inChar = (char)Serial.read();
    
    if (inChar == '\n') {
      stringComplete = true;
    } else {
      inputBuffer += inChar;
    }
  }
  
  if (stringComplete) {
    parseCommand(inputBuffer);
    inputBuffer = "";
    stringComplete = false;
  }
}

void parseCommand(String cmd) {
  cmd.trim();
  
  // Command format: COMMAND:VALUE
  int separatorIndex = cmd.indexOf(':');
  
  if (separatorIndex == -1) {
    // Simple commands without values
    if (cmd == "STOP") {
      targetSpeed = 0;
      Serial.println("OK:STOPPED");
    } 
    else if (cmd == "STATUS") {
      sendStatus();
    }
    else if (cmd == "ENABLE") {
      digitalWrite(EN_PIN, LOW);
      Serial.println("OK:ENABLED");
    }
    else if (cmd == "DISABLE") {
      digitalWrite(EN_PIN, HIGH);
      targetSpeed = 0;
      currentSpeed = 0;
      Serial.println("OK:DISABLED");
    }
    else {
      Serial.println("ERROR:UNKNOWN_COMMAND");
    }
  } 
  else {
    // Commands with values
    String command = cmd.substring(0, separatorIndex);
    String value = cmd.substring(separatorIndex + 1);
    
    if (command == "SPEED_RPS") {
      float rps = value.toFloat();
      targetSpeed = rps * STEPS_PER_REV;
      Serial.print("OK:SPEED_SET:");
      Serial.println(rps);
    }
    else if (command == "SPEED_STEPS") {
      targetSpeed = value.toFloat();
      Serial.print("OK:SPEED_SET:");
      Serial.println(targetSpeed);
    }
    else if (command == "RAMP") {
      rampRate = value.toFloat();
      stepper.setAcceleration(rampRate);
      Serial.print("OK:RAMP_SET:");
      Serial.println(rampRate);
    }
    else {
      Serial.println("ERROR:UNKNOWN_COMMAND");
    }
  }
}

void sendStatus() {
  Serial.print("STATUS:");
  Serial.print(currentSpeed / STEPS_PER_REV);
  Serial.print(",");
  Serial.print(targetSpeed / STEPS_PER_REV);
  Serial.print(",");
  Serial.println(stepper.currentPosition());
}
