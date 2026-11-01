"""Check that IPM includes the Embedded Python package."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


class PackagingTests(unittest.TestCase):
    def test_ipm_dependencies_include_rpds(self):
        """The clean IPM bootstrap requires rpds-py for jsonschema dependencies."""
        requirements = (Path(__file__).resolve().parents[1] / 'requirements.txt').read_text().splitlines()
        self.assertTrue(any(line.strip().lower().startswith('rpds-py') for line in requirements))

    def test_python_package_is_a_file_copy_resource(self):
        """The Python source directory must be installed as files, not as a class package."""
        root = ET.parse(Path(__file__).resolve().parents[1] / 'module.xml').getroot()
        copies = [(node.get('Name'), node.get('Target')) for node in root.iter('FileCopy')]
        self.assertIn(('python/kaggleloader', '${libdir}python/kaggleloader/'), copies)
        self.assertNotIn('python', [node.get('Name') for node in root.iter('Resource')])

if __name__ == '__main__':
    unittest.main()
