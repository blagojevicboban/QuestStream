"""Quest-specific 3D reconstruction pipeline."""

import json
import numpy as np
from pathlib import Path
from threading import Thread
from datetime import datetime

from .quest_image_processor import QuestImageProcessor
from .reconstruction import QuestReconstructor, HAS_OPEN3D, o3d
from .config_manager import ConfigManager
from .quest_reconstruction_utils import (
    Transforms, CoordinateSystem, compute_depth_camera_params, convert_depth_to_linear
)


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
        
    def get_camera_intrinsics(self, camera='left', depth_info=None, debug=False):
        """
        Extract camera intrinsics from metadata or use updated info.
        
        Args:
            camera: 'left' or 'right'
            depth_info: Optional dict with 'fov_...' tangents and 'width'/'height'
            debug: If True, print debug information
        
        Returns:
            3x3 intrinsics matrix
        """
        fx, fy, cx, cy = 0, 0, 0, 0
        computed_from_fov = False

        if depth_info:
            # Use accurate intrinsics from frame metadata
            w = depth_info.get('width', 0)
            h = depth_info.get('height', 0)
            l = depth_info.get('fov_left', 0)
            r = depth_info.get('fov_right', 0)
            t = depth_info.get('fov_top', 0)
            b = depth_info.get('fov_down', 0)
            
            if debug:
                print(f"  FOV tangents: L={l:.4f}, R={r:.4f}, T={t:.4f}, B={b:.4f}, W={w}, H={h}")
            
            if w > 0 and h > 0 and (l + r) > 0.01 and (t + b) > 0.01:
                fx_temp, fy_temp, cx_temp, cy_temp = compute_depth_camera_params(l, r, t, b, w, h)
                
                # Validate computed values - reject if suspiciously low
                # Quest 3 depth camera typically has focal length around 800-900 pixels
                if fx_temp > 300 and fy_temp > 300:
                    fx, fy, cx, cy = fx_temp, fy_temp, cx_temp, cy_temp
                    computed_from_fov = True
                elif debug:
                    print(f"  WARNING: Computed intrinsics rejected (FX={fx_temp:.1f}, FY={fy_temp:.1f})")
        
        if fx == 0:
            # Fallback to global metadata or defaults
            cam_data = self.camera_metadata.get(camera, {})
            intrinsics_obj = cam_data.get('intrinsics', {})
            
            fx = intrinsics_obj.get('fx', 867.0)
            fy = intrinsics_obj.get('fy', 867.0)
            cx = intrinsics_obj.get('cx', 640.0)
            cy = intrinsics_obj.get('cy', 640.0)
            
            if debug:
                print(f"  Using fallback intrinsics: FX={fx:.1f}, FY={fy:.1f}")
        elif debug:
            print(f"  Using computed intrinsics: FX={fx:.1f}, FY={fy:.1f}")
        
        intrinsics = np.array([
            [fx, 0, cx],
            [0, fy, cy],
            [0, 0, 1]
        ], dtype=np.float64)
        
        return intrinsics
    
    def get_camera_extrinsics(self, camera='left'):
        """
        Get 4x4 homogenous matrix for Head-to-Camera transform (Unity Coordinates).
        """
        cam_data = self.camera_metadata.get(camera, {})
        
        # Translation
        offset_x = -0.032 if camera == 'left' else 0.032
        translation = list(cam_data.get('translation', [offset_x, 0, 0]))
        
        # Apply reference project logic: transl[2] *= -1
        if len(translation) >= 3:
            translation[2] *= -1
        t = np.array(translation)
        
        # Rotation
        rotation = cam_data.get('rotation', None)
        if rotation is None:
             rotation = cam_data.get('rotation_quat', [0, 0, 0, 1])

        clean_rot = np.array(rotation)
        
        if len(clean_rot) >= 4:
            # Match reference logic from image_data_io.py:
            # qx = -rot_quat[0]
            # qy = -rot_quat[1]
            # qz = rot_quat[2]
            # qw = rot_quat[3]
            qx = -clean_rot[0]
            qy = -clean_rot[1]
            qz = clean_rot[2]
            qw = clean_rot[3]
            
            from scipy.spatial.transform import Rotation as R
            rot = R.from_quat((qx, qy, qz, qw)).inv()
            
            # Apply 180-degree rotation to align Android camera pose with HMD world
            # rot *= R.from_euler('x', np.pi)
            rot = rot * R.from_euler('x', np.pi)
            
            mat = rot.as_matrix()
        else:
            mat = np.eye(3)
        
        H = np.eye(4)
        H[:3, :3] = mat
        H[:3, 3] = t
        
        return H

    def run_reconstruction(
        self, 
        on_progress=None, 
        on_log=None,
        on_frame=None,
        is_cancelled=None,
        camera='left',
        frame_interval=1,
        start_frame=0,
        end_frame=None
    ):
        """
        Run the reconstruction process.
        """
        if not self.reconstructor:
            if on_log:
                on_log("ERROR: Open3D not available. Cannot run reconstruction.")
            return None
        
        total_frames = len(self.frames)
        if end_frame is None or end_frame >= total_frames:
            end_frame = total_frames - 1
            
        frames_subset = self.frames[start_frame : end_frame + 1]
        
        if on_log:
            on_log(f"Starting reconstruction with {len(frames_subset)} frames (Range: {start_frame}-{end_frame})...")
            on_log(f"Using camera mode: {camera}")
            
        cameras_to_process = ['left', 'right'] if camera == 'both' else [camera]
        
        # Pre-calculate extrinsics (Head-to-Camera) in Unity space
        extrinsics_map_unity = {cam: self.get_camera_extrinsics(cam) for cam in cameras_to_process}
        
        processed_count = 0
        failed_count = 0
        
        processing_frames = frames_subset[::frame_interval]
        total_processing = len(processing_frames)
        
        for i, frame in enumerate(processing_frames):
            if is_cancelled and is_cancelled():
                if on_log: on_log("Reconstruction CANCELLED by user.")
                return None
                
            current_real_index = start_frame + i * frame_interval
            
            if on_frame: on_frame(current_real_index)
            if on_progress: on_progress(int((i + 1) / total_processing * 100))
            if on_log and i % max(1, total_processing // 20) == 0:
                on_log(f"Processing frame set {i+1}/{total_processing}...")
            
            # Get Head Pose (Unity World)
            # frame['pose']['position'] -> [x, y, z]
            # frame['pose']['rotation'] -> [x, y, z, w] ideally
            head_pos = np.array(frame['pose']['position'])
            head_rot = np.array(frame['pose']['rotation'])
            
            # Construct Head Matrix (Unity)
            from scipy.spatial.transform import Rotation as R
            head_R = R.from_quat(head_rot).as_matrix()
            head_T = np.eye(4)
            head_T[:3, :3] = head_R
            head_T[:3, 3] = head_pos
            
            for cam in cameras_to_process:
                try:
                    # FIX 1: Map 'color' option to 'left' camera (Quest RGB is left camera)
                    actual_cam = 'left' if cam == 'color' else cam
                    
                    rgb, depth, depth_info = QuestImageProcessor.process_quest_frame(
                        str(self.project_dir),
                        frame,
                        camera=actual_cam
                    )
                    
                    if rgb is None or depth is None:
                        failed_count += 1
                        continue
                     
                    # 1. Get accurate intrinsics
                    intrinsics = self.get_camera_intrinsics(cam, depth_info, debug=(i < 5))
                    
                    # DEBUG: Check raw depth BEFORE linearization
                    if i < 5:
                        raw_valid = depth[depth > 0]
                        if len(raw_valid) > 0:
                            msg = f"  RAW Depth: min={np.min(raw_valid):.4f}, max={np.max(raw_valid):.4f}, mean={np.mean(raw_valid):.4f}, pixels={len(raw_valid)}"
                            print(msg)
                            if on_log: on_log(msg)
                        else:
                            msg = "  RAW Depth: NO VALID PIXELS (all zeros!)"
                            print(msg)
                            if on_log: on_log(msg)
                    
                    # 2. Linearize depth
                    if depth_info:
                        near = depth_info.get('near_z', 0.1)
                        far = depth_info.get('far_z', 3.0)
                        
                        # DEBUG: Log linearization parameters
                        if i < 5:
                            msg = f"  Linearizing depth: near={near:.2f}, far={far:.2f}"
                            print(msg)
                            if on_log: on_log(msg)
                        
                        depth_linear = convert_depth_to_linear(depth, near, far)
                    else:
                        # Fallback: assume depth is already linear or use defaults
                        # If raw depth was loaded as float32, it's likely non-linear NDC-like if from Quest?
                        # Or it might be meters. Existing code assumed meters.
                        # Let's assume meters to be safe for legacy support.
                        depth_linear = depth
                    
                    # FIX 2a: Filter depth range for room scanning (remove noise)
                    # TEMPORARILY DISABLED - too aggressive, removes all pixels
                    # depth_linear[depth_linear < 0.2] = 0.0  # Too close (< 20cm)
                    # depth_linear[depth_linear > 2.5] = 0.0  # Too far for small room (> 2.5m)
                    
                    # DEBUG: Log depth distribution to see what values we have
                    if i < 5:
                        valid_depth = depth_linear[depth_linear > 0]
                        if len(valid_depth) > 0:
                            d_min, d_max, d_mean = np.min(valid_depth), np.max(valid_depth), np.mean(valid_depth)
                            msg = f"  Depth stats: min={d_min:.2f}m, max={d_max:.2f}m, mean={d_mean:.2f}m, pixels={len(valid_depth)}"
                            print(msg)
                            if on_log: on_log(msg)
                    
                    # FIX 2b: Apply bilateral filtering for smoother depth
                    # TEMPORARILY DISABLED - testing without filtering first
                    # if depth_linear.max() > 0:
                    #     depth_linear = cv2.bilateralFilter(
                    #         depth_linear.astype(np.float32), 
                    #         d=5, 
                    #         sigmaColor=0.1, 
                    #         sigmaSpace=0.1
                    #     )
                        
                    # 3. Compute Camera Pose in Unity World
                    # T_cam_world = T_head_world @ T_cam_head
                    unity_camera_pose = head_T @ extrinsics_map_unity[cam]
                    
                    # 4. Convert to Open3D Coordinate System
                    # Create Transforms object with this single pose
                    # Extract translation and rotation from the combined matrix
                    cam_pos_unity = unity_camera_pose[:3, 3]
                    cam_rot_unity = R.from_matrix(unity_camera_pose[:3, :3]).as_quat()
                    
                    unity_transform = Transforms(
                        coordinate_system=CoordinateSystem.UNITY,
                        positions=np.array([cam_pos_unity]),
                        rotations=np.array([cam_rot_unity]) # [x, y, z, w]
                    )
                    
                    open3d_transform = unity_transform.convert_coordinate_system(
                        CoordinateSystem.OPEN3D, 
                        is_camera=True # <--- CRITICAL FIX: Treat as camera to apply correct Basis change
                    )
                    
                    # Get Camera-to-World matrix in Open3D space
                    # indexing [0] because we wrapped in array
                    final_pose_open3d = open3d_transform.extrinsics_cw[0]
                    # Integation Debug Check
                    if i < 20 or (i % 10 == 0):
                         t_min, t_max = np.min(depth_linear), np.max(depth_linear)
                         p_trans = final_pose_open3d[:3, 3]
                         curr_fx = intrinsics[0,0]
                         msg = f"DEBUG Frame {i}: Depth[{t_min:.3f}, {t_max:.3f}] PoseT{p_trans} FX={curr_fx:.1f}"
                         if on_log: on_log(msg)
                         print(msg) 
                    
                    # Safety Check: Skip frames where intrinsics are wildy different (e.g. uninitialized 144.4 vs expected ~800)
                    curr_fx = intrinsics[0,0]
                    if curr_fx < 400: 
                        warn = f"WARNING: Skipping Frame {i} due to suspicious intrinsics (FX={curr_fx:.1f})"
                        if on_log: on_log(warn)
                        print(warn)
                        continue

                    if np.any(np.isnan(final_pose_open3d)) or np.any(np.isinf(final_pose_open3d)):
                        err_msg = f"ERROR: Invalid Pose detected in frame {i}!"
                        if on_log: on_log(err_msg)
                        print(err_msg)
                        continue

                    # Integrate
                    self.reconstructor.integrate_frame(
                        rgb, 
                        depth_linear, 
                        intrinsics, 
                        final_pose_open3d
                    )
                    processed_count += 1
                    
                except Exception as e:
                    if on_log and failed_count < 5:
                        on_log(f"Error processing {cam} frame {i}: {str(e)}")
                    failed_count += 1
        
        if on_log:
            on_log(f"Integration complete! Processed: {processed_count}, Failed: {failed_count}")
            on_log("Extracting mesh...")
        
        mesh = self.reconstructor.extract_mesh()
        
        output_path = None
        if on_log:
            if hasattr(mesh, 'vertices'):
                on_log(f"✓ Mesh extracted: {len(mesh.vertices)} vertices")
                
                export_config = self.config.get("export") if self.config else {}
                fmt = export_config.get("format", "obj")
                
                if export_config.get("save_mesh", True):
                    export_dir = self.project_dir / "Export"
                    export_dir.mkdir(exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = export_dir / f"reconstruction_{timestamp}.{fmt}"
                    
                    on_log(f"Saving mesh to {output_path}...")
                    try:
                        o3d.io.write_triangle_mesh(str(output_path), mesh)
                        on_log(f"✓ Saved successfully")
                        
                        # Thumbnail
                        try:
                            vis = o3d.visualization.Visualizer()
                            vis.create_window(visible=False, width=640, height=480)
                            vis.add_geometry(mesh)
                            vis.poll_events()
                            vis.update_renderer()
                            thumb_path = export_dir / f"thumbnail_{timestamp}.png"
                            vis.capture_screen_image(str(thumb_path), do_render=True)
                            latest_thumb = self.project_dir / "thumbnail.png"
                            import shutil
                            shutil.copy2(str(thumb_path), str(latest_thumb))
                            vis.destroy_window()
                        except: pass
                        
                    except Exception as e:
                        on_log(f"ERROR saving mesh: {e}")
            else:
                on_log("⚠ Mesh extraction failed")
        
        return {
            'mesh': mesh,
            'processed_frames': processed_count,
            'failed_frames': failed_count,
            'output_path': str(output_path) if output_path and output_path.exists() else None
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
                frame_interval=5  # Default interval
            )
            
            if self.on_finished:
                self.on_finished(result)
                
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            if self.on_log:
                self.on_log(f"ERROR: {str(e)}")
