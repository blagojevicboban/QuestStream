
import time
import numpy as np
import open3d as o3d
import os
from modules.config_manager import ConfigManager
from modules.reconstruction import QuestReconstructor

def get_memory_usage():
    # Placeholder
    return 0

def benchmark():
    print("Starting benchmark...")
    print(f"Open3D Version: {o3d.__version__}")
    
    # Check for Tensor API
    try:
        import open3d.core as o3c
        # print(f"Open3D Core available. Cuda devices: {o3c.Device.get_available_devices()}")
        print("Open3D Core available.")
    except ImportError:
        print("Open3D Tensor API NOT available.")
    except AttributeError:
        print("Open3D Core interface mismatch.")

    # Mock Config
    config = ConfigManager()
    config.set("reconstruction.voxel_size", 0.005)
    
    reconstructor = QuestReconstructor(config)
    
    # Mock Data
    width, height = 640, 480
    intrinsics = np.array([
        [500, 0, 320],
        [0, 500, 240],
        [0, 0, 1]
    ], dtype=np.float64)
    
    frames_to_process = 50
    
    print(f"Benchmarking {frames_to_process} frames integration (CPU Legacy)...")
    start_time = time.time()
    start_mem = get_memory_usage()
    
    for i in range(frames_to_process):
        # Generate random RGB and Depth
        rgb = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        depth = np.random.uniform(0.1, 2.0, (height, width)).astype(np.float32)
        
        # Identity pose
        pose = np.eye(4)
        
        reconstructor.integrate_frame(rgb, depth, intrinsics, pose)
        
        if (i+1) % 10 == 0:
            print(f"Processed {i+1} frames...")
            
    end_time = time.time()
    end_mem = get_memory_usage()
    
    duration = end_time - start_time
    fps = frames_to_process / duration
    
    print(f"\nResults:")
    print(f"Total Time: {duration:.2f}s")
    print(f"FPS: {fps:.2f}")
    print(f"Memory Delta: {end_mem - start_mem:.2f} MB")
    
    # Mesh extraction
    print("\nExtracting mesh...")
    t0 = time.time()
    mesh = reconstructor.extract_mesh()
    print(f"Mesh extraction time: {time.time() - t0:.2f}s")
    print(f"Vertices: {len(mesh.vertices)}")

if __name__ == "__main__":
    benchmark()
