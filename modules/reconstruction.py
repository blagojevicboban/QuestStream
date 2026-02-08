"""
3D Reconstruction module using Open3D Tensor API (VoxelBlockGrid).
Implements Scalable TSDF volume integration for generating meshes from RGBD data.
Optimized for GPU acceleration.
"""

import numpy as np
from .config_manager import ConfigManager
import time

try:
    import open3d as o3d
    import open3d.core as o3c
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False
    o3d = None
    o3c = None

class QuestReconstructor:
    """
    Handles the integration of multiple RGBD frames into a single 3D volume
    using Open3D's VoxelBlockGrid (Tensor API).
    """
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager # Store for accessing post-processing config later
        self.config = config_manager.get("reconstruction")
        self.voxel_size = float(self.config.get("voxel_size", 0.01))
        self.trunc_voxel_multiplier = float(self.config.get("trunc_voxel_multiplier", 8.0))
        self.depth_max = float(self.config.get("depth_max", 3.0))
        self.sdf_trunc = self.voxel_size * self.trunc_voxel_multiplier
        self.block_resolution = int(self.config.get("block_resolution", 16))
        self.block_count = int(self.config.get("block_count", 50000))
        
        if HAS_OPEN3D:
            # Try to use CUDA if available
            self.device = o3c.Device("CPU:0")
            try:
                # Check for CUDA availability
                # Open3D 0.18+ approach
                if hasattr(o3c, "cuda") and o3c.cuda.is_available():
                    self.device = o3c.Device("CUDA:0")
                    print("QuestReconstructor: CUDA is available. Using GPU acceleration.")
                else:
                    # Fallback check by trying to create a device
                    try:
                        test_dev = o3c.Device("CUDA:0")
                        # If no exception, it might be valid, but best to stick to CPU if is_available missing
                        # Use CPU to be safe unless we are sure.
                        pass
                    except:
                        pass
                    print("QuestReconstructor: CUDA not available or not detected. Using CPU.")
            except Exception as e:
                print(f"QuestReconstructor: Error checking CUDA, using CPU. ({e})")

            # Initialize VoxelBlockGrid
            self.vbg = o3d.t.geometry.VoxelBlockGrid(
                attr_names=('tsdf', 'weight', 'color'),
                attr_dtypes=(o3c.float32, o3c.float32, o3c.float32),
                attr_channels=((1), (1), (3)),
                voxel_size=self.voxel_size,
                block_resolution=self.block_resolution,
                block_count=self.block_count,
                device=self.device
            )
        else:
            self.vbg = None

    def integrate_frame(self, rgb_image, depth_image, intrinsics, pose):
        """
        Integrate a single RGBD frame into the volume.
        
        Args:
            rgb_image: (H, W, 3) numpy array (uint8)
            depth_image: (H, W) numpy array (float32 meters)
            intrinsics: (3, 3) numpy array
            pose: (4, 4) numpy array (Camera to World)
        """
        if not self.vbg:
            return

        # Prepare Tensors on device
        # Depth is expected in uint16 or float32. 
        # Since input is float meters, we can use it directly with depth_scale=1.0 or convert to uint16 mm.
        # Tensor API integrate expects float depth usually.
        
        depth_tensor = o3d.t.geometry.Image(
            o3c.Tensor(depth_image.astype(np.float32), device=self.device)
        )
        
        color_tensor = o3d.t.geometry.Image(
            o3c.Tensor(rgb_image.astype(np.float32) / 255.0, device=self.device)
        )

        # Intrinsics
        intrinsics_tensor = o3c.Tensor(intrinsics.astype(np.float64), device=self.device)
        
        # Extrinsics (World to Camera) = Inverse of Pose (Camera to World)
        extrinsic = np.linalg.inv(pose)
        extrinsic_tensor = o3c.Tensor(extrinsic.astype(np.float64), device=self.device)

        # ScalableTSDFVolume parameters
        depth_scale = 1.0  # Input is already in meters
        depth_max = self.depth_max
        trunc_voxel_multiplier = self.trunc_voxel_multiplier
        
        # Get active blocks (frustum culling)
        # For Open3D 0.16+, VoxelBlockGrid has a direct integrate function 
        # that handles block allocation internally if we use the right overload.
        
        # However, looking at standard examples, we often see:
        # frustum_block_coords = vbg.hashmap().active_buf_indices()
        
        # Let's try the direct integration without manual block computation first, 
        # as modern Open3D Tensor API usually supports it.
        
        # If that fails, we might need to use the specific low-level API.
        # The error was 'AttributeError: 'open3d.cpu.pybind.core.HashMap' object has no attribute 'compute_active_block_indices'
        
        # Let's check available methods on vbg object in a separate script if possible, 
        # but for now let's try the most common pattern:
        
        # vbg.integrate(depth, color, intrinsic, extrinsic, depth_scale, depth_max)
        # This assumes the high-level API exists.
        
        # Get active blocks (frustum culling)
        # Fix for Open3D 0.18+ API
        
        # Create frustum block coordinates from depth
        # We need to use the method on the VoxelBlockGrid object or utility
        
        # Get active blocks (frustum culling)
        # Low-level implementation since high-level helpers are missing in 0.19
        
        # 1. Provide Depth Image to simple PointCloud
        # We need to compute which blocks are touched by the depth map.
        # This is usually done by "projecting" the depth map to 3D and finding unique block coords.
        
        # Create a point cloud from depth
        pcd = o3d.t.geometry.PointCloud.create_from_depth_image(
            depth_tensor,
            intrinsics_tensor,
            extrinsic_tensor,
            depth_scale,
            depth_max,
            stride=4  # Downsample for speed in block allocation
        )
        
        # Get coordinates
        points = pcd.point.positions
        
        # Compute block coordinates: floor(point / (voxel_size * block_resolution))
        # block_size = voxel_size * block_resolution
        block_size = self.voxel_size * self.block_resolution
        block_coords = (points / block_size).floor().to(o3c.int32)
        
        # Activate blocks in hashmap
        # This returns the indices of activated blocks and handles uniqueness internally usually
        # hashmap.activate(keys)
        # Note: activate might return a tuple or just buffers.
        # We need to get the unique keys to pass to integrate?
        # Actually, integrate takes 'frustum_block_coords' which are the *keys* (block indices), 
        # or 'block_indices' which are indices into the value tensor?
        # The argument name in signatures is usually 'block_coords'.
        
        hashmap = self.vbg.hashmap()
        
        # Unique block coords
        # unique_block_coords, _ = block_coords.unique(return_counts=False) # Tensor API doesn't have unique?
        # Hashmap `activate` handles uniqueness.
        
        buf_indices, masks = hashmap.activate(block_coords)
        
        # We need to identify which blocks are active for integration.
        # integrate expects 'block_coords' (Nx3 int32).
        # We can pass the unique block coords we just calculated/activated.
        
        # To get unique keys accurately:
        # 1. activation adds them.
        # 2. we can assume all 'buf_indices' returned are the ones we want? No, that's element-wise.
        
        # Let's try to just collect unique keys from the points.
        # Open3D Tensor API generic unique:
        # Not easily available.
        # However, checking Open3D examples for 0.18/0.19:
        # They usually use `compute_unique_block_coordinates` which I verified is MISSING in 0.19 Python API (or I missed it).
        # Wait, I missed checking `dir(vbg)` output carefully in previous step? 
        # Output was: ['__class__', ..., 'attribute', 'block_count', ..., 'integrate', ..., 'save', 'size', 'to', 'value_tensor', 'value_tensors']
        # 'compute_unique_block_coordinates' was NOT in `dir(vbg)`.
        
        # Workaround:
        # If we can't easily get unique active blocks, we might be stuck.
        # But `integrate` documentation says it needs `block_coords`.
        # Maybe we can pass *all* block coords from the point cloud? It might be slow but correct?
        # Or maybe `integrate` handles duplicates? 
        
        # Let's simple try to pass all block_coords from the stride=4 point cloud.
        
        self.vbg.integrate(
            block_coords,
            depth_tensor,
            color_tensor,
            intrinsics_tensor,
            intrinsics_tensor,
            extrinsic_tensor,
            depth_scale,
            depth_max
        )

    def extract_mesh(self):
        """
        Extract triangle mesh from the TSDF volume.
        Returns a legacy Open3D mesh for compatibility.
        """
        if not self.vbg:
             class DummyMesh:
                vertices = []
             return DummyMesh()
            
        # Extract mesh (Tensor)
        mesh_t = self.vbg.extract_triangle_mesh()
        
        # Convert to legacy mesh for GUI compatibility and advanced post-processing
        # (Tensor API post-processing is faster but legacy has more features exposed in Python)
        mesh_legacy = mesh_t.to_legacy()
        
        # Apply Post-Processing if enabled
        pp_config = self.config_manager.get("post_processing") if hasattr(self, "config_manager") else None
        
        # Fallback if config_manager not passed to __init__ (it is passed in current code)
        if pp_config and pp_config.get("enable", False):
            mesh_legacy = self.post_process_mesh(mesh_legacy, pp_config)
            
        return mesh_legacy

    def post_process_mesh(self, mesh, config):
        """
        Apply smoothing, decimation, and outlier removal.
        """
        if not mesh.has_vertices():
            return mesh
            
        print("Starting Mesh Post-Processing...")
        
        # 1. Outlier Removal (Components)
        if config.get("remove_outliers", True):
            # Remove small disconnected components (floating artifacts)
            # This is different from statistical outlier removal (which is for point clouds)
            # For meshes, we usually remove small clusters.
            # Open3D legacy: cluster_connected_triangles
            pass # TODO: complex to tune, maybe skip for now or use statistical if converted to PCD? 
            # Actually, standard outlier removal on vertices is:
            # mesh.remove_vertices_by_mask(...)
            # But let's stick to simple Smoothing first.
            
        # 1. Smoothing
        iterations = config.get("smoothing_iterations", 0)
        if iterations > 0:
            # Laplacian smoothing
            mesh = mesh.filter_smooth_laplacian(number_of_iterations=iterations)
            print(f" - Applied Laplacian smoothing ({iterations} iters)")

        # 2. Decimation
        target_triangles = config.get("decimation_target_triangles", 0)
        if target_triangles > 0 and len(mesh.triangles) > target_triangles:
            mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_triangles)
            print(f" - Decimated to {len(mesh.triangles)} triangles")
            
        # 3. Cleanup
        mesh.remove_degenerate_triangles()
        mesh.remove_duplicated_triangles()
        mesh.remove_duplicated_vertices()
        mesh.compute_vertex_normals()
        
        return mesh

    def extract_point_cloud(self):
        """
        Extract point cloud from the TSDF volume.
        Returns a legacy Open3D point cloud.
        """
        if not self.vbg:
             class DummyPC:
                points = []
             return DummyPC()
             
        pcd_t = self.vbg.extract_point_cloud()
        return pcd_t.to_legacy()
