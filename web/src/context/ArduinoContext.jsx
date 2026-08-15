import { useCallback, useEffect, useRef, useState } from "react";
import ArduinoContext from "./ArduinoContextValue";

const BAUD_RATE = 115200;
// Most Arduino boards reset when a serial connection opens. Waiting before
// reporting the port as ready prevents the first probability from being lost
// while the bootloader is still running.
const BOARD_STARTUP_DELAY_MS = 1500;

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function ArduinoProvider({ children }) {
  const supported = typeof navigator !== "undefined" && "serial" in navigator;
  const [status, setStatus] = useState(supported ? "disconnected" : "unsupported");
  const [error, setError] = useState("");
  const [connectionId, setConnectionId] = useState(0);
  const portRef = useRef(null);
  const writeQueueRef = useRef(Promise.resolve());

  const queueWrite = useCallback(async (message) => {
    const write = async () => {
      const port = portRef.current;
      if (!port?.writable) throw new Error("Arduino is not connected");

      const writer = port.writable.getWriter();
      try {
        await writer.write(new TextEncoder().encode(message));
      } finally {
        writer.releaseLock();
      }
    };

    const operation = writeQueueRef.current.then(write, write);
    // Keep the queue usable after one failed write while still returning the
    // real operation to this caller so it can display the error.
    writeQueueRef.current = operation.catch(() => {});
    return operation;
  }, []);

  const connect = useCallback(async () => {
    if (!supported) throw new Error("Web Serial is not supported in this browser");
    if (portRef.current) return;

    setStatus("connecting");
    setError("");
    let port = null;
    try {
      port = await navigator.serial.requestPort();
      await port.open({ baudRate: BAUD_RATE });
      portRef.current = port;
      await wait(BOARD_STARTUP_DELAY_MS);
      if (portRef.current !== port || !port.writable) {
        throw new Error("Arduino disconnected while starting");
      }
      setConnectionId((value) => value + 1);
      setStatus("connected");
    } catch (connectionError) {
      if (port?.readable || port?.writable) {
        await port.close().catch(() => {});
      }
      portRef.current = null;
      const message =
        connectionError?.name === "NotFoundError"
          ? "No Arduino was selected."
          : "Could not connect to the Arduino.";
      setError(message);
      setStatus("disconnected");
      throw connectionError;
    }
  }, [supported]);

  const sendProbability = useCallback(
    async (probability) => {
      const numeric = Number(probability);
      if (!Number.isFinite(numeric) || numeric < 0 || numeric > 1) {
        throw new Error("Overspending probability must be between 0 and 1");
      }

      try {
        // Newline-delimited text keeps the browser/Arduino protocol easy to
        // inspect in both DevTools and Arduino's Serial Monitor.
        await queueWrite(`P:${numeric.toFixed(6)}\n`);
        setError("");
      } catch (writeError) {
        setError("The probability could not be sent to the Arduino.");
        throw writeError;
      }
    },
    [queueWrite],
  );

  const disconnect = useCallback(async () => {
    const port = portRef.current;
    if (!port) return;

    // Stop an active alert before releasing the port. If the cable is pulled
    // unexpectedly, the physical button remains the hardware-side fail-safe.
    await queueWrite("S\n").catch(() => {});
    await writeQueueRef.current.catch(() => {});
    portRef.current = null;
    await port.close().catch(() => {});
    setStatus(supported ? "disconnected" : "unsupported");
    setError("");
  }, [queueWrite, supported]);

  useEffect(() => {
    if (!supported) return undefined;

    function handleDisconnect(event) {
      if (event.target !== portRef.current) return;
      portRef.current = null;
      setStatus("disconnected");
      setError("The Arduino was disconnected.");
    }

    navigator.serial.addEventListener("disconnect", handleDisconnect);
    return () => navigator.serial.removeEventListener("disconnect", handleDisconnect);
  }, [supported]);

  const value = {
    supported,
    status,
    error,
    connectionId,
    connect,
    disconnect,
    sendProbability,
  };

  return <ArduinoContext.Provider value={value}>{children}</ArduinoContext.Provider>;
}
