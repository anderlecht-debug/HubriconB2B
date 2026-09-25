"""FakeDB plus the two things the unit-economics code asks of PostgREST that
the loop modules never did: paged reads (`.range`), and a table that is not
there yet (the migration not applied), which fails at execute as the real
client does."""

from __future__ import annotations

from fakedb import FakeDB, _Q


class _PagedQ(_Q):
    def range(self, start, end):
        self._range = (start, end)
        return self

    def execute(self):
        if self.name in self.db.missing:
            raise RuntimeError(f'relation "public.{self.name}" does not exist')
        res = super().execute()
        window = getattr(self, "_range", None)
        if window is not None and self.op == "select":
            res.data = res.data[window[0]: window[1] + 1]
        return res


class EconDB(FakeDB):
    def __init__(self, missing=(), **tables):
        super().__init__(**tables)
        self.missing = set(missing)

    def table(self, name):
        return _PagedQ(self, name)
