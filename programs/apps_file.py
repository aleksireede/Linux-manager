from pathlib import Path
import yaml

from programs.installer_logic import detect_install_method

class AppsFileStore:
    def __init__(self, yaml_path=None):
        self.yaml_path = yaml_path or Path(__file__).parent.parent.resolve().joinpath("bin", "apps.yaml")
        self.yaml_data_loaded = []
        self._is_loaded = False

    def load_apps_from_file(self):
        return self.get_apps(self.load_yaml())

    def load_yaml(self):
        if self._is_loaded:
            return self.yaml_data_loaded

        if not self.yaml_path.exists():
            self.yaml_data_loaded = []
            self._is_loaded = True
            return self.yaml_data_loaded

        with open(self.yaml_path, "r") as f:
            try:
                data = yaml.safe_load(f)
                self.yaml_data_loaded = data if isinstance(data, list) else []
            except yaml.YAMLError:
                self.yaml_data_loaded = []
        self._is_loaded = True
        return self.yaml_data_loaded

    @staticmethod
    def get_apps(yaml_data):
        """Extract apps from YAML data into a list."""
        return [app["name"] for app in yaml_data if "name" in app]

    def get_app_source(self, app_name):
        yaml_data = self.load_yaml()
        for app in yaml_data:
            if app.get("name") == app_name:
                return app.get("source")
        return None

    def get_app_category(self, app_name):
        for app in self.load_yaml():
            if app.get("name") == app_name:
                return str(app.get("category") or "Universal").strip() or "Universal"
        return "Universal"

    def set_apps_category(self, app_names, category):
        category = category.strip() or "Universal"
        names = set(app_names)
        data = self.load_yaml()
        for app in data:
            if app.get("name") in names:
                app["category"] = category
        self.write_to_yaml(data)

    def add_app_to_yaml(self, app_to_add, category="Universal"):
        yaml_data = self.load_yaml()
        source = detect_install_method(app_to_add)
        application = {
            "name": app_to_add,
            "description": f"Default description for {app_to_add}",
            "source": source if source else "Unknown",
            "category": category.strip() or "Universal",
            "conflicts": [],
        }
        yaml_data.append(application)
        self.write_to_yaml(yaml_data)

    def remove_app_from_yaml(self, app_to_remove):
        yaml_data = self.load_yaml()
        self.yaml_data_loaded = [app for app in yaml_data if app.get("name") != app_to_remove]
        self.write_to_yaml(self.yaml_data_loaded)

    def write_to_yaml(self, yaml_data):
        yaml_data.sort(key=lambda x: x.get("name", ""))
        self.yaml_data_loaded = yaml_data
        self._is_loaded = True
        with open(self.yaml_path, "w") as f:
            yaml.safe_dump(self.yaml_data_loaded, f, sort_keys=False)


apps_file_store = AppsFileStore()
yaml_data_loaded = []


def load_apps_from_file():
    return apps_file_store.load_apps_from_file()


def load_yaml():
    global yaml_data_loaded
    yaml_data_loaded = apps_file_store.load_yaml()
    return yaml_data_loaded


def get_apps(yaml_data):
    return apps_file_store.get_apps(yaml_data)


def get_app_source(app_name):
    return apps_file_store.get_app_source(app_name)


def add_app_to_yaml(app_to_add, category="Universal"):
    apps_file_store.add_app_to_yaml(app_to_add, category)


def get_app_category(app_name):
    return apps_file_store.get_app_category(app_name)


def set_apps_category(app_names, category):
    apps_file_store.set_apps_category(app_names, category)


def remove_app_from_yaml(app_to_remove):
    apps_file_store.remove_app_from_yaml(app_to_remove)


def write_to_yaml(yaml_data):
    apps_file_store.write_to_yaml(yaml_data)


if __name__ == "__main__":
    load_yaml()
    print(yaml_data_loaded)
