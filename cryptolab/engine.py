"""Replay bounded validator entry and exit queues with FIFO churn capacity, minimum active count and duplicate guards."""

from .common import (
    number,
    integer,
    identity,
    records,
    chronology,
    allocate,
    result,
    validate_document,
)
from decimal import Decimal


def _analyze(d):
    active = set(identity(v) for v in d["active"])
    minimum = integer(d["minimum_active"])
    activation_limit = integer(d["activation_limit"])
    exit_limit = integer(d["exit_limit"])
    entries = []
    exits = []
    trace = []
    seen_epochs = set()
    if len(active) != len(d["active"]) or len(active) < minimum:
        raise ValueError("invalid initial validator set")
    for e in chronology(d["events"]):
        kind = e["kind"]
        epoch = e["timestamp"]
        if kind == "activate_request":
            v = identity(e["validator"])
            if v in active or v in entries or v in exits:
                raise ValueError("duplicate activation")
            entries.append(v)
        elif kind == "exit_request":
            v = identity(e["validator"])
            if v not in active or v in exits:
                raise ValueError("invalid exit request")
            exits.append(v)
        elif kind == "process":
            if epoch in seen_epochs:
                raise ValueError("epoch already processed")
            seen_epochs.add(epoch)
            activated = entries[:activation_limit]
            entries = entries[len(activated) :]
            active.update(activated)
            count = min(exit_limit, len(exits), max(len(active) - minimum, 0))
            removed = exits[:count]
            exits = exits[count:]
            active.difference_update(removed)
            trace.append(
                {
                    "epoch": epoch,
                    "activated": activated,
                    "exited": removed,
                    "active_count": len(active),
                }
            )
        else:
            raise ValueError("unknown validator event")
    return {
        "active": sorted(active),
        "activation_queue": entries,
        "exit_queue": exits,
        "trace": trace,
    }


def analyze(document):
    validate_document(document)
    try:
        return result(_analyze(document))
    except (KeyError, TypeError, ArithmeticError, RecursionError) as error:
        raise ValueError("invalid domain input: " + str(error)) from error
