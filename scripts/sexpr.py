"""Minimal S-expression reader for KiCad files (keeps source spans for verbatim copy)."""
import re

_TOKEN = re.compile(r'\s*(\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+)')


def parse(text):
    """Parse into nested lists. Each list node is (items, start, end) -> returned as Node."""
    pos = 0
    stack = [Node(None, 0)]
    while True:
        m = _TOKEN.match(text, pos)
        if not m:
            break
        tok = m.group(1)
        start = m.start(1)
        pos = m.end()
        if tok == "(":
            n = Node(stack[-1], start)
            stack[-1].items.append(n)
            stack.append(n)
        elif tok == ")":
            n = stack.pop()
            n.end = pos
        else:
            if tok.startswith('"'):
                tok = Str(bytes(tok[1:-1], "utf-8").decode("unicode_escape") if "\\" in tok else tok[1:-1])
            stack[-1].items.append(tok)
    return stack[0].items[0]


class Str(str):
    pass


class Node:
    def __init__(self, parent, start):
        self.parent = parent
        self.items = []
        self.start = start
        self.end = None

    @property
    def tag(self):
        return self.items[0] if self.items else None

    def children(self, tag=None):
        return [i for i in self.items if isinstance(i, Node) and (tag is None or i.tag == tag)]

    def child(self, tag):
        for i in self.items:
            if isinstance(i, Node) and i.tag == tag:
                return i
        return None

    def walk(self):
        yield self
        for c in self.children():
            yield from c.walk()
