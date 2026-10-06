#!/bin/sh
# Autoroute the centre of eugeo.kicad_pcb with Freerouting (key area is pre-routed and locked).
#   FREEROUTING_JAR=/path/to/freerouting-2.1.0.jar scripts/route.sh [timeout hh:mm:ss]
set -eu
cd "$(dirname "$0")/.."
KP=${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}
JAR=${FREEROUTING_JAR:?set FREEROUTING_JAR to freerouting-2.1.0.jar}
TIMEOUT=${1:-00:03:00}
WORK=$(mktemp -d)
"$KP" scripts/export_dsn.py eugeo.kicad_pcb "$WORK/eugeo.dsn"
java -Djava.awt.headless=true -jar "$JAR" -de "$WORK/eugeo.dsn" -do "$WORK/eugeo.ses" \
  --gui.enabled=false --router.job_timeout="$TIMEOUT" > "$WORK/freerouting.log" 2>&1
grep -o '"incomplete_count": [0-9]*' "$WORK/freerouting.log" | tail -1
"$KP" scripts/import_ses.py eugeo.kicad_pcb "$WORK/eugeo.ses"
echo "log: $WORK/freerouting.log"
