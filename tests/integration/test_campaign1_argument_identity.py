import unittest
from pathlib import Path
from scripts.campaign1_verification.argument_review import compare

class ArgumentIdentity(unittest.TestCase):

    def test_relative_invocation_cannot_change_owned_path_identity(self):
        root = Path('data/campaign1-verifier/argument-test-fixture')
        actual = str(root.resolve() / 'incoming')
        predicate = {'tool': 'file.read', 'field': 'path', 'op': 'eq', 'value': 'C:\\EvalFixture\\incoming'}
        relative = compare({'path': actual}, predicate, root, 'Read incoming.')
        absolute = compare({'path': actual}, predicate, root.resolve(), 'Read incoming.')
        self.assertEqual(relative, absolute)
        self.assertTrue(relative['literal_pass'])

    def test_windows_separators_and_app_case_are_identity_only(self):
        predicate = {'tool': 'file.read', 'field': 'path', 'op': 'eq', 'value': 'C:\\EvalFixture\\\\incoming'}
        x = compare({'path': 'C:\\owned\\incoming'}, predicate, 'C:\\owned', 'List path.')
        self.assertFalse(x['literal_pass'])
        self.assertTrue(x['identity_equivalent'])
        doubled = {'tool': 'file.read', 'field': 'path', 'op': 'eq', 'value': 'C:\\\\EvalFixture\\\\incoming'}
        x = compare({'path': 'C:\\owned\\incoming'}, doubled, 'C:\\owned', 'List path.')
        self.assertFalse(x['literal_pass'])
        self.assertTrue(x['identity_equivalent'])
        app = compare({'app': 'notepad'}, {'tool': 'app.open', 'field': 'app', 'op': 'eq', 'value': 'Notepad'}, 'C:\\owned', 'Open Notepad.')
        self.assertFalse(app['literal_pass'])
        self.assertTrue(app['identity_equivalent'])

    def test_sentence_punctuation_is_disclosed_without_rewriting_oracle(self):
        p = {'tool': 'file.write', 'field': 'path', 'op': 'eq', 'value': 'C:\\EvalFixture\\agenda.txt.'}
        x = compare({'path': 'C:\\owned\\agenda.txt'}, p, 'C:\\owned', 'Write to C:\\owned\\agenda.txt.')
        self.assertFalse(x['literal_pass'])
        self.assertFalse(x['identity_equivalent'])
        self.assertIsNotNone(x['annotation_limitation'])

    def test_record_ids_text_and_different_paths_remain_distinct(self):
        for field, a, b, tool in [('id', 'ABC', 'abc', 'todo.get'), ('text', 'Team', 'team', 'file.write'), ('path', 'C:\\owned\\a', 'C:\\owned\\b', 'file.read')]:
            x = compare({field: a}, {'tool': tool, 'field': field, 'op': 'eq', 'value': b}, 'C:\\owned', 'Exact content.')
            self.assertFalse(x['identity_equivalent'])
if __name__ == '__main__':
    unittest.main()
