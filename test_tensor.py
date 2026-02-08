
import open3d as o3d
import numpy as np

def test_tensor_api():
    print(f"Open3D Version: {o3d.__version__}")
    
    try:
        import open3d.core as o3c
        # device = o3c.Device("CUDA:0") if o3c.Device("CUDA:0").is_available() else o3c.Device("CPU:0")
        # defaulting to CPU for now to ensure baseline works
        device = o3c.Device("CPU:0")
        print(f"Using device: {device}")
        
        # Create VoxelGrid
        voxel_size = 0.005
        sdf_trunc = 0.02
        block_resolution = 16
        block_count = 1000
        
        vbg = o3d.t.geometry.VoxelBlockGrid(
            attr_names=('tsdf', 'weight', 'color'),
            attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
            attr_channels=((1), (1), (3)),
            voxel_size=voxel_size,
            block_resolution=block_resolution,
            block_count=block_count,
            device=device
        )
        print("VoxelBlockGrid created successfully.")
        
        # Create dummy RGBD
        width, height = 640, 480
        depth = o3d.t.geometry.Image(
            np.random.uniform(0.1, 2.0, (height, width)).astype(np.float32)
        ).to(device)
        color = o3d.t.geometry.Image(
            np.random.randint(0, 255, (height, width, 3), dtype=np.uint8).astype(np.float32) / 255.0
        ).to(device)
        
        intrinsics = o3c.Tensor(
            [[500, 0, 320], [0, 500, 240], [0, 0, 1]], 
            dtype=o3c.float64, 
            device=device
        )
        extrinsic = o3c.Tensor(np.eye(4), dtype=o3c.float64, device=device)
        
        # Integrate
        frustum_block_coords = vbg.hashmap().active_buf_indices()
        
        # This part requires specific implementation details from Open3D Tensor API examples
        # Simulating integration call if available in high-level API
        # o3d.t.pipelines.integration doesn't exist in same way as legacy
        
        # We need to use core operations. 
        # But let's check if we can simply use the VoxelBlockGrid.
        
        print("Test complete (VoxelBlockGrid instantiation works).")
        return True
        
    except Exception as e:
        print(f"Tensor API test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_tensor_api()
