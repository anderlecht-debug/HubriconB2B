// A take's pace, measured in the browser the moment it is stopped (docs/content/LEARNING_DESIGN.md:
// viewers stay with a speaker who is clear and alive, about 120 to 200 words a minute). The voiced span
// runs from the first to the last 20 ms window above a tenth of the take's loudest window, so the
// silence before and after a take does not count against it.
export const WPM = [120, 200];

export function pace(samples, sampleRate, words) {
  const win = Math.max(1, Math.round(sampleRate * 0.02));
  const rms = [];
  for (let i = 0; i + win <= samples.length; i += win) {
    let s = 0;
    for (let j = i; j < i + win; j++) s += samples[j] * samples[j];
    rms.push(Math.sqrt(s / win));
  }
  const floor = Math.max(0.004, Math.max(0, ...rms) * 0.1);
  const first = rms.findIndex((r) => r > floor), last = rms.findLastIndex((r) => r > floor);
  if (first < 0 || !words) return { wpm: 0, seconds: 0, verdict: "silent", note: "No voice in this take." };
  const seconds = ((last - first + 1) * win) / sampleRate;
  const wpm = Math.round(words / (seconds / 60));
  const verdict = wpm < WPM[0] ? "slow" : wpm > WPM[1] ? "fast" : "good";
  const note = verdict === "good" ? `${wpm} words a minute · a clear pace`
    : verdict === "fast" ? `${wpm} words a minute: a little fast. Read it again, and let the figures land.`
    : `${wpm} words a minute: a little slow. Read it again with more drive.`;
  return { wpm, seconds: Math.round(seconds * 10) / 10, verdict, note };
}
