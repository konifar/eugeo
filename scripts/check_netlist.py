#!/usr/bin/env python3
"""Compare the schematic netlist (kicad-cli export) with design.py."""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(__file__))
import design, sexpr
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.environ.get("KICAD_CLI", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
out = os.path.join(tempfile.mkdtemp(), "n.net")
subprocess.run([CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out,
                os.path.join(ROOT, design.PROJECT + ".kicad_sch")], check=True, capture_output=True)
root = sexpr.parse(open(out).read())
got = {}
for net in root.child("nets").children("net"):
    name = net.child("name").items[1].lstrip("/")
    for node in net.children("node"):
        got[(node.child("ref").items[1], node.child("pin").items[1])] = name
want = {}
for p in design.parts():
    for pin, net in p["pins"].items():
        want[(p["ref"], pin)] = net
bad = 0
for k, v in sorted(want.items()):
    g = got.get(k)
    if v is None:
        if g is not None and not g.startswith("unconnected"):
            print("expected NC", k, g); bad += 1
    elif g != v:
        print("MISMATCH", k, "want", v, "got", g); bad += 1
extra = set(r for r, _ in got) - set(r for r, _ in want)
print("extra refs:", sorted(extra))
print("mismatches:", bad)
sys.exit(1 if bad else 0)
