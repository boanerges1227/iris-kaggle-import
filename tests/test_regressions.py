"""Regression tests for import edge cases, runnable locally or in the IRIS container."""
import os
import sys
import tempfile
import unittest
import types
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'python'))
import kaggleloader as loader


class FakeSQL:
    """Record table operations and simulate existing table metadata."""
    def __init__(self, exists=False):
        self.exists = exists
        self.commands = []

    def exec(self, sql):
        self.commands.append(sql)

    def prepare(self, sql):
        return self

    def execute(self, *args):
        return [(1 if self.exists else 0,)]


class FakeIris:
    def __init__(self, exists=False):
        self.sql = FakeSQL(exists)


class ImportRegressionTests(unittest.TestCase):
    def test_colliding_file_names_fail_before_import(self):
        """Reject file name collisions before modifying tables."""
        with tempfile.TemporaryDirectory() as directory:
            for name in ('a-b.csv', 'a_b.csv'):
                with open(os.path.join(directory, name), 'w') as file:
                    file.write('x\n1\n')
            iris = FakeIris()
            modules = {'iris': iris, 'kagglehub': types.SimpleNamespace(dataset_download=lambda handle: directory)}
            with patch.dict(sys.modules, modules):
                result = loader.load_kaggle_to_iris('owner/dataset')
            self.assertIn('same target table', result['error'])
            self.assertEqual(iris.sql.commands, [])

    def test_csv_rejects_extra_fields_without_creating_table(self):
        """Reject extra CSV fields before creating a table."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'data.csv')
            with open(path, 'w') as file:
                file.write('a,b\n1,2,3\n')
            iris = FakeIris()
            result = loader._import_csv(iris, path, 'Test', 'data', 'replace', 0)
            self.assertIn('error', result)
            self.assertEqual(iris.sql.commands, [])

    def test_csv_names_remain_unique_after_normalization(self):
        """Resolve collisions between source names and generated suffixes."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'data.csv')
            with open(path, 'w') as file:
                file.write('a,a,a_1\n1,2,3\n')
            iris = FakeIris()
            result = loader._import_csv(iris, path, 'Test', 'data', 'replace', 0)
            self.assertEqual(len(result['columnTypes']), 3)

    def test_parquet_append_does_not_create_existing_table(self):
        """Do not create an existing table when appending Parquet data."""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest('pyarrow is unavailable')
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'data.parquet')
            pq.write_table(pa.table({'a': [1]}), path)
            iris = FakeIris(exists=True)
            result = loader._import_parquet(iris, path, 'Test', 'data', 'append', 0)
            self.assertNotIn('error', result)
            self.assertFalse(any(command.startswith('CREATE') for command in iris.sql.commands))

    def test_table_lookup_errors_are_not_treated_as_missing(self):
        """Do not treat metadata query errors as missing tables."""
        iris = FakeIris()
        with patch.object(iris.sql, 'prepare', side_effect=RuntimeError('metadata unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'metadata unavailable'):
                loader._table_exists(iris, 'Test', 'data')

if __name__ == '__main__':
    unittest.main()
