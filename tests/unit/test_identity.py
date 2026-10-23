from __future__ import annotations
import unittest
from hanni.core.identity import Actor, ActorKind, local_machine_name

class IdentityTests(unittest.TestCase):

    def test_v1_actor_kinds(self) -> None:
        """D-0010: owner, local machine, internal - no remote/Discord identities in V1."""
        self.assertEqual({kind.value for kind in ActorKind}, {'owner', 'local-machine', 'internal'})

    def test_clear_authority(self) -> None:
        self.assertTrue(Actor.owner().may_clear_emergency_stop)
        self.assertTrue(Actor.owner('voice').may_clear_emergency_stop)
        self.assertTrue(Actor.local('LAPTOP').may_clear_emergency_stop)
        self.assertFalse(Actor.internal('supervisor-llm').may_clear_emergency_stop)
        self.assertFalse(Actor.internal('watchdog').may_clear_emergency_stop)

    def test_actor_validation_and_label(self) -> None:
        self.assertEqual(Actor.local('LAPTOP').label, 'local-machine:LAPTOP')
        self.assertEqual(Actor.owner('voice').label, 'owner:voice')
        self.assertTrue(Actor.owner().is_owner)
        self.assertFalse(Actor.local().is_owner)
        with self.assertRaises(ValueError):
            Actor(ActorKind.OWNER, '')
        with self.assertRaises(TypeError):
            Actor('owner', '1')

    def test_local_machine_name(self) -> None:
        self.assertEqual(local_machine_name({'HANNI_NODE_ID': ' laptop '}), 'laptop')
        self.assertTrue(local_machine_name({}))
        self.assertTrue(local_machine_name({'HANNI_NODE_ID': ''}))
