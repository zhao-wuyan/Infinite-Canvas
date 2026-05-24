import unittest

from app_runtime import app_base_url, resolve_app_port, resolve_runtime_paths


class ResolveRuntimePathsTests(unittest.TestCase):
    def test_defaults_to_base_dir_when_data_root_missing(self):
        paths = resolve_runtime_paths("/tmp/app")

        self.assertEqual(paths["APP_DIR"], "/tmp/app")
        self.assertEqual(paths["APP_DATA_ROOT"], "/tmp/app")
        self.assertEqual(paths["STATIC_DIR"], "/tmp/app/static")
        self.assertEqual(paths["API_ENV_FILE"], "/tmp/app/API/.env")

    def test_separates_resource_and_data_roots(self):
        paths = resolve_runtime_paths("/opt/infinite-canvas", "/data/infinite-canvas")

        self.assertEqual(paths["WORKFLOW_DIR"], "/opt/infinite-canvas/workflows")
        self.assertEqual(paths["STATIC_DIR"], "/opt/infinite-canvas/static")
        self.assertEqual(paths["OUTPUT_DIR"], "/data/infinite-canvas/output")
        self.assertEqual(paths["DATA_DIR"], "/data/infinite-canvas/data")
        self.assertEqual(paths["GLOBAL_CONFIG_FILE"], "/data/infinite-canvas/global_config.json")

    def test_resolve_app_port_uses_default_for_invalid_values(self):
        self.assertEqual(resolve_app_port(""), 3000)
        self.assertEqual(resolve_app_port("70000"), 3000)
        self.assertEqual(resolve_app_port("3005"), 3005)

    def test_app_base_url_uses_resolved_port(self):
        self.assertEqual(app_base_url(3011), "http://127.0.0.1:3011")
        self.assertEqual(app_base_url("bad"), "http://127.0.0.1:3000")


if __name__ == "__main__":
    unittest.main()
