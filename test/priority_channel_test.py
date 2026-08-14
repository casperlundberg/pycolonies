import unittest

from pycolonies import Colonies, FuncSpec, Conditions
from model import PriorityUpdate, PriorityUpdateResult


class TestPriorityChannel(unittest.TestCase):
    """The client side of the priority channel.

    These pin the wire shape and the return type without needing a server: the
    RPC call itself is replaced, so what is under test is the message this
    client builds and how it reads the reply.
    """

    def _client_with_captured_rpc(self, response):
        client = Colonies("localhost", 8080)
        captured = {}

        def fake_rpc(msg, prvkey):
            captured["msg"] = msg
            captured["prvkey"] = prvkey
            return response

        # __rpc is name-mangled, so patch the mangled attribute.
        client._Colonies__rpc = fake_rpc

        return client, captured

    def test_sends_a_colony_scoped_bulk_message(self):
        client, captured = self._client_with_captured_rpc([
            {"processid": "p1", "outcome": "updated", "priority": 0},
            {"processid": "p2", "outcome": "not_waiting", "priority": 50},
        ])

        results = client.set_process_priorities(
            "test_colony",
            [PriorityUpdate(processid="p1", priority=0), PriorityUpdate(processid="p2", priority=0)],
            "prvkey")

        msg = captured["msg"]
        assert msg["msgtype"] == "setprocessprioritiesmsg"
        assert msg["colonyname"] == "test_colony"
        assert msg["updates"] == [
            {"processid": "p1", "priority": 0},
            {"processid": "p2", "priority": 0},
        ]
        assert captured["prvkey"] == "prvkey"

        # A process that could not be moved is reported, not raised.
        assert [r.outcome for r in results] == ["updated", "not_waiting"]
        assert isinstance(results[0], PriorityUpdateResult)
        assert results[1].priority == 50

    def test_accepts_plain_dicts(self):
        client, captured = self._client_with_captured_rpc([
            {"processid": "p1", "outcome": "updated", "priority": 25},
        ])

        results = client.set_process_priorities("test_colony", [{"processid": "p1", "priority": 25}], "prvkey")

        assert captured["msg"]["updates"] == [{"processid": "p1", "priority": 25}]
        assert results[0].priority == 25

    def test_func_spec_carries_optional_priority_bounds(self):
        # Escalation above the submission priority is opt-in, and the opt-in
        # travels with the spec.
        spec = FuncSpec(conditions=Conditions(executortype="test_executor_type"), priority=25, priorityceiling=400)
        dumped = spec.model_dump(by_alias=True)
        assert dumped["priorityceiling"] == 400
        assert dumped["priorityfloor"] is None

        unbounded = FuncSpec(conditions=Conditions(executortype="test_executor_type"), priority=25)
        assert unbounded.model_dump(by_alias=True)["priorityceiling"] is None
