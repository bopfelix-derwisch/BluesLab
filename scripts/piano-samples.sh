#!/usr/bin/env bash
# Haalt de Salamander Grand Piano-samples (Alexander Holm, CC-BY 3.0) via Tone.js op
# en maakt ze klein voor web/piano/<midi>.mp3: mono, stilte vooraf eraf, 2 s met fade-out.
set -euo pipefail
cd "$(dirname "$0")/.."
BRON=https://tonejs.github.io/audio/salamander
NAMEN=(C2 Ds2 Fs2 A2 C3 Ds3 Fs3 A3 C4 Ds4 Fs4 A4 C5 Ds5 Fs5)  # MIDI 36, 39, ..., 78
WERK=$(mktemp -d)
trap 'rm -rf "$WERK"' EXIT
mkdir -p web/piano
midi=36
for n in "${NAMEN[@]}"; do
  curl -fsSL "$BRON/$n.mp3" -o "$WERK/$n.mp3"
  ffmpeg -loglevel error -y -i "$WERK/$n.mp3" -ac 1 \
    -af "silenceremove=start_periods=1:start_threshold=-50dB,atrim=0:2,afade=t=out:st=1.7:d=0.3" \
    -b:a 96k "web/piano/$midi.mp3"
  midi=$((midi + 3))
done
ls -l web/piano
