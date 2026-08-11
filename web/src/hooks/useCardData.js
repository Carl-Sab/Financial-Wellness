import { useEffect, useState } from "react";

// Each card/page owns its own loading/error/data cycle — one failing must
// never block or blank another. loadFn is expected to be a stable
// module-level function (no props/closures to worry about), so `attempt`
// alone is enough to drive re-fetching on retry.
export function useCardData(loadFn) {
  const [status, setStatus] = useState("loading"); // loading | error | success
  const [data, setData] = useState(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    loadFn()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setStatus("success");
      })
      .catch(() => {
        if (cancelled) return;
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);

  return { status, data, retry: () => setAttempt((a) => a + 1) };
}
