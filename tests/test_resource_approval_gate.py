from __future__ import annotations

from core.resource_access import ResourceAccessEvaluator, ResourceAccessProfile, ResourceAccessRule


def test_resource_requires_approval_when_allowed_and_flagged() -> None:
    ev = ResourceAccessEvaluator(
        ResourceAccessProfile(
            rules={
                "long_term_memory": ResourceAccessRule(
                    read="allow",
                    write="allow",
                    write_requires_approval=True,
                )
            }
        )
    )
    assert ev.is_allowed("long_term_memory", "write") is True
    assert ev.requires_approval("long_term_memory", "write") is True


def test_resource_requires_approval_false_when_denied() -> None:
    ev = ResourceAccessEvaluator(
        ResourceAccessProfile(
            rules={
                "long_term_memory": ResourceAccessRule(
                    read="allow",
                    write="deny",
                    write_requires_approval=True,
                )
            }
        )
    )
    assert ev.is_allowed("long_term_memory", "write") is False
    assert ev.requires_approval("long_term_memory", "write") is False
