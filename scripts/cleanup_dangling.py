"""Delete tracks that KiCad's DRC reports as dangling (autorouter leftovers).

    $KP scripts/cleanup_dangling.py eugeo.kicad_pcb
Repeats DRC until no dangling track remains.
"""
import json
import os
import subprocess
import sys
import tempfile

import pcbnew

CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")


def dangling_uuids(path):
    out = os.path.join(tempfile.mkdtemp(), "drc.json")
    subprocess.run([CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", out, path],
                   check=True, capture_output=True)
    rep = json.load(open(out))
    ids = set()
    for v in rep.get("violations", []):
        if v["type"] in ("track_dangling", "via_dangling"):
            ids.add(v["items"][0]["uuid"])
    return ids


def main(path):
    total = 0
    while True:
        ids = dangling_uuids(path)
        if not ids:
            break
        board = pcbnew.LoadBoard(path)
        dead = [t for t in board.GetTracks() if t.m_Uuid.AsString() in ids]
        if not dead:
            break
        for t in dead:
            board.Delete(t)
        pcbnew.SaveBoard(path, board)
        total += len(dead)
    print("removed", total, "dangling tracks/vias")


if __name__ == "__main__":
    main(sys.argv[1])
