# Arduino overspending alert

Upload `overspending_alert/overspending_alert.ino` to an Arduino-compatible
board, then open the Financial Wellness app in desktop Chrome or Edge.

## Wiring

| Part | Arduino connection |
| --- | --- |
| Buzzer signal | Digital pin 2 |
| LED anode | Digital pin 8 through a 220-330 ohm resistor |
| LED cathode | GND |
| Push button | Between digital pin 9 and GND |

The button uses `INPUT_PULLUP`, so no external pull-up resistor is needed. The
firmware defaults to a passive buzzer using `tone()` at 2 kHz. Set
`PASSIVE_BUZZER` to `false` in the sketch when using an active buzzer module.
If a buzzer or lamp draws more current than an Arduino pin safely supplies,
drive it through a transistor or suitable driver instead of connecting it
directly.

## Behavior

| Probability | Behavior |
| --- | --- |
| Less than 0.33 | LED and buzzer remain off |
| 0.33 through 0.66 | A synchronized 100 ms LED/buzzer pulse every 1000 ms |
| Greater than 0.66 | A synchronized 100 ms LED/buzzer pulse every 200 ms |

Pressing the button immediately stops and acknowledges the current alert. A
new probability received later starts a new alert when its band requires one.

## Browser connection

1. Connect the uploaded board over USB.
2. Open the app using `http://localhost:5173` in desktop Chrome or Edge.
3. Go to **Check-in** and select **Connect Arduino**.
4. Choose the Arduino serial port in the browser prompt.
5. Complete a check-in. Once the probability appears, the app sends it to the
   board automatically at 115200 baud.

Web Serial requires a secure context. `localhost` is accepted for local
development; a deployed site must use HTTPS.

The newline-delimited protocol is deliberately small:

- `P:0.742500` applies a probability between 0 and 1.
- `S` stops the current alert, including when the user disconnects through the
  web UI.
