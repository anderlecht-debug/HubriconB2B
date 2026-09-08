"""No test reaches the network, whatever is on this machine's disk.

The harvest's fetchers are real HTTP clients, and two of its entry points
build one themselves rather than taking an injected double: `run.run_all`'s
Shopify pass and `shopify.load_handles`, which reads the cached store listing
from ~/.hubricon and crawls whatever it finds there. On 2026-09-04 a live
`hubricon harvest shopify` wrote that cache for the first time, and the next
`pytest` run quietly started fetching real stores through headless Chrome —
the suite went from two seconds to hanging, and the reason was invisible.

So the transports themselves are disarmed for the whole session: any test
that constructs a real Fetcher and calls it fails loudly with the URL it
tried, instead of going out to the internet. Tests inject their own doubles
(FakeFetcher) and are unaffected.
"""

import pytest

from hubricon_engine.harvest import enrich as enrichmod
from hubricon_engine.harvest import fetch as fetchmod
from hubricon_engine.sourcing import discover as discovermod
from hubricon_engine.sourcing import sheet as sheetmod


class NetworkAccessInTest(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def refuse(target, *args, **kwargs):
        raise NetworkAccessInTest(
            f"a test tried to reach {target!r}. Inject a fake fetcher, or pass "
            "shopify=False / a cdx_file so the call never builds a real one."
        )

    # Plain HTTP refuses, and Chrome's real runner is Popen, so both transports
    # land here. chrome_binary and _chrome_transport are left intact: the
    # transport takes an injected runner and is unit-tested without a browser.
    monkeypatch.setattr(fetchmod, "_urllib_transport", lambda jar: refuse)
    monkeypatch.setattr(fetchmod.subprocess, "Popen", refuse)
    # DNS: the enrichment's MX check shells out to dig
    monkeypatch.setattr(enrichmod.subprocess, "run", refuse)
    monkeypatch.setattr(enrichmod.socket, "gethostbyname", refuse)
    # Sourcing has three more ways out: its own dig for the Shopify DNS
    # fingerprint, the Tranco download, and the Google Sheet webhook. Each
    # takes an injectable seam (resolver=, opener=), and these make forgetting
    # to pass one an error rather than a live request.
    monkeypatch.setattr(discovermod.subprocess, "run", refuse)
    monkeypatch.setattr(discovermod, "_open", refuse)
    monkeypatch.setattr(sheetmod.urllib.request, "urlopen", refuse)
