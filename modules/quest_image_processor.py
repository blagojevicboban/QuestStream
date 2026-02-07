"""Quest Image Processing - YUV to RGB conversion and depth processing."""

import numpy as np
import cv2
import json
import os
from pathlib import Path
import struct


class QuestImageProcessor:
    """Processes Quest YUV images and raw depth maps."""
    
    @staticmethod
    def load_image_format_info(json_path):
        """Load Quest image format information from JSON."""
        with open(json_path, 'r') as f:
            return json.load(f)
    
    @staticmethod
    def yuv420_to_rgb(yuv_path, width, height):
        """
        Convert YUV_420_888 to RGB.
        
        Args:
            yuv_path: Path to .yuv file
            width: Image width
            height: Image height
            
        Returns:
            RGB image as numpy array (H, W, 3) uint8
        """
        # YUV_420_888 format:
        # Y plane: width * height
        # U plane: (width/2) * (height/2)
        # V plane: (width/2) * (height/2)
        
        y_size = width * height
        uv_size = (width // 2) * (height // 2)
        expected_size = y_size + 2 * uv_size
        
        with open(yuv_path, 'rb') as f:
            yuv_data = f.read()
        
        actual_size = len(yuv_data)
        if actual_size < expected_size:
            raise ValueError(
                f"YUV file too small: {actual_size} bytes, "
                f"expected at least {expected_size} bytes "
                f"for {width}x{height}"
            )
        
        # Note: Quest YUV files may have padding/extra data
        # Use only the expected amount
        yuv_data = yuv_data[:expected_size]
        
        # Extract Y, U, V planes
        y_plane = np.frombuffer(yuv_data[:y_size], dtype=np.uint8).reshape((height, width))
        u_plane = np.frombuffer(yuv_data[y_size:y_size + uv_size], dtype=np.uint8).reshape((height // 2, width // 2))
        v_plane = np.frombuffer(yuv_data[y_size + uv_size:y_size + 2 * uv_size], dtype=np.uint8).reshape((height // 2, width // 2))
        
        # Upsample U and V to full resolution
        u_upsampled = cv2.resize(u_plane, (width, height), interpolation=cv2.INTER_LINEAR)
        v_upsampled = cv2.resize(v_plane, (width, height), interpolation=cv2.INTER_LINEAR)
        
        # Stack into YUV image
        yuv_image = np.stack([y_plane, u_upsampled, v_upsampled], axis=-1)
        
        # Convert YUV to RGB using OpenCV
        rgb_image = cv2.cvtColor(yuv_image, cv2.COLOR_YUV2RGB)
        
        return rgb_image
    
    @staticmethod
    def load_depth_descriptor(csv_path, timestamp):
        """
        Load depth descriptor for a specific timestamp from CSV.
        
        Args:
            csv_path: Path to depth descriptor CSV
            timestamp: Unix timestamp in ms
            
        Returns:
            Dictionary with depth info or None
        """
        import csv as csv_module
        
        best_match = None
        min_diff = float('inf')
        
        with open(csv_path, 'r') as f:
            reader = csv_module.DictReader(f)
            for row in reader:
                row_timestamp = int(row['timestamp_ms'])
                diff = abs(row_timestamp - timestamp)
                
                # Find nearest timestamp within 100ms
                if diff < min_diff and diff < 100:
                    min_diff = diff
                    best_match = {
                        'width': int(row['width']),
                        'height': int(row['height']),
                        'near_z': float(row['near_z']),
                        'far_z': float(row['far_z']),
                        'fov_left': float(row['fov_left_angle_tangent']),
                        'fov_right': float(row['fov_right_angle_tangent']),
                        'fov_top': float(row['fov_top_angle_tangent']),
                        'fov_down': float(row['fov_down_angle_tangent']),
                    }
        
        return best_match
    
    @staticmethod
    def load_raw_depth(depth_path, width, height):
        """
        Load raw depth map from .raw file (float32 format).
        
        Args:
            depth_path: Path to .raw depth file
            width: Depth map width
            height: Depth map height
            
        Returns:
            Depth map as numpy array (H, W) float32
        """
        with open(depth_path, 'rb') as f:
            depth_data = f.read()
        
        # Each pixel is a float32 (4 bytes)
        expected_size = width * height * 4
        if len(depth_data) != expected_size:
            raise ValueError(f"Depth file size mismatch: {len(depth_data)} bytes, expected {expected_size}")
        
        # Read as float32 array
        depth_array = np.frombuffer(depth_data, dtype=np.float32)
        depth_map = depth_array.reshape((height, width))
        
        return depth_map
    
    @staticmethod
    def process_quest_frame(project_dir, frame_info, camera='left'):
        """
        Process a single Quest frame (YUV + depth).
        
        Args:
            project_dir: Path to Quest project directory
            frame_info: Frame dictionary from frames.json
            camera: 'left' or 'right'
            
        Returns:
            Tuple of (rgb_image, depth_map) or (None, None) if failed
        """
        project_path = Path(project_dir)
        
        try:
            # Load image format info
            format_json = project_path / f"{camera}_camera_image_format.json"
            if not format_json.exists():
                return None, None
            
            format_info = QuestImageProcessor.load_image_format_info(format_json)
            
            # Get image dimensions from format info
            width = format_info.get('width', 640)
            height = format_info.get('height', 480)
            
            # Load YUV and convert to RGB
            yuv_path = project_path / frame_info['cameras'][camera]['image']
            if not yuv_path.exists():
                return None, None
            
            rgb_image = QuestImageProcessor.yuv420_to_rgb(str(yuv_path), width, height)
            
            # Load depth map
            depth_path_rel = frame_info['cameras'][camera].get('depth')
            if not depth_path_rel:
                return rgb_image, None
            
            depth_path = project_path / depth_path_rel
            if not depth_path.exists():
                return rgb_image, None
            
            # Load depth descriptor to get dimensions
            depth_descriptor_csv = project_path / f"{camera}_depth_descriptors.csv"
            timestamp = frame_info['timestamp']
            
            depth_info = None
            if depth_descriptor_csv.exists():
                depth_info = QuestImageProcessor.load_depth_descriptor(
                    str(depth_descriptor_csv), 
                    timestamp
                )
            
            # Use default dimensions if descriptor not found (Quest 3 default is 320x320)
            depth_width = depth_info['width'] if depth_info else 320
            depth_height = depth_info['height'] if depth_info else 320
            
            depth_map = QuestImageProcessor.load_raw_depth(
                str(depth_path), 
                depth_width, 
                depth_height
            )
            
            # Resize depth to match RGB if needed
            if depth_map.shape != (height, width):
                depth_map = cv2.resize(depth_map, (width, height), interpolation=cv2.INTER_NEAREST)
            
            return rgb_image, depth_map
            
        except Exception as e:
            import traceback
            import sys
            err_msg = f"Quest frame error: {e}\n{traceback.format_exc()}"
            print(err_msg)
            sys.stderr.write(err_msg)
            return None, None
