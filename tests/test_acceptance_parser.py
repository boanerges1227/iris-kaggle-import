"""Tests for interpreting acceptance output without cross-case matches."""
import importlib.util
import json
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('acceptance', pathlib.Path(__file__).with_name('verify_acceptance.py'))
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


class AcceptanceParserTests(unittest.TestCase):
    def test_errors_in_one_case_do_not_satisfy_another(self):
        """Each assertion must inspect the corresponding result, not the whole log."""
        results = {
            'import': {'status': 'success', 'rowsWritten': 782, 'tables': [{'file': '2015.csv'}]},
            'info': {'files': ['2015.csv']},
            'invalid': {'status': 'success', 'error': 'invalid handle'},
            'pinned': {'status': 'success', 'pinned': True},
            'fail': {'status': 'error', 'error': 'already exists'},
            'limit': {'status': 'success', 'tables': [{'rows': 10}]},
        }
        self.assertIn('invalid', acceptance.check_results(results))

    def test_marked_json_survives_other_output(self):
        """Kaggle download messages must not be mistaken for result records."""
        log = 'Downloading...\nCASE:invalid\n' + json.dumps({'status': 'error'}) + '\n'
        self.assertEqual(acceptance.parse_results(log)['invalid']['status'], 'error')

if __name__ == '__main__':
    unittest.main()
