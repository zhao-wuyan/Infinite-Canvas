import unittest
from pathlib import Path


class DockerfileTests(unittest.TestCase):
    def test_runtime_import_dependencies_are_copied(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("COPY . .", dockerfile)

    def test_dreamina_cli_template_is_preserved_for_mounted_state(self):
        dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

        self.assertIn("/opt/dreamina-cli-template", dockerfile)
        self.assertIn("/home/appuser/.dreamina_cli", dockerfile)


if __name__ == "__main__":
    unittest.main()
