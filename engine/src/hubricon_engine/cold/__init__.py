"""The cold engine: a defensible finding about a company that has never heard
of us, rendered as a page and an email.

The warm engine turns a client's private exports into a dollar figure. This one
runs the same discipline over *public* data, where every input is an estimate
and the output has to carry that uncertainty honestly or it is worthless — one
wrong number sent to a $5M seller costs more than the channel earns, and this
ICP talks to each other constantly.

    sources/     one module per provider, all behind the same Protocol
    snapshot     provider payloads → one typed ProspectSnapshot
    priors       the published rate cards a finding is priced from
    findings     snapshot → every finding it supports, each with a range
    select       findings → the one worth leading with, or None
    copy         a Finding → subject, body, script. Numbers are templated.
    page         a Finding → the teardown page the email links to
    compliance   can_contact(): the only path to a send
    run          the orchestration the CLI drives

Sending nothing is an acceptable output, and roughly half of the prospects that
reach here should produce one.
"""

ENGINE_VERSION = "cold-1"
