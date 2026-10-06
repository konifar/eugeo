#!/bin/sh
# Full pipeline: schematic -> PCB placement + key routing -> autoroute -> cleanup -> GND fill -> DRC
#   FREEROUTING_JAR=/path/to/freerouting-2.1.0.jar scripts/build_all.sh
set -eu
cd "$(dirname "$0")/.."
KP=${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}
CLI=${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}
quiet() { grep -v -E 'assert|memory leak|duplicate image handler' || true; }
python3 scripts/gen_schematic.py
python3 scripts/check_netlist.py | tail -1
"$KP" scripts/build_pcb.py 2>&1 | quiet
scripts/route.sh "${ROUTE_TIMEOUT:-00:03:00}" 2>&1 | quiet
"$KP" scripts/cleanup_dangling.py eugeo.kicad_pcb 2>&1 | quiet
"$KP" scripts/fill_zones.py eugeo.kicad_pcb 2>&1 | quiet
"$CLI" pcb drc --severity-all --schematic-parity -o drc.rpt eugeo.kicad_pcb >/dev/null
if grep -q -E '^\[' drc.rpt; then grep -E '^\[' drc.rpt | sort | uniq -c; exit 1; fi
echo "DRC clean"
