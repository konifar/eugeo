"""Add a GND pour on B.Cu (if missing) and fill all zones."""
import sys

import pcbnew


def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main(path):
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    import design
    board = pcbnew.LoadBoard(path)
    if not any(z.GetNetname() == "GND" for z in board.Zones()):
        x1, y1, x2, y2 = design.EDGE
        z = pcbnew.ZONE(board)
        z.SetLayer(pcbnew.B_Cu)
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
    main(sys.argv[1])
