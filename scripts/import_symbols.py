#!/usr/bin/env python3
"""Copy the symbols eugeo needs from the KiCad standard library into the project.

    python3 scripts/import_symbols.py

Derived symbols ("extends") are flattened, everything is renamed to eugeo:<name>,
and both scripts/lib_symbols.sexpr (embedded in the schematic) and
symbols/eugeo.kicad_sym (project library) are rewritten. Symbols that came from
Lumberjack and are already in lib_symbols.sexpr are kept.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import sexpr  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STD = os.environ.get("KICAD_SYMBOL_DIR", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols")

# eugeo name: (library, symbol)
WANTED = {
    "RP2040": ("MCU_RaspberryPi", "RP2040"),
    "W25Q16JVSS": ("Memory_Flash", "W25Q16JVSS"),
    "MCP1700-3302E_TO": ("Regulator_Linear", "MCP1700x-330xxTO"),
    "USBLC6-2SC6": ("Power_Protection", "USBLC6-2SC6"),
    "+3V3": ("power", "+3V3"),
}
DROP = {"eugeo:ATmega328P-PU", "eugeo:D_Zener_Small_ALT", "eugeo:Conn_02x03_Odd_Even", "eugeo:Conn_01x04_Pin"}


def find(lib, name):
    text = open(os.path.join(STD, lib + ".kicad_sym")).read()
    root = sexpr.parse(text)
    for s in root.children("symbol"):
        if s.items[1] == name:
            return text, s
    raise SystemExit(f"{lib}:{name} not found")


def flatten(lib, name):
    """Symbol text with 'extends' resolved, still named <name>."""
    text, node = find(lib, name)
    ext = node.child("extends")
    if ext is None:
        return text[node.start:node.end]
    base_name = ext.items[1]
    btext, bnode = find(lib, base_name)
    base = btext[bnode.start:bnode.end]
    # take the derived symbol's properties, the base symbol's graphics and pins
    props = "".join("\n\t\t" + text[p.start:p.end] for p in node.children("property"))
    body = "".join("\n\t\t" + btext[c.start:c.end] for c in bnode.children()
                   if c.tag not in ("property", "extends"))
    flags = "".join("\n\t\t" + btext[c.start:c.end] for c in bnode.children()
                    if c.tag in ("pin_names", "pin_numbers", "exclude_from_sim", "in_bom", "on_board"))
    body = body.replace(f'(symbol "{base_name}_', f'(symbol "{name}_')
    # flags were already included in body; only properties come from the derived symbol
    del flags
    return f'(symbol "{name}"{props}{body}\n\t)'


def rename(sym_text, old, new):
    sym_text = sym_text.replace(f'(symbol "{old}"', f'(symbol "{new}"', 1)
    return re.sub(r'\(symbol "' + re.escape(old) + r'_(\d+_\d+)"', lambda m: f'(symbol "{new}_{m.group(1)}"', sym_text)


def main():
    path = os.path.join(HERE, "lib_symbols.sexpr")
    text = open(path).read()
    root = sexpr.parse(text)
    kept = {s.items[1]: text[s.start:s.end] for s in root.children("symbol") if s.items[1] not in DROP}
    for new, (lib, name) in WANTED.items():
        sym = flatten(lib, name)
        sym = rename(sym, name, new)                    # sub-units use the bare name
        sym = sym.replace(f'(symbol "{new}"', f'(symbol "eugeo:{new}"', 1)
        kept[f"eugeo:{new}"] = sym
    open(path, "w").write("(lib_symbols\n" + "\n".join(kept[k] for k in sorted(kept)) + "\n)\n")
    lib = []
    for full, sym in sorted(kept.items()):
        bare = full.split(":", 1)[1]
        lib.append("  " + sym.replace(f'(symbol "{full}"', f'(symbol "{bare}"', 1))
    open(os.path.join(ROOT, "symbols", "eugeo.kicad_sym"), "w").write(
        "(kicad_symbol_lib (version 20241209) (generator kicad_symbol_editor)\n" + "\n".join(lib) + "\n)\n")
    print("symbols:", ", ".join(sorted(kept)))


if __name__ == "__main__":
    main()
