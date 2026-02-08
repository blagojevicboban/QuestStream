import yaml
import os

DEFAULT_CONFIG = {
    "reconstruction": {
        "voxel_size": 0.01,
        "trunc_voxel_multiplier": 8.0,
        "depth_max": 2.0,
        "use_confidence_filtered_depth": True,
        "confidence_threshold": 0.05,
        "valid_count_threshold": 4,
        "block_resolution": 16,
        "block_count": 50000,
        "frame_interval": 5,
        "camera": "left"
    },
    "ingestion": {
        "validation_checksum": True,
    },
    "post_processing": {
        "enable": True,
        "smoothing_iterations": 5, # Laplacian smoothing
        "decimation_target_triangles": 100000, # 0 to disable
        "remove_outliers": True,
        "outlier_nb_neighbors": 20,
        "outlier_std_ratio": 2.0
    },
    "export": {
        "format": "obj",  # ply, obj, glb
        "save_mesh": True,
        "save_pointcloud": False,
    }
}

class ConfigManager:
    def __init__(self, config_path="config.yml"):
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_path):
            self.save_config(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        
        try:
            with open(self.config_path, "r") as f:
                return yaml.safe_load(f) or DEFAULT_CONFIG
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG

    def save_config(self, config=None):
        if config is None:
            config = self.config
        try:
            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def set(self, key, value):
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self.save_config()
