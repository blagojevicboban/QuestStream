"""Quest-specific 3D reconstruction pipeline."""

import json
import numpy as np
from pathlib import Path
from threading import Thread
from datetime import datetime

from .quest_image_processor import QuestImageProcessor
from .reconstruction import QuestReconstructor, HAS_OPEN3D, o3d
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

    def convert_pose_unity_to_open3d(self, pose):
        """
        Convert Unity (Left-Handed, Y-Up) pose to Open3D (Right-Handed, Y-Down).
        Transformation:
        1. Flip Z axis (Left-Handed -> Right-Handed check).
        2. Rotate 180 degrees around X axis (Y-Up -> Y-Down).
        Effective Transformation: Scale(1, -1, -1) applied to the pose.
        
        Args:
            pose: 4x4 homogenous matrix (Unity coordinates)
            
        Returns:
            4x4 homogenous matrix (Open3D coordinates)
        """
        # Create scaling matrix S = diag(1, -1, -1, 1)
        # This mirrors Y and Z axes.
        # Why?
        # Unity: +Y Up, +Z Forward (Left Handed)
        # Open3D Camera: -Y Up, -Z Forward (Right Handed)
        # So we flip Y and Z.
        S = np.eye(4)
        S[1, 1] = -1
        S[2, 2] = -1
        
        # Apply transformation: P_new = S * P_old * S
        # Pre-multiply by S flips the world axes.
        # Post-multiply by S flips the local camera axes.
        # We need to transform the camera pose itself.
        
        # Actually, simpler model:
        # Just negate Z position? No, that mirrors the world.
        # Just negate Z axis of rotation? That changes handedness.
        
        # Let's use the standard conversion logic:
        # Open3D = S @ Unity @ S
        return S @ pose @ S
    
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
        Computes T_camera_head (Camera relative to Head).
        """
        cam_data = self.camera_metadata.get(camera, {})
        
        # Translation
        # Default approximate offsets if missing
        offset_x = -0.032 if camera == 'left' else 0.032
        translation = cam_data.get('translation', [offset_x, 0, 0])
        t = np.array(translation)
        
        # Rotation
        # Quest 3 cameras are canted. We must apply this rotation.
        # Format: [w, x, y, z] or [x, y, z, w]?
        # quest_adapter.py reads: floats for rot_w, rot_x...
        # metadata json: usually [w, x, y, z] or [x, y, z, w]
        # Let's check a sample or assume standard Quest [x, y, z, w] or similar?
        # quest_adapter used row['rot_w'] etc for poses.
        # For metadata, it's a list. 
        # Usually Unity JSON is [x, y, z, w].
        # But let's check input list length/order.
        # Standard convention in this pipeline seems to be [w, x, y, z] from build_pose_matrix.
        
        rotation = cam_data.get('rotation', None) # Check keys: 'rotation' or 'rotation_quat'?
        if rotation is None:
             rotation = cam_data.get('rotation_quat', [1, 0, 0, 0]) # Default Identity w=1
             
        # Ensure rotation is [w, x, y, z]
        # If it's 3 elements, it's Euler. If 4, Quat.
        if len(rotation) == 4:
            # Assume [w, x, y, z] based on build_pose_matrix usage
            R = self.quaternion_to_matrix(rotation)
        else:
            R = np.eye(3)
            
        H = np.eye(4)
        H[:3, :3] = R
        H[:3, 3] = t
        
        return H

    def run_reconstruction(
        self, 
        on_progress=None, 
        on_log=None,
        on_frame=None,
        is_cancelled=None, # New parameter
        camera='left',
        frame_interval=1,
        start_frame=0,
        end_frame=None
    ):
        """
        Run the reconstruction process.
        
        Args:
            on_progress: Callback(percentage: int)
            on_log: Callback(message: str)
            on_frame: Callback(frame_index: int) - Called when a frame is processed
            is_cancelled: Callback() -> bool - Check if processing should stop
            camera: 'left', 'right', or 'both'
            frame_interval: Process every N-th frame (1 = all frames)
            start_frame: Start index (inclusive)
            end_frame: End index (inclusive)
            
        Returns:
            Dictionary with reconstruction results
        """
        if not self.reconstructor:
            if on_log:
                on_log("ERROR: Open3D not available. Cannot run reconstruction.")
            return None
        
        total_frames = len(self.frames)
        if end_frame is None or end_frame >= total_frames:
            end_frame = total_frames - 1
            
        # Slice frames based on range
        # Note: end_frame is inclusive from UI, so using +1 for slice
        frames_subset = self.frames[start_frame : end_frame + 1]
        
        if on_log:
            on_log(f"Starting reconstruction with {len(frames_subset)} frames (Range: {start_frame}-{end_frame})...")
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
        
        processing_frames = frames_subset[::frame_interval]
        total_processing = len(processing_frames)
        
        for i, frame in enumerate(processing_frames):
            # Check for cancellation
            if is_cancelled and is_cancelled():
                if on_log:
                    on_log("Reconstruction CANCELLED by user.")
                return None
                
            # Calculate actual global frame index for UI preview
            current_real_index = start_frame + i * frame_interval
            
            if on_frame:
                on_frame(current_real_index)

            if on_progress:
                progress = int((i + 1) / total_processing * 100)
                on_progress(progress)
            
            if on_log and i % max(1, total_processing // 20) == 0:
                on_log(f"Processing frame set {i+1}/{total_processing}...")
            
            # Identify Head Pose from Unity coordinates
            unity_head_pose = self.build_pose_matrix(
                frame['pose']['position'],
                frame['pose']['rotation']
            )
            # DO NOT convert head pose yet. We need to combine it with Unity-space camera offset first.
            
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
                        
                    # Combine Head Pose + Camera Extrinsics
                    # Both are in Unity Frame (Left Handed, Y-Up)
                    # T_cam_world = T_head_world @ T_cam_head
                    
                    camera_extrinsics_unity = extrinsics_map[cam]
                    unity_camera_pose = unity_head_pose @ camera_extrinsics_unity
                    
                    # NOW convert to Open3D frame
                    final_pose = self.convert_pose_unity_to_open3d(unity_camera_pose)
                    
                    # Integrate
                    self.reconstructor.integrate_frame(
                        rgb, 
                        depth, 
                        intrinsics_map[cam], 
                        final_pose
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
                    # Create Export directory
                    export_dir = self.project_dir / "Export"
                    export_dir.mkdir(exist_ok=True)
                    
                    # Generate timestamped filename
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = export_dir / f"reconstruction_{timestamp}.{fmt}"
                    
                    on_log(f"Saving mesh to {output_path}...")
                    try:
                        # Open3D supports .ply, .obj, .glb, .gltf natively
                        success = o3d.io.write_triangle_mesh(str(output_path), mesh)
                        
                        if success and output_path.exists():
                            on_log(f"✓ Saved successfully: {output_path.name}")
                            # Keep output_path defined for return
                        else:
                            on_log(f"ERROR: failed to write mesh to {output_path}")
                            # Remove output_path from locals() logic by ensuring it's not set if failed
                            # Actually, easier to use a dedicated variable for success
                            pass
                        
                        # Generate Thumbnail
                        try:
                            on_log("Generating thumbnail...")
                            vis = o3d.visualization.Visualizer()
                            vis.create_window(visible=False, width=640, height=480)
                            vis.add_geometry(mesh)
                            vis.poll_events()
                            vis.update_renderer()
                            # Save thumbnail in Export folder too
                            thumb_path = export_dir / f"thumbnail_{timestamp}.png"
                            vis.capture_screen_image(str(thumb_path), do_render=True)
                            
                            # Also update the 'latest' thumbnail for GUI preview
                            latest_thumb = self.project_dir / "thumbnail.png"
                            import shutil
                            shutil.copy2(str(thumb_path), str(latest_thumb))
                            
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
            'failed_frames': failed_count,
            'output_path': str(output_path) if 'output_path' in locals() and output_path.exists() else None
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
