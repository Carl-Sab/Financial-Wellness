import { useContext } from "react";
import ArduinoContext from "../context/ArduinoContextValue";

export function useArduino() {
  const context = useContext(ArduinoContext);
  if (!context) throw new Error("useArduino must be used within an ArduinoProvider");
  return context;
}
