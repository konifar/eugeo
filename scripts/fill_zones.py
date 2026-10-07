"""Add a GND pour on B.Cu (and with --top, on F.Cu too) if missing, and fill all zones.

The top pour is added only after autorouting (build_all.sh), so Freerouting sees the
top layer free; it ties the GND pads of the centre parts together where back-side
tracks cut the bottom pour into pieces.
"""
import sys

import pcbnew


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main(path, top=False):
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import design
    board = pcbnew.LoadBoard(path)
    zones = [board.GetArea(i) for i in range(board.GetAreaCount())]
    have = {z.GetLayer() for z in zones if z.GetNetname() == "GND"}
    for layer in (pcbnew.B_Cu, pcbnew.F_Cu) if top else (pcbnew.B_Cu,):
        if layer in have:
            continue
        x1, y1, x2, y2 = design.EDGE
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(board.GetNetInfo().GetNetItem("GND").GetNetCode())
        z.SetLocalClearance(pcbnew.FromMM(0.3))
        z.SetMinThickness(pcbnew.FromMM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        outline = z.Outline()
        outline.NewOutline()
        for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
            outline.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("zones filled")


if __name__ == "__main__":
    main(sys.argv[1], "--top" in sys.argv[2:])
