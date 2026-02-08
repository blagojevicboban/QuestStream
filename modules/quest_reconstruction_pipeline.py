"""Quest-specific 3D reconstruction pipeline."""

import json
import numpy as np
from pathlib import Path
from threading import Thread

from .quest_image_processor import QuestImageProcessor
from .reconstruction import QuestReconstructor, HAS_OPEN3D
from .config_manager import ConfigManager


class QuestReconstructionPipeline:
    """End-to-end reconstruction pipeline for Quest data."""
    
    def __init__(self, project_dir, config_manager: ConfigManager):
        """
        Initialize reconstruction pipeline.
        
        Args:
            project_dir: Path to extracted Quest data
            config_manager: Configuration manager
        """
        self.project_dir = Path(project_dir)
        self.config = config_manager
        self.reconstructor = QuestReconstructor(config_manager) if HAS_OPEN3D else None
        
        # Load frames.json
        frames_json = self.project_dir / "frames.json"
        if not frames_json.exists():
            raise FileNotFoundError(f"frames.json not found in {project_dir}")
        
        with open(frames_json, 'r') as f:
            self.data = json.load(f)
        
        self.frames = self.data.get('frames', [])
        self.camera_metadata = self.data.get('camera_metadata', {})
        
    def get_camera_intrinsics(self, camera='left'):
        """
        Extract camera intrinsics from metadata.
        
        Returns:
            3x3 intrinsics matrix
        """
        cam_data = self.camera_metadata.get(camera, {})
        
        # Try to parse intrinsics from Quest metadata
        # The intrinsics are in a nested object: camera_metadata.left.intrinsics
        intrinsics_obj = cam_data.get('intrinsics', {})
        
        # Read from nested intrinsics or use defaults
        fx = intrinsics_obj.get('fx', 867.0)
        fy = intrinsics_obj.get('fy', 867.0)
        cx = intrinsics_obj.get('cx', 640.0)
        cy = intrinsics_obj.get('cy', 640.0)
        
        intrinsics = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ], dtype=np.float64)
        
        return intrinsics
    
    def quaternion_to_matrix(self, quat):
        """
        Convert quaternion (w, x, y, z) to 3x3 rotation matrix.
        
        Args:
            quat: [w, x, y, z] quaternion
            
        Returns:
            3x3 rotation matrix
        """
        w, x, y, z = quat
        
        R = np.array([
            [1 - 2*y**2 - 2*z**2, 2*x*y - 2*w*z, 2*x*z + 2*w*y],
            [2*x*y + 2*w*z, 1 - 2*x**2 - 2*z**2, 2*y*z - 2*w*x],
            [2*x*z - 2*w*y, 2*y*z + 2*w*x, 1 - 2*x**2 - 2*y**2]
        ])
        
        return R
    
    def build_pose_matrix(self, position, rotation):
        """
        Build 4x4 pose matrix from position and quaternion.
        
        Args:
            position: [x, y, z]
            rotation: [w, x, y, z] quaternion
            
        Returns:
            4x4 pose matrix (camera to world)
        """
        R = self.quaternion_to_matrix(rotation)
        t = np.array(position).reshape(3, 1)
        
        pose = np.eye(4)
        pose[:3, :3] = R
        pose[:3, 3] = t.flatten()
        
        return pose
    
    def run_reconstruction(
        self, 
        on_progress=None, 
        on_log=None,
        camera='left',
        frame_interval=1
    ):
        """
        Run the reconstruction process.
        
        Args:
            on_progress: Callback(percentage: int)
            on_log: Callback(message: str)
            camera: Which camera to use ('left' or 'right')
            frame_interval: Process every N-th frame (1 = all frames)
            
        Returns:
            Dictionary with reconstruction results
        """
        if not self.reconstructor:
            if on_log:
                on_log("ERROR: Open3D not available. Cannot run reconstruction.")
            return None
        
        if on_log:
            on_log(f"Starting reconstruction with {len(self.frames)} frames...")
            on_log(f"Using camera: {camera}")
            on_log(f"Frame interval: {frame_interval}")
        
        
    def get_camera_extrinsics(self, camera='left'):
        """
        Get 4x4 homogenous matrix for Head-to-Camera transform.
        """
        # Default extrinsics (approximate Quest 3 IPD ~64mm)
        # Left eye is roughly -32mm on X, Right is +32mm
        # TODO: Read from metadata if available (currently falling back to defaults)
        
        offset_x = -0.032 if camera == 'left' else 0.032
        
        # Identity rotation (assuming cameras are parallel to head forward)
        # In reality, they might be canted (toed-in).
        # Metadata check:
        cam_data = self.camera_metadata.get(camera, {})
        translation = cam_data.get('translation', [offset_x, 0, 0])
        rotation = cam_data.get('rotation_quat', [1, 0, 0, 0]) # w, x, y, z
        
        # If metadata has translation, use it
        if 'translation' in cam_data:
             t = np.array(translation)
        else:
             t = np.array([offset_x, 0, 0])
             
        # Rotation
        # If metadata has rotation, convert it. Otherwise Identity.
        # But for now, let's stick to simple Translation offset default.
        
        R = np.eye(3) # Identity
        
        H = np.eye(4)
        H[:3, :3] = R
        H[:3, 3] = t
        
        return H

    def run_reconstruction(
        self, 
        on_progress=None, 
        on_log=None,
        camera='left',
        frame_interval=1
    ):
        """
        Run the reconstruction process.
        
        Args:
            on_progress: Callback(percentage: int)
            on_log: Callback(message: str)
            camera: 'left', 'right', or 'both'
            frame_interval: Process every N-th frame (1 = all frames)
            
        Returns:
            Dictionary with reconstruction results
        """
        if not self.reconstructor:
            if on_log:
                on_log("ERROR: Open3D not available. Cannot run reconstruction.")
            return None
        
        if on_log:
            on_log(f"Starting reconstruction with {len(self.frames)} frames...")
            on_log(f"Using camera mode: {camera}")
            on_log(f"Frame interval: {frame_interval}")
            
        cameras_to_process = ['left', 'right'] if camera == 'both' else [camera]
        
        intrinsics_map = {cam: self.get_camera_intrinsics(cam) for cam in cameras_to_process}
        extrinsics_map = {cam: self.get_camera_extrinsics(cam) for cam in cameras_to_process}
        
        if on_log:
            for cam in cameras_to_process:
                ints = intrinsics_map[cam]
                on_log(f"[{cam}] Intrinsics: fx={ints[0,0]:.1f}, cx={ints[0,2]:.1f}")
                exts = extrinsics_map[cam][:3, 3]
                on_log(f"[{cam}] Extrinsics Offset: {exts}")
        
        # Process frames
        processed_count = 0
        failed_count = 0
        
        for i, frame in enumerate(self.frames[::frame_interval]):
            if on_progress:
                progress = int((i + 1) / len(self.frames[::frame_interval]) * 100)
                on_progress(progress)
            
            if on_log and i % max(1, len(self.frames) // 20) == 0:
                on_log(f"Processing frame set {i+1}/{len(self.frames[::frame_interval])}...")
            
            # Identify Head Pose
            head_pose = self.build_pose_matrix(
                frame['pose']['position'],
                frame['pose']['rotation']
            )
            
            # Process each camera
            for cam in cameras_to_process:
                try:
                    rgb, depth = QuestImageProcessor.process_quest_frame(
                        str(self.project_dir),
                        frame,
                        camera=cam
                    )
                    
                    if rgb is None or depth is None:
                        # Only check logging for failures if single camera mode or significant failure
                        if on_log and failed_count < 5: 
                            on_log(f"⚠ [{cam}] Frame {i} failed: RGB={rgb is not None}, Depth={depth is not None}")
                        failed_count += 1
                        continue
                        
                    # Calculate Camera World Pose
                    # T_cam_world = T_head_world @ T_head_to_cam
                    T_head_cam = extrinsics_map[cam]
                    cam_pose = head_pose @ T_head_cam
                    
                    # Integrate
                    self.reconstructor.integrate_frame(
                        rgb, 
                        depth, 
                        intrinsics_map[cam], 
                        cam_pose
                    )
                    processed_count += 1
                    
                except Exception as e:
                    if on_log and failed_count < 10:
                        on_log(f"Error processing {cam} frame {i}: {str(e)[:100]}")
                    failed_count += 1
        
        if on_log:
            on_log(f"Integration complete!")
            on_log(f"  Processed: {processed_count} frames")
            on_log(f"  Failed: {failed_count} frames")
            on_log("Extracting mesh...")
        
        # Extract mesh
        mesh = self.reconstructor.extract_mesh()
        
        if on_log:
            if hasattr(mesh, 'vertices'):
                on_log(f"✓ Mesh extracted: {len(mesh.vertices)} vertices")
                
                # Save Mesh
                export_config = self.config.get("export") if self.config else {}
                fmt = export_config.get("format", "obj")
                save_mesh = export_config.get("save_mesh", True)
                
                if save_mesh:
                    output_path = self.project_dir / f"reconstruction.{fmt}"
                    on_log(f"Saving mesh to {output_path}...")
                    try:
                        # Open3D supports .ply, .obj, .glb, .gltf natively
                        o3d.io.write_triangle_mesh(str(output_path), mesh)
                        on_log(f"✓ Saved successfully.")
                        
                        # Generate Thumbnail
                        try:
                            on_log("Generating thumbnail...")
                            vis = o3d.visualization.Visualizer()
                            vis.create_window(visible=False, width=640, height=480)
                            vis.add_geometry(mesh)
                            vis.poll_events()
                            vis.update_renderer()
                            thumb_path = self.project_dir / "thumbnail.png"
                            vis.capture_screen_image(str(thumb_path), do_render=True)
                            vis.destroy_window()
                            on_log(f"✓ Thumbnail saved: {thumb_path.name}")
                        except Exception as e:
                            on_log(f"⚠ Thumbnail generation failed: {e}")
                            
                    except Exception as e:
                        on_log(f"ERROR saving mesh: {e}")
            else:
                on_log("⚠ Mesh extraction failed")
        
        return {
            'mesh': mesh,
            'processed_frames': processed_count,
            'failed_frames': failed_count
        }


class AsyncQuestReconstruction(Thread):
    """Background thread for Quest reconstruction."""
    
    def __init__(self, project_dir, config_manager, on_progress=None, on_finished=None, on_error=None, on_log=None):
        super().__init__(daemon=True)
        self.project_dir = project_dir
        self.config_manager = config_manager
        self.on_progress = on_progress
        self.on_finished = on_finished
        self.on_error = on_error
        self.on_log = on_log
        
    def run(self):
        try:
            pipeline = QuestReconstructionPipeline(self.project_dir, self.config_manager)
            result = pipeline.run_reconstruction(
                on_progress=self.on_progress,
                on_log=self.on_log,
                camera='left',
                frame_interval=5  # Process every 5th frame for speed
            )
            
            if self.on_finished:
                self.on_finished(result)
                
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            if self.on_log:
                self.on_log(f"ERROR: {str(e)}")
