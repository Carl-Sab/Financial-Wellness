import { useArduino } from "../hooks/useArduino";

export default function ArduinoConnection({ deliveryStatus, probability }) {
  const { supported, status, error, connect, disconnect } = useArduino();

  async function handleConnect() {
    try {
      await connect();
    } catch {
      // ArduinoContext owns the user-facing error message.
    }
  }

  const connected = status === "connected";
  const busy = status === "connecting";
  const statusLabel =
    status === "unsupported"
      ? "Unsupported browser"
      : connected
        ? "Connected"
        : busy
          ? "Connecting"
          : "Not connected";
  const deliveryMessage = (() => {
    if (deliveryStatus === "sending") return "Sending the probability...";
    if (deliveryStatus === "error") return "The probability was not delivered.";
    if (deliveryStatus !== "sent") return null;
    if (probability < 0.33) return "Probability sent. The hardware alert will stay off.";
    return "Probability sent. Press the hardware button to stop the alert.";
  })();

  return (
    <section className="arduino-alert" aria-live="polite">
      <div>
        <p className="arduino-alert__title">Arduino alert</p>
        <p className="arduino-alert__description">
          {supported
            ? "Connect the board once; each new prediction is sent automatically."
            : "Web Serial requires Chrome or Edge on desktop."}
        </p>
      </div>

      {supported && (
        <button
          type="button"
          className="arduino-alert__button"
          onClick={connected ? disconnect : handleConnect}
          disabled={busy}
        >
          {busy ? "Connecting..." : connected ? "Disconnect" : "Connect Arduino"}
        </button>
      )}

      <p className={`arduino-alert__status arduino-alert__status--${status}`}>
        {statusLabel}
      </p>
      {error && <p className="arduino-alert__message arduino-alert__message--error">{error}</p>}
      {deliveryMessage && (
        <p
          className={`arduino-alert__message ${
            deliveryStatus === "error" ? "arduino-alert__message--error" : ""
          }`}
        >
          {deliveryMessage}
        </p>
      )}
    </section>
  );
}
