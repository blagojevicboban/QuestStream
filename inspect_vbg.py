
import open3d as o3d
import open3d.core as o3c

def inspect_vbg():
    print(f"Open3D Version: {o3d.__version__}")
    
    device = o3c.Device("CPU:0")
    vbg = o3d.t.geometry.VoxelBlockGrid(
        attr_names=('tsdf', 'weight', 'color'),
        attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
        attr_channels=((1), (1), (3)),
        voxel_size=0.01,
        block_resolution=16,
        block_count=1000,
        device=device
    )
    
    print("\nDir(vbg):")
    print(dir(vbg))
    
    print("\nDir(vbg.hashmap()):")
    print(dir(vbg.hashmap()))

if __name__ == "__main__":
    inspect_vbg()
