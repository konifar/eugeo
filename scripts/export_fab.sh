#!/bin/sh
# Export gerbers + drill files (JLCPCB-compatible) for the main PCB and the plates.
set -eu
cd "$(dirname "$0")/.."
CLI=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
LAYERS=F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts
fab() { # $1 = board file, $2 = output name
  out=gerbers/$2
  rm -rf "$out" "gerbers/$2.zip"
  mkdir -p "$out"
  "$CLI" pcb export gerbers --layers "$LAYERS" --subtract-soldermask --no-x2 -o "$out/" "$1" >/dev/null
  "$CLI" pcb export drill --format excellon --excellon-separate-th --generate-map --map-format gerberx2 -o "$out/" "$1" >/dev/null
  (cd "$out" && zip -q -r "../$2.zip" .)
  echo "gerbers/$2.zip"
}
fab eugeo.kicad_pcb eugeo
fab plates/eugeo-plate.kicad_pcb eugeo-plate
fab plates/eugeo-bottom.kicad_pcb eugeo-bottom
fab plates/eugeo-cover.kicad_pcb eugeo-cover

# DXF for laser cutters (plates, foams) and 1:1 PDF templates for cutting foam by hand
dxf() { "$CLI" pcb export dxf --mode-single --layers Edge.Cuts --output-units mm -o "${1%.kicad_pcb}.dxf" "$1" >/dev/null && echo "${1%.kicad_pcb}.dxf"; }
for b in plates/eugeo-plate plates/eugeo-cover plates/eugeo-bottom foam/eugeo-plate-foam foam/eugeo-case-foam-left foam/eugeo-case-foam-right foam/eugeo-gasket-pad; do
  dxf "$b.kicad_pcb"
done
for b in foam/eugeo-plate-foam foam/eugeo-case-foam-left foam/eugeo-case-foam-right foam/eugeo-gasket-pad; do
  "$CLI" pcb export pdf --layers Edge.Cuts,Dwgs.User --black-and-white -o "$b-1to1.pdf" "$b.kicad_pcb" >/dev/null && echo "$b-1to1.pdf"
done
