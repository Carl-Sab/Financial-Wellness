/**
 * A stylized multi-cycle ECG trace (P wave, sharp QRS spike, T wave,
 * repeated) as an SVG path `d` string. Built procedurally rather than
 * hand-authored so the cycle count/proportions stay easy to tune.
 */
export function buildEcgPath({ width = 640, height = 64, cycles = 3 } = {}) {
  const mid = height / 2;
  const cycleWidth = width / cycles;
  const points = [[0, mid]];

  for (let i = 0; i < cycles; i += 1) {
    const start = i * cycleWidth;
    points.push(
      [start + cycleWidth * 0.08, mid],
      [start + cycleWidth * 0.14, mid - height * 0.18],
      [start + cycleWidth * 0.2, mid],
      [start + cycleWidth * 0.34, mid],
      [start + cycleWidth * 0.38, mid + height * 0.1],
      [start + cycleWidth * 0.42, mid - height * 0.85],
      [start + cycleWidth * 0.46, mid + height * 0.55],
      [start + cycleWidth * 0.5, mid],
      [start + cycleWidth * 0.62, mid],
      [start + cycleWidth * 0.68, mid - height * 0.22],
      [start + cycleWidth * 0.76, mid],
      [start + cycleWidth, mid],
    );
  }

  return points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
}
