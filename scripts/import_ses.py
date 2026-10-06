import sys, pcbnew
b = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ImportSpecctraSES(b, sys.argv[2])
print("import", ok)
pcbnew.SaveBoard(sys.argv[3] if len(sys.argv) > 3 else sys.argv[1], b)
