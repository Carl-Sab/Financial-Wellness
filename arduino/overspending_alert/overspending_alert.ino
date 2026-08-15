// Financial Wellness overspending alert.
// Browser protocol at 115200 baud:
//   P:<probability>\n  e.g. P:0.742500
//   S\n               stop the current alert

#include <Arduino.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

const byte BUZZER_PIN = 2;
const byte LED_PIN = 8;
const byte BUTTON_PIN = 9;

const unsigned long MEDIUM_INTERVAL_MS = 1000;
const unsigned long HIGH_INTERVAL_MS = 200;
const unsigned long PULSE_DURATION_MS = 100;
const unsigned long BUTTON_DEBOUNCE_MS = 35;
const unsigned int BUZZER_FREQUENCY_HZ = 2000;
// Leave true for a passive piezo buzzer. Set false for an active buzzer
// module that sounds whenever its signal pin is HIGH.
const bool PASSIVE_BUZZER = true;

const float MEDIUM_THRESHOLD = 0.33;
const float HIGH_THRESHOLD = 0.66;

char serialBuffer[32];
byte serialLength = 0;

float currentProbability = 0.0;
unsigned long alertIntervalMs = 0;
unsigned long lastPulseStartedAt = 0;
bool alertAcknowledged = false;
bool pulseOn = false;

bool lastButtonReading = HIGH;
bool stableButtonState = HIGH;
unsigned long buttonChangedAt = 0;

void setOutputs(bool enabled) {
  pulseOn = enabled;
  digitalWrite(LED_PIN, enabled ? HIGH : LOW);
  if (enabled) {
    if (PASSIVE_BUZZER) {
      tone(BUZZER_PIN, BUZZER_FREQUENCY_HZ);
    } else {
      digitalWrite(BUZZER_PIN, HIGH);
    }
  } else {
    noTone(BUZZER_PIN);
    digitalWrite(BUZZER_PIN, LOW);
  }
}

void stopAlert(bool acknowledge) {
  alertIntervalMs = 0;
  alertAcknowledged = acknowledge;
  setOutputs(false);
}

void applyProbability(float probability) {
  currentProbability = probability;
  alertAcknowledged = false;
  setOutputs(false);

  if (probability < MEDIUM_THRESHOLD) {
    alertIntervalMs = 0;
  } else if (probability <= HIGH_THRESHOLD) {
    alertIntervalMs = MEDIUM_INTERVAL_MS;
  } else {
    alertIntervalMs = HIGH_INTERVAL_MS;
  }

  // Start the first pulse immediately instead of making the user wait for
  // the first interval to elapse.
  if (alertIntervalMs > 0) {
    lastPulseStartedAt = millis();
    setOutputs(true);
  }
}

void handleSerialCommand(char *command) {
  if (strcmp(command, "S") == 0) {
    stopAlert(true);
    Serial.println("ACK:S");
    return;
  }

  if (strncmp(command, "P:", 2) != 0) {
    Serial.println("ERR:COMMAND");
    return;
  }

  char *end = nullptr;
  const float probability = strtof(command + 2, &end);
  if (end == command + 2 || *end != '\0' || !isfinite(probability) ||
      probability < 0.0 || probability > 1.0) {
    Serial.println("ERR:PROBABILITY");
    return;
  }

  applyProbability(probability);
  Serial.print("ACK:P:");
  Serial.println(currentProbability, 6);
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char incoming = static_cast<char>(Serial.read());
    if (incoming == '\r') continue;

    if (incoming == '\n') {
      serialBuffer[serialLength] = '\0';
      if (serialLength > 0) handleSerialCommand(serialBuffer);
      serialLength = 0;
      continue;
    }

    if (serialLength < sizeof(serialBuffer) - 1) {
      serialBuffer[serialLength++] = incoming;
    } else {
      serialLength = 0;
      Serial.println("ERR:TOO_LONG");
    }
  }
}

void updateButton() {
  const bool reading = digitalRead(BUTTON_PIN);
  const unsigned long now = millis();

  if (reading != lastButtonReading) {
    lastButtonReading = reading;
    buttonChangedAt = now;
  }

  if (now - buttonChangedAt < BUTTON_DEBOUNCE_MS || reading == stableButtonState) return;

  stableButtonState = reading;
  if (stableButtonState == LOW) {
    stopAlert(true);
    Serial.println("ACK:BUTTON");
  }
}

void updateAlert() {
  if (alertAcknowledged || alertIntervalMs == 0) {
    if (pulseOn) setOutputs(false);
    return;
  }

  const unsigned long now = millis();
  const unsigned long elapsed = now - lastPulseStartedAt;

  if (pulseOn && elapsed >= PULSE_DURATION_MS) {
    setOutputs(false);
  }

  if (elapsed >= alertIntervalMs) {
    lastPulseStartedAt = now;
    setOutputs(true);
  }
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(LED_PIN, OUTPUT);
  // Wire the button between pin 9 and GND; the internal pull-up removes the
  // need for an external resistor and makes a press read LOW.
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  setOutputs(false);

  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  readSerialCommands();
  updateButton();
  updateAlert();
}
