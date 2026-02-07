"""Quest data format adapter - converts Quest CSV/JSON to frames.json format."""

import json
import csv
import os
from pathlib import Path


class QuestDataAdapter:
    """Converts Quest 3 camera/pose data to unified frames.json format."""
    
    @staticmethod
    def adapt_quest_data(extraction_dir):
        """
        Convert Quest export format to frames.json.
        
        Args:
            extraction_dir: Path to extracted Quest data
            
        Returns:
            Path to generated frames.json
        """
        extraction_path = Path(extraction_dir)
        
        # Read HMD poses
        hmd_poses_file = extraction_path / "hmd_poses.csv"
        if not hmd_poses_file.exists():
            raise FileNotFoundError("hmd_poses.csv not found")
        
        poses = []
        with open(hmd_poses_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                poses.append({
                    'timestamp': int(row['unix_time']),
                    'position': [
                        float(row['pos_x']),
                        float(row['pos_y']),
                        float(row['pos_z'])
                    ],
                    'rotation': [
                        float(row['rot_w']),  # Quaternion format: w, x, y, z
                        float(row['rot_x']),
                        float(row['rot_y']),
                        float(row['rot_z'])
                    ]
                })
        
        # Read camera characteristics
        left_cam_file = extraction_path / "left_camera_characteristics.json"
        right_cam_file = extraction_path / "right_camera_characteristics.json"
        
        cameras = {}
        if left_cam_file.exists():
            with open(left_cam_file, 'r') as f:
                cameras['left'] = json.load(f)
        
        if right_cam_file.exists():
            with open(right_cam_file, 'r') as f:
                cameras['right'] = json.load(f)
        
        # Scan for image files
        left_images = sorted([f.name for f in (extraction_path / "left_camera_raw").iterdir() if f.suffix == '.yuv'])
        right_images = sorted([f.name for f in (extraction_path / "right_camera_raw").iterdir() if f.suffix == '.yuv'])
        left_depth = sorted([f.name for f in (extraction_path / "left_depth").iterdir() if f.suffix == '.raw'])
        right_depth = sorted([f.name for f in (extraction_path / "right_depth").iterdir() if f.suffix == '.raw'])
        
        # Build frames structure
        frames = []
        for i in range(min(len(left_images), len(poses))):
            frame = {
                'frame_id': i,
                'timestamp': poses[i]['timestamp'],
                'pose': {
                    'position': poses[i]['position'],
                    'rotation': poses[i]['rotation']
                },
                'cameras': {
                    'left': {
                        'image': f"left_camera_raw/{left_images[i]}",
                        'depth': f"left_depth/{left_depth[i]}" if i < len(left_depth) else None
                    },
                    'right': {
                        'image': f"right_camera_raw/{right_images[i]}" if i < len(right_images) else None,
                        'depth': f"right_depth/{right_depth[i]}" if i < len(right_depth) else None
                    }
                }
            }
            frames.append(frame)
        
        # Write frames.json
        output = {
            'version': '1.0',
            'source': 'Quest 3',
            'camera_metadata': cameras,
            'frames': frames
        }
        
        frames_json_path = extraction_path / "frames.json"
        with open(frames_json_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        return str(frames_json_path)
