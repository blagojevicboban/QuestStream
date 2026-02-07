"""Test script to debug Quest YUV processing."""

import sys
import json
from pathlib import Path

# Add modules to path
sys.path.insert(0, r'c:\Users\Mejkerslab\.gemini\antigravity\scratch\QuestStream')

from modules.quest_image_processor import QuestImageProcessor

# Test data
project_dir = r"D:\METAQUEST\20260206_145230_extracted"

# Load frames.json
with open(Path(project_dir) / "frames.json", 'r') as f:
    data = json.load(f)

frame = data['frames'][0]

print("Testing frame 0...")
print(f"YUV path: {frame['cameras']['left']['image']}")
print(f"Depth path: {frame['cameras']['left']['depth']}")

# Test YUV loading
yuv_path = Path(project_dir) / frame['cameras']['left']['image']
print(f"\nYUV file exists: {yuv_path.exists()}")
print(f"YUV file size: {yuv_path.stat().st_size} bytes")

# Load format info
format_json = Path(project_dir) / "left_camera_image_format.json"
with open(format_json, 'r') as f:
    format_info = json.load(f)
    print(f"\nFormat info:")
    print(f"  Width: {format_info['width']}")
    print(f"  Height: {format_info['height']}")
    print(f"  Format: {format_info['format']}")

# Calculate expected size
width = format_info['width']
height = format_info['height']
y_size = width * height
uv_size = (width // 2) * (height // 2)
expected_size = y_size + 2 * uv_size

print(f"\nExpected YUV size: {expected_size} bytes")
print(f"Actual YUV size: {yuv_path.stat().st_size} bytes")
print(f"Difference: {yuv_path.stat().st_size - expected_size} bytes")

# Try to load YUV
print("\nAttempting YUV conversion...")
try:
    rgb = QuestImageProcessor.yuv420_to_rgb(str(yuv_path), width, height)
    print(f"✓ YUV conversion successful! RGB shape: {rgb.shape}")
except Exception as e:
    print(f"✗ YUV conversion failed: {e}")
    import traceback
    traceback.print_exc()

# Test depth loading
depth_path = Path(project_dir) / frame['cameras']['left']['depth']
print(f"\nDepth file exists: {depth_path.exists()}")
if depth_path.exists():
    print(f"Depth file size: {depth_path.stat().st_size} bytes")
    
    # Try to load depth
    print("\nAttempting depth loading...")
    try:
        # Assume 256x256 for now
        depth = QuestImageProcessor.load_raw_depth(str(depth_path), 256, 256)
        print(f"✓ Depth loading successful! Depth shape: {depth.shape}")
    except Exception as e:
        print(f"✗ Depth loading failed: {e}")
        import traceback
        traceback.print_exc()

print("\nTest complete!")
