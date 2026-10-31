#!/usr/bin/env bash
# Haalt het akoestische drumstel uit Google Chrome Labs web-audio-samples (Apache-2.0) op
# en maakt het klein voor web/drums/<naam>.mp3: mono, stilte vooraf eraf, max 1 s met fade-out.
set -euo pipefail
cd "$(dirname "$0")/.."
BRON=https://raw.githubusercontent.com/GoogleChromeLabs/web-audio-samples/main
WERK=$(mktemp -d)
trap 'rm -rf "$WERK"' EXIT
mkdir -p web/drums
for n in kick snare hihat; do
  curl -fsSL "$BRON/src/sounds/drum-samples/acoustic-kit/$n.wav" -o "$WERK/$n.wav"
  ffmpeg -loglevel error -y -i "$WERK/$n.wav" -ac 1 -map_metadata -1 \
    -af "silenceremove=start_periods=1:start_threshold=-50dB,atrim=0:1,afade=t=out:st=0.8:d=0.2" \
    -b:a 96k "web/drums/$n.mp3"
done
curl -fsSL "$BRON/LICENSE" -o web/drums/LICENSE-Apache-2.0.txt
ls -l web/drums
