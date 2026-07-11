
export const lerp = (start, end, factor) => {
  return start + (end - start) * factor;
};

export const smoothEma = (current, previous, alpha = 0.2) => {
  if (previous === null || previous === undefined) return current;
  return (current * alpha) + (previous * (1 - alpha));
};

export const mapRange = (value, inMin, inMax, outMin, outMax) => {
  return ((value - inMin) * (outMax - outMin)) / (inMax - inMin) + outMin;
};