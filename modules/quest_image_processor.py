"""Quest Image Processing - YUV to RGB conversion and depth processing."""

import numpy as np
import json
import os
from pathlib import Path
import struct

# Lazy load cv2
cv2 = None

def _ensure_cv2():
    global cv2
    if cv2 is None:
        import cv2 as cv2_module
        cv2 = cv2_module
    return cv2

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
        
        cv2 = _ensure_cv2()
        
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
        Process a single Quest frame (YUV + depth or JPG + PNG).
        Auto-detects format based on file extensions.
        
        Args:
            project_dir: Path to Quest project directory
            frame_info: Frame dictionary from frames.json
            camera: 'left', 'right', or 'center' (for new format)
            
        Returns:
            Tuple of (rgb_image, depth_map, depth_info) or (None, None, None) if failed
        """
        project_path = Path(project_dir)
        
        try:
            # Check which camera format we're using
            if camera not in frame_info.get('cameras', {}):
                # If camera not found, try 'center' as fallback (new format)
                if 'center' in frame_info.get('cameras', {}):
                    camera = 'center'
                else:
                    return None, None, None
            
            camera_data = frame_info['cameras'][camera]
            image_path_rel = camera_data.get('image', '')
            
            if not image_path_rel:
                return None, None, None
            
            image_path = project_path / image_path_rel
            
            if not image_path.exists():
                return None, None, None
            
            # Auto-detect image format by extension
            image_ext = image_path.suffix.lower()
            
            # Use local cv2 reference
            cv2 = _ensure_cv2()
            
            # NEW FORMAT: JPG/PNG
            if image_ext in ['.jpg', '.jpeg', '.png']:
                rgb_image = cv2.imread(str(image_path))
                if rgb_image is None:
                    return None, None, None
                
                # OpenCV loads as BGR, convert to RGB
                rgb_image = cv2.cvtColor(rgb_image, cv2.COLOR_BGR2RGB)
                
                # Load depth if available (PNG 16-bit)
                depth_path_rel = camera_data.get('depth')
                if depth_path_rel:
                    depth_path = project_path / depth_path_rel
                    if depth_path.exists():
                        depth_map = cv2.imread(str(depth_path), cv2.IMREAD_UNCHANGED)
                        
                        # Convert 16-bit to float if needed
                        if depth_map is not None and depth_map.dtype == np.uint16:
                            # Normalize to meters (assuming depth is in mm or similar)
                            depth_map = depth_map.astype(np.float32) / 1000.0
                        
                        return rgb_image, depth_map, None
                    
                return rgb_image, None, None
            
            # OLD FORMAT: YUV + RAW
            elif image_ext == '.yuv':
                # Load image format info
                format_json = project_path / f"{camera}_camera_image_format.json"
                if not format_json.exists():
                    return None, None, None
                
                format_info = QuestImageProcessor.load_image_format_info(format_json)
                
                # Get image dimensions from format info
                width = format_info.get('width', 640)
                height = format_info.get('height', 480)
                
                # Load YUV and convert to RGB
                rgb_image = QuestImageProcessor.yuv420_to_rgb(str(image_path), width, height)
                
                # Load depth map
                depth_path_rel = camera_data.get('depth')
                if not depth_path_rel:
                    return rgb_image, None, None
                
                depth_path = project_path / depth_path_rel
                if not depth_path.exists():
                    return rgb_image, None, None
                
                # Load depth descriptor to get dimensions
                depth_descriptor_csv = project_path / f"{camera}_depth_descriptors.csv"
                timestamp = frame_info.get('timestamp', 0)
                
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
                
                return rgb_image, depth_map, depth_info
            
            else:
                print(f"Unsupported image format: {image_ext}")
                return None, None, None
            
        except Exception as e:
            import traceback
            import sys
            err_msg = f"Quest frame error: {e}\n{traceback.format_exc()}"
            print(err_msg)
            sys.stderr.write(err_msg)
            return None, None, None
