"""An in-memory stand-in for the Supabase client, wide enough for the loop
modules (proof, referral, speed, loop, calibration) and nothing wider.

Every query runs against plain lists of dicts; inserts mint an id when the
row has none; upserts honour on_conflict. Nothing here touches the network,
which the session-wide conftest would refuse anyway."""

from __future__ import annotations

import re


class _R:
    def __init__(self, data):
        self.data = data
        self.count = len(data) if isinstance(data, list) else None


class _Not:
    def __init__(self, q):
        self.q = q

    def is_(self, col, _val):
        self.q.filters.append(lambda r: r.get(col) is not None)
        return self.q


class _Q:
    def __init__(self, db, name):
        self.db, self.name = db, name
        self.filters = []
        self.op = "select"
        self.rows = None
        self.patch = None
        self.on_conflict = None
        self._order = None
        self._limit = None
        self.not_ = _Not(self)

    # -- verbs
    def select(self, *_a, **_k):
        return self

    def insert(self, rows):
        self.op, self.rows = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def update(self, patch):
        self.op, self.patch = "update", patch
        return self

    def upsert(self, rows, on_conflict=None, **_k):
        self.op, self.rows = "upsert", rows if isinstance(rows, list) else [rows]
        self.on_conflict = [c.strip() for c in (on_conflict or "id").split(",")]
        return self

    # -- filters
    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        vals = list(vals)
        self.filters.append(lambda r: r.get(col) in vals)
        return self

    def is_(self, col, val):
        self.filters.append(lambda r: r.get(col) is None if val == "null" else r.get(col) == val)
        return self

    def gte(self, col, val):
        self.filters.append(lambda r: r.get(col) is not None and str(r.get(col)) >= str(val))
        return self

    def or_(self, expr):
        clauses = []
        for part in expr.split(","):
            col, op, needle = part.split(".", 2)
            if op == "ilike":
                pat = re.escape(needle).replace("%", ".*")
                clauses.append((col, re.compile(f"^{pat}$", re.I)))
        self.filters.append(lambda r: any(rx.search(str(r.get(c) or "")) for c, rx in clauses))
        return self

    def order(self, col, desc=False):
        self._order = (col, desc)
        return self

    def limit(self, n):
        self._limit = n
        return self

    # -- run
    def _match(self, r):
        return all(f(r) for f in self.filters)

    def execute(self):
        store = self.db.store.setdefault(self.name, [])
        if self.op == "insert":
            for r in self.rows:
                r = dict(r)
                r.setdefault("id", f"{self.name}-{len(store) + 1}")
                store.append(r)
            self.db.writes.append((self.name, "insert", list(self.rows)))
            return _R(list(store[-len(self.rows):]))
        if self.op == "upsert":
            out = []
            for r in self.rows:
                r = dict(r)
                hit = next((x for x in store if all(x.get(c) == r.get(c) for c in self.on_conflict)), None)
                if hit:
                    hit.update(r)
                    out.append(hit)
                else:
                    r.setdefault("id", f"{self.name}-{len(store) + 1}")
                    store.append(r)
                    out.append(r)
            self.db.writes.append((self.name, "upsert", list(self.rows)))
            return _R(out)
        rows = [r for r in store if self._match(r)]
        if self.op == "update":
            for r in rows:
                r.update(self.patch)
            self.db.writes.append((self.name, "update", dict(self.patch), [r.get("id") for r in rows]))
            return _R(rows)
        if self._order:
            col, desc = self._order
            rows = sorted(rows, key=lambda r: str(r.get(col) or ""), reverse=desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        return _R([dict(r) for r in rows])


class _Rpc:
    def __init__(self, fn, params):
        self.fn, self.params = fn, params

    def execute(self):
        if self.fn is None:
            raise RuntimeError("no such rpc")
        return _R(self.fn(**(self.params or {})))


class FakeDB:
    def __init__(self, **tables):
        self.store = {k: [dict(r) for r in v] for k, v in tables.items()}
        self.writes = []
        self.rpcs = {}

    def table(self, name):
        return _Q(self, name)

    def rpc(self, name, params=None):
        return _Rpc(self.rpcs.get(name), params)

    def rows(self, name):
        return self.store.get(name, [])
