"""
Main GUI module for QuestStream 3D Processor.
Handles user interaction, thread management, and UI rendering using Flet.
"""

import os
import json
import threading
import time
import numpy as np
import flet as ft
from datetime import datetime

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    HAS_OPEN3D = False
    o3d = None

# Lazy import cv2 to avoid file locking during NerfStudio installation
# cv2 will be imported on-demand when actually needed
cv2 = None

def _ensure_cv2():
    """Lazy-load cv2 module when needed."""
    global cv2
    if cv2 is None:
        import cv2 as cv2_module
        cv2 = cv2_module
    return cv2

import base64
from .config_manager import ConfigManager
from .ingestion import ZipValidator, AsyncExtractor
from .reconstruction import QuestReconstructor
from .image_processing import yuv_to_rgb, filter_depth
from .quest_image_processor import QuestImageProcessor

class ReconstructionThread(threading.Thread):
    """
    Worker thread that handles the 3D reconstruction process for Quest data.
    Uses QuestReconstructionPipeline to process YUV images and raw depth.
    """
    def __init__(self, data_dir, config_manager, on_progress=None, on_status=None, on_log=None, on_finished=None, on_error=None, on_frame=None, start_frame=0, end_frame=None):
        super().__init__()
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_log = on_log
        self.on_finished = on_finished
        self.on_error = on_error
        self.on_frame = on_frame
        self.start_frame = start_frame
        self.end_frame = end_frame
        self._is_running = True

    def run(self):
        try:
            from .quest_reconstruction_pipeline import QuestReconstructionPipeline
            
            if self.on_status:
                self.on_status("Initializing Quest Reconstruction Pipeline...")
            if self.on_log:
                self.on_log("Initializing Quest Reconstruction Pipeline...")
            
            # Create pipeline
            pipeline = QuestReconstructionPipeline(self.data_dir, self.config_manager)
            
            # Run reconstruction
            result = pipeline.run_reconstruction(
                on_progress=lambda p: (
                    self.on_progress(p / 100.0) if self.on_progress else None,
                    self.on_status(f"Processing: {p}%") if self.on_status else None
                ),
                on_log=self.on_log,
                on_frame=self.on_frame,
                is_cancelled=lambda: not self._is_running, # Pass cancellation check
                camera=self.config_manager.get("reconstruction.camera", "left"),
                frame_interval=int(self.config_manager.get("reconstruction.frame_interval", 5)),
                start_frame=self.start_frame,
                end_frame=self.end_frame
            )
            
            if result and result.get('mesh'):
                if self.on_log:
                    self.on_log(f"✓ Reconstruction complete!")
                    if hasattr(result['mesh'], 'vertices'):
                        self.on_log(f"  Vertices: {len(result['mesh'].vertices)}")
                if self.on_finished:
                    self.on_finished(result) # Pass full result dict
            else:
                if self.on_error:
                    self.on_error("Reconstruction failed - no mesh generated")
        
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))
            if self.on_log:
                self.on_log(f"ERROR: {str(e)}")


    def stop(self):
        self._is_running = False

def main(page: ft.Page):
    page.title = "QuestGear 3D Studio"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1024
    page.window_height = 768
    
    config_manager = ConfigManager()
    
    # State
    temp_dir = None
    current_mesh = None
    frames_data = [] # List of frame objects
    current_extractor = None # Tracking for cancellation
    pending_zip_path = None # For confirmation dialog
    
    # Controls
    status_text = ft.Text("Ready")
    progress_bar = ft.ProgressBar(value=0, visible=False)
    log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    
    # Frame Selection Controls
    preview_img = ft.Image(fit=ft.ImageFit.CONTAIN, visible=False, expand=True)
    frame_range_slider = ft.RangeSlider(
        min=0, max=100, 
        start_value=0, end_value=100,
        label="{value}",
        visible=False,
        disabled=True
    )
    frame_range_label = ft.Text("Frame Range: -", visible=False)
    
    # Splitter Handling
    video_section_height = 300
    
    def on_splitter_drag(e: ft.DragUpdateEvent):
        nonlocal video_section_height
        video_section_height += e.delta_y
        # Clamp height
        if video_section_height < 150: video_section_height = 150
        if video_section_height > 600: video_section_height = 600
        
        video_container.height = video_section_height
        page.update()

    splitter = ft.GestureDetector(
        on_vertical_drag_update=on_splitter_drag,
        mouse_cursor=ft.MouseCursor.RESIZE_UP_DOWN,
        content=ft.Container(
            bgcolor=ft.Colors.GREY_800,
            height=12,
            content=ft.Icon(ft.Icons.DRAG_HANDLE, size=10, color=ft.Colors.GREY_400),
            alignment=ft.alignment.center,
            border_radius=4,
            tooltip="Drag to resize"
        )
    )

    def update_frame_preview(index):
        if not frames_data or index < 0 or index >= len(frames_data):
            return
            
        try:
            # Load frame using QuestImageProcessor
            frame_info = frames_data[index]
            camera = config_manager.get("reconstruction.camera", "left")
            if camera == 'both': camera = 'left' # Preview left for stereo
            
            rgb, _, _ = QuestImageProcessor.process_quest_frame(
                temp_dir, frame_info, camera=camera
            )
            
            if rgb is not None:
                # Ensure cv2 is loaded before use
                cv2 = _ensure_cv2()
                # Convert to base64 for Flet
                is_success, buffer = cv2.imencode(".jpg", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                if is_success:
                    b64_img = base64.b64encode(buffer).decode("utf-8")
                    preview_img.src_base64 = b64_img
                    preview_img.update()
        except Exception as e:
            print(f"Preview error: {e}")

    last_range_start = -1
    last_range_end = -1

    def on_range_change(e):
        nonlocal last_range_start, last_range_end
        start = int(e.control.start_value)
        end = int(e.control.end_value)
        
        frame_range_label.value = f"Frame Range: {start} - {end} (Total: {end - start + 1})"
        frame_range_label.update()
        
        # Determine which handle moved to update preview
        if abs(start - last_range_start) > 0:
            update_frame_preview(start)
        elif abs(end - last_range_end) > 0:
            update_frame_preview(end)
            
        last_range_start = start
        last_range_end = end

    frame_range_slider.on_change = on_range_change

    btn_process = ft.ElevatedButton("Start Reconstruction", disabled=True)
    btn_visualize = ft.ElevatedButton("Visualizer (External)", disabled=True)
    
    # Selection buttons (declared here as variables so they can be disabled)
    btn_load_zip = ft.ElevatedButton("Load ZIP", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(
        dialog_title="Open Quest Capture ZIP",
        allowed_extensions=["zip"],
        initial_directory="D:\\METAQUEST" if os.path.exists("D:\\METAQUEST") else None
    ))
    btn_load_folder = ft.ElevatedButton("Load Folder", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: folder_picker.get_directory_path(
        dialog_title="Open Extracted Quest Data Folder",
        initial_directory="D:\\METAQUEST" if os.path.exists("D:\\METAQUEST") else None
    ))
    
    def stop_zip_extraction(e):
        nonlocal current_extractor
        if current_extractor:
            add_log("STOP signal sent to extractor...")
            current_extractor.stop()
            btn_stop_zip.visible = False
            status_text.value = "Stopping..."
            page.update()

    btn_stop_zip = ft.ElevatedButton(
        "Stop", 
        icon=ft.Icons.STOP, 
        visible=False, 
        on_click=stop_zip_extraction,
        bgcolor=ft.Colors.RED_700,
        color=ft.Colors.WHITE
    )

    def add_log(msg):
        now = datetime.now().strftime("%H:%M:%S")
        log_list.controls.append(ft.Text(f"[{now}] {msg}", font_family="Consolas", size=12))
        if len(log_list.controls) > 100:
            log_list.controls.pop(0)
        page.update()

    def get_memory_usage():
        """Get current memory usage in MB using a more robust Windows approach."""
        import os, subprocess, re
        try:
            pid = os.getpid()
            # use wmic for cleaner numeric output if possible, or stick to tasklist with better regex
            cmd = f'tasklist /FI "PID eq {pid}" /NH /FO CSV'
            output = subprocess.check_output(cmd, shell=True).decode(errors='ignore')
            
            # Regex to find the memory value which is usually the last field like "123,456 K" or "123.456 K"
            matches = re.findall(r'"([^"]+)"', output)
            if len(matches) >= 5:
                mem_str = matches[4] # The 5th field is Mem Usage
                # Remove anything that isn't a digit (handles commas, dots, spaces, and 'K')
                digits_only = re.sub(r'[^\d]', '', mem_str)
                if digits_only:
                    return int(digits_only) / 1024.0
            
            # Fallback to a simpler tasklist output if CSV fails
            cmd_alt = f'tasklist /FI "PID eq {pid}" /NH'
            output_alt = subprocess.check_output(cmd_alt, shell=True).decode(errors='ignore')
            # Look for a number followed by ' K'
            match = re.search(r'(\d[\d,.\s]*)\s*K', output_alt)
            if match:
                digits_only = re.sub(r'[^\d]', '', match.group(1))
                return int(digits_only) / 1024.0
        except:
            pass
        return 0.0
            
    # Memory Monitor
    mem_text = ft.Text("RAM: -- MB", size=12, color=ft.Colors.GREY_400)
    
    def update_memory_loop():
        while True:
            if page.route: # Check if page is active
                mem = get_memory_usage()
                mem_text.value = f"RAM: {mem:.1f} MB"
                page.update()
            time.sleep(2)
            
    threading.Thread(target=update_memory_loop, daemon=True).start()

    def show_msg(text):
        page.snack_bar = ft.SnackBar(content=ft.Text(text))
        page.snack_bar.open = True
        page.update()

    def load_frames_ui(frames_json_path):
        nonlocal frames_data
        try:
            with open(frames_json_path, 'r') as f:
                data = json.load(f)
                frames_data = data.get('frames', [])
                
                if frames_data:
                    count = len(frames_data)
                    frame_range_slider.min = 0
                    frame_range_slider.max = count - 1
                    frame_range_slider.start_value = 0
                    frame_range_slider.end_value = count - 1
                    frame_range_slider.divisions = count
                    frame_range_slider.visible = True
                    frame_range_slider.disabled = False
                    
                    frame_range_label.value = f"Frame Range: 0 - {count-1} (Total: {count})"
                    frame_range_label.visible = True
                    
                    preview_img.visible = True
                    
                    # Initial Preview
                    update_frame_preview(0)
                    
                    add_log(f"Loaded {count} frames.")
        except Exception as e:
            add_log(f"Error loading frames info: {e}")

    def on_img_load_progress(val):
        progress_bar.value = val / 100.0
        page.update()

    def on_img_load_finished(path):
        nonlocal temp_dir, current_extractor
        temp_dir = path
        current_extractor = None
        progress_bar.visible = False
        btn_stop_zip.visible = False
        btn_load_zip.disabled = False
        btn_load_folder.disabled = False
        status_text.value = f"Extracted to {path}"
        add_log(f"Extraction complete: {path}")
        
        # Check if this is Quest format (no frames.json)
        frames_json = os.path.join(path, "frames.json")
        if not os.path.exists(frames_json):
            add_log("Quest format detected - converting to frames.json...")
            try:
                from modules.quest_adapter import QuestDataAdapter
                frames_json_path = QuestDataAdapter.adapt_quest_data(path)
                add_log(f"✓ Created frames.json")
                add_log(f"Quest data successfully converted!")
            except Exception as e:
                add_log(f"ERROR converting Quest data: {str(e)}")
                show_msg(f"Failed to convert Quest data: {str(e)}")
                return
        
        # Load frames.json for preview
        load_frames_ui(frames_json)
        
        btn_process.disabled = False
        show_msg("Data loaded successfully.")

    def on_img_load_error(err):
        nonlocal current_extractor
        current_extractor = None
        progress_bar.visible = False
        btn_stop_zip.visible = False
        btn_load_zip.disabled = False
        btn_load_folder.disabled = False
        
        if err == "Stopped":
            status_text.value = "Ready"
            add_log("Extraction safely stopped and cleaned up.")
        else:
            status_text.value = "Extraction Failed"
            add_log(f"Extraction Error: {err}")
            show_msg(f"Error: {err}")
            
        page.update()

    def execute_extraction(file_path):
        nonlocal current_extractor
        status_text.value = "Extracting..."
        progress_bar.visible = True
        progress_bar.value = None
        btn_stop_zip.visible = True
        page.update()
        
        current_extractor = AsyncExtractor(
            file_path,
            on_progress=on_img_load_progress,
            on_finished=on_img_load_finished,
            on_error=on_img_load_error,
            on_log=add_log
        )
        current_extractor.start()

    def load_zip_result(e):
        nonlocal pending_zip_path
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            log_list.controls.clear()
            add_log(f"Selected file: {file_path}")
            
            # Check if extracted folder already exists
            zip_dir = os.path.dirname(file_path)
            zip_name = os.path.splitext(os.path.basename(file_path))[0]
            target_extracted_dir = os.path.join(zip_dir, f"{zip_name}_extracted")
            
            if os.path.exists(target_extracted_dir):
                pending_zip_path = file_path
                overwrite_msg.value = f"Folder '{os.path.basename(target_extracted_dir)}' already exists.\nDo you want to overwrite it?"
                page.open(confirm_dialog)
                return

            status_text.value = "Validating ZIP structure..."
            btn_load_zip.disabled = True
            btn_load_folder.disabled = True
            page.update()
            
            add_log("Starting ZIP validation...")
            valid, msg = ZipValidator.validate(file_path, log_callback=add_log)
            if not valid:
                status_text.value = "Invalid ZIP"
                btn_load_zip.disabled = False
                btn_load_folder.disabled = False
                show_msg(f"Invalid ZIP: {msg}")
                add_log(f"Validation FAILED: {msg}")
                return

            execute_extraction(file_path)

    def handle_confirm_overwrite(e):
        nonlocal pending_zip_path
        page.close(confirm_dialog)
        if pending_zip_path:
            # Re-run the validation and extraction logic
            status_text.value = "Validating ZIP structure..."
            btn_load_zip.disabled = True
            btn_load_folder.disabled = True
            page.update()
            
            add_log("Starting ZIP validation (after confirmation)...")
            valid, msg = ZipValidator.validate(pending_zip_path, log_callback=add_log)
            if not valid:
                status_text.value = "Invalid ZIP"
                btn_load_zip.disabled = False
                btn_load_folder.disabled = False
                show_msg(f"Invalid ZIP: {msg}")
                return
                
            execute_extraction(pending_zip_path)
            pending_zip_path = None

    def handle_cancel_overwrite(e):
        nonlocal pending_zip_path
        pending_zip_path = None
        page.close(confirm_dialog)
        status_text.value = "Extraction cancelled"
        page.update()

    # --- Dialogs and Pickers ---
    
    format_dropdown_start = ft.Dropdown(
        label="Select Export Format",
        value=config_manager.get("export.format", "obj"),
        options=[
            ft.dropdown.Option("ply", "PLY (Point Cloud/Mesh)"),
            ft.dropdown.Option("obj", "OBJ (Standard Mesh)"),
            ft.dropdown.Option("glb", "GLB (Binary GLTF)"),
        ],
        width=300
    )

    def confirm_start_reconstruction(e):
        nonlocal thread
        page.close(reconstruct_format_dialog)
        
        # Save selected format to config for the pipeline to pick up
        config_manager.set("export.format", format_dropdown_start.value)
        
        if not temp_dir:
            return
        
        btn_process.disabled = True
        btn_load_zip.disabled = True
        btn_load_folder.disabled = True
        btn_stop_reconstruct.visible = True
        frame_range_slider.disabled = True # Disable slider during processing
        status_text.value = f"Initializing ({format_dropdown_start.value.upper()})..."
        progress_bar.visible = True
        progress_bar.value = 0
        page.update()
        
        # Get frame range
        start_frame = int(frame_range_slider.start_value) if frame_range_slider.visible else 0
        end_frame = int(frame_range_slider.end_value) if frame_range_slider.visible else None
        
        thread = ReconstructionThread(
            temp_dir,
            config_manager,
            on_progress=on_reconstruct_progress,
            on_status=lambda s: (setattr(status_text, "value", s) or page.update()),
            on_log=add_log,
            on_finished=on_reconstruct_finished,
            on_error=on_reconstruct_error,
            on_frame=update_frame_preview, # Live preview!
            start_frame=start_frame,
            end_frame=end_frame
        )
        thread.start()

    reconstruct_format_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Reconstruction Format"),
        content=ft.Column([
            ft.Text("Choose the output format for the 3D model:"),
            format_dropdown_start
        ], tight=True, height=100),
        actions=[
            ft.TextButton("Start", on_click=confirm_start_reconstruction),
            ft.TextButton("Cancel", on_click=lambda _: page.close(reconstruct_format_dialog)),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    overwrite_msg = ft.Text("")
    confirm_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Folder Exists"),
        content=overwrite_msg,
        actions=[
            ft.TextButton("Yes, Overwrite", on_click=handle_confirm_overwrite),
            ft.TextButton("No, Cancel", on_click=handle_cancel_overwrite),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    file_picker = ft.FilePicker()
    file_picker.on_result = load_zip_result
    page.overlay.append(file_picker)
    page.overlay.append(confirm_dialog) # Register dialog
    page.overlay.append(reconstruct_format_dialog) # Register format dialog

    def load_folder_result(e: ft.FilePickerResultEvent):
        if e.path:
            folder_path = e.path
            log_list.controls.clear()
            add_log(f"Selected folder: {folder_path}")
            
            status_text.value = "Processing folder..."
            page.update()
            
            # Use the folder directly (no extraction needed)
            nonlocal temp_dir
            temp_dir = folder_path
            add_log(f"Using folder: {folder_path}")
            
            # Check if this is Quest format (no frames.json)
            frames_json = os.path.join(folder_path, "frames.json")
            if not os.path.exists(frames_json):
                add_log("Quest format detected - converting to frames.json...")
                try:
                    from modules.quest_adapter import QuestDataAdapter
                    frames_json_path = QuestDataAdapter.adapt_quest_data(folder_path)
                    add_log(f"✓ Created frames.json")
                    add_log(f"Quest data successfully converted!")
                except Exception as e:
                    add_log(f"ERROR converting Quest data: {str(e)}")
                    show_msg(f"Failed to convert Quest data: {str(e)}")
                    status_text.value = "Failed to process folder"
                    page.update()
                    return
            
            status_text.value = f"Loaded folder: {folder_path}"
            
            # Load frames UI
            load_frames_ui(frames_json)
            
            btn_process.disabled = False
            page.update()
            show_msg("Folder loaded successfully.")

    folder_picker = ft.FilePicker()
    folder_picker.on_result = load_folder_result
    page.overlay.append(folder_picker)

    def stop_reconstruction(e):
        nonlocal thread
        if thread:
            add_log("STOP signal sent to reconstruction...")
            thread.stop()
            status_text.value = "Stopping reconstruction..."
            btn_stop_reconstruct.visible = False
            page.update()

    btn_stop_reconstruct = ft.ElevatedButton(
        "Stop", 
        icon=ft.Icons.STOP, 
        visible=False,
        bgcolor=ft.Colors.RED_700,
        color=ft.Colors.WHITE,
        on_click=stop_reconstruction
    )
    
    # Placeholder for thread reference to allow cancellation from button
    thread = None

    def on_reconstruct_progress(val):
        progress_bar.value = val
        page.update()

    thumb_img = ft.Image(src="", width=320, height=240, fit=ft.ImageFit.CONTAIN, visible=False)
    
    def on_reconstruct_finished(result):
        nonlocal current_mesh
        current_mesh = result.get('mesh')
        mesh = current_mesh
        
        # Get actual exported filename and path from result
        full_path = result.get('output_path')
        if full_path:
            filename = os.path.basename(full_path)
        else:
            fmt = config_manager.get("export.format", "obj")
            filename = f"reconstruction.{fmt}"
            full_path = os.path.join(temp_dir, filename) if temp_dir else filename
        
        status_text.value = "Reconstruction Complete"
        btn_process.disabled = False
        btn_visualize.disabled = False
        btn_load_zip.disabled = False
        btn_load_folder.disabled = False
        btn_stop_reconstruct.visible = False
        frame_range_slider.disabled = False # Re-enable slider
        
        add_log(f"✓ Reconstruction finished: {len(mesh.vertices)} vertices.")
        
        # Verify file and update title/logs
        if full_path and os.path.exists(full_path):
            add_log(f"✓ File saved: {filename}")
            add_log(f"  Path: {full_path}")
            page.title = f"QuestGear 3D Studio - {filename}"
            show_msg(f"Success! Model saved to:\n{full_path}")
        else:
            add_log(f"⚠ Mesh extracted but file {filename} not found in {temp_dir}")
            page.title = "QuestGear 3D Studio"
            
        progress_bar.visible = False
        
        # Check for thumbnail
        if temp_dir:
            thumb_path = os.path.join(temp_dir, "thumbnail.png")
            if os.path.exists(thumb_path):
                # Force reload by adding timestamp
                thumb_img.src = f"{thumb_path}?t={time.time()}" 
                thumb_img.visible = True
        
        page.update()

    def on_reconstruct_error(err):
        status_text.value = "Data Loaded" if temp_dir else "Ready"
        btn_process.disabled = False
        btn_visualize.disabled = current_mesh is None
        btn_load_zip.disabled = False
        btn_load_folder.disabled = False
        btn_stop_reconstruct.visible = False
        frame_range_slider.disabled = False # Re-enable slider
        add_log(f"Reconstruction Info: {err}")
        progress_bar.visible = False
        page.update()

    def start_reconstruction(e):
        # This now just opens the format selection dialog
        page.open(reconstruct_format_dialog)

    btn_process.on_click = start_reconstruction

    def show_visualizer(e):
        if not HAS_OPEN3D:
            show_msg("Visualizer not available (Open3D missing).")
            return
            
        if current_mesh and hasattr(current_mesh, 'vertices') and len(current_mesh.vertices) > 0:
            try:
                add_log("Opening 3D Visualizer...")
                vis = o3d.visualization.Visualizer()
                vis.create_window(window_name="QuestStream Result", width=1024, height=768)
                vis.add_geometry(current_mesh)
                
                # Setup render options for better visibility
                opt = vis.get_render_option()
                opt.background_color = np.asarray([0.1, 0.1, 0.1])
                opt.point_size = 2.0
                
                vis.run() # This blocks until window is closed
                vis.destroy_window()
                add_log("Visualizer closed.")
            except Exception as ex:
                add_log(f"Visualizer Error: {ex}")
                show_msg(f"Visualizer Error: {ex}")
        else:
            show_msg("No mesh to visualize.")

    btn_visualize.on_click = show_visualizer

    # Settings Dialog
    voxel_input = ft.TextField(label="Voxel Size (m)", value=str(config_manager.get("reconstruction.voxel_size", 0.02)))
    depth_max_input = ft.TextField(label="Max Depth (m)", value=str(config_manager.get("reconstruction.depth_max", 10.0)))
    frame_int_input = ft.TextField(label="Frame Interval", value=str(config_manager.get("reconstruction.frame_interval", 5)))
    camera_dropdown = ft.Dropdown(
        label="Camera",
        value=config_manager.get("reconstruction.camera", "left"),
        options=[
            ft.dropdown.Option("left", "Left Camera (Grayscale)"),
            ft.dropdown.Option("right", "Right Camera (Grayscale)"),
            ft.dropdown.Option("both", "Stereo (Both)"),
            ft.dropdown.Option("color", "RGB Camera (Color)"),
        ]
    )
    filter_check = ft.Checkbox(label="Filter Depth", value=config_manager.get("reconstruction.use_confidence_filtered_depth", True))
    
    # Post-Processing & Export
    smoothing_input = ft.TextField(label="Smoothing Iterations", value=str(config_manager.get("post_processing.smoothing_iterations", 5)))
    decimation_input = ft.TextField(label="Target Triangles", value=str(config_manager.get("post_processing.decimation_target_triangles", 100000)))
    export_fmt_dropdown = ft.Dropdown(
        label="Export Format",
        value=config_manager.get("export.format", "obj"),
        options=[
            ft.dropdown.Option("ply", "PLY (Standard)"),
            ft.dropdown.Option("obj", "OBJ (Universal)"),
            ft.dropdown.Option("glb", "GLB (Web/AR)"),
        ]
    )

    def save_settings(e):
        try:
            config_manager.set("reconstruction.voxel_size", float(voxel_input.value))
            config_manager.set("reconstruction.depth_max", float(depth_max_input.value))
            config_manager.set("reconstruction.frame_interval", int(frame_int_input.value))
            config_manager.set("reconstruction.camera", camera_dropdown.value)
            config_manager.set("reconstruction.use_confidence_filtered_depth", filter_check.value)
            
            # Post-processing
            config_manager.set("post_processing.smoothing_iterations", int(smoothing_input.value))
            config_manager.set("post_processing.decimation_target_triangles", int(decimation_input.value))
            config_manager.set("export.format", export_fmt_dropdown.value)
            
            page.close(settings_dialog)
            show_msg("Settings saved")
        except ValueError:
            show_msg("Invalid numerical values")

    settings_dialog = ft.AlertDialog(
        title=ft.Text("Settings"),
        content=ft.Column([
            ft.Text("Reconstruction Parameters", weight="bold"),
            voxel_input, 
            depth_max_input, 
            frame_int_input,
            camera_dropdown,
            filter_check,
            ft.Divider(),
            ft.Text("Post-Processing", weight="bold"),
            smoothing_input,
            decimation_input,
            ft.Divider(),
            ft.Text("Export", weight="bold"),
            export_fmt_dropdown
        ], tight=True, scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancel", on_click=lambda _: page.close(settings_dialog)),
            ft.TextButton("Save", on_click=save_settings),
        ],
    )

    def open_settings(e):
        page.open(settings_dialog)

    # ==== NerfStudio Integration ====
    from .nerfstudio_gui import NerfStudioUI
    
    nerfstudio_ui = NerfStudioUI(
        page=page,
        on_log=add_log,
        temp_dir_getter=lambda: temp_dir
    )

    # Layout - Now with Tabs
    page.appbar = ft.AppBar(
        title=ft.Text("QuestGear 3D Studio"),
        bgcolor=ft.Colors.BLUE_800,
        actions=[
            ft.IconButton(icon=ft.Icons.SETTINGS, on_click=open_settings),
        ]
    )

    # TSDF Reconstruction Tab (existing functionality)
    tsdf_tab_content = ft.Container(
        content=ft.Column([
            ft.Row([
                btn_load_zip,
                btn_load_folder,
                btn_stop_zip,
                btn_process,
                btn_stop_reconstruct,
                btn_visualize,
                ft.Container(content=mem_text, padding=10)
            ]),
            video_container := ft.Container(
                content=ft.Column([
                    ft.Text("Video Track & Cropping:", weight="bold"),
                    preview_img,
                    frame_range_slider,
                    frame_range_label
                ]),
                padding=10,
                bgcolor="#252525",
                border_radius=10,
                height=300,
                animate_size=None
            ),
            splitter,
            progress_bar,
            status_text,
            thumb_img,
            ft.Divider(),
            ft.Text("Process Logs:", size=16, weight="bold"),
            ft.Container(
                content=log_list,
                expand=True,
                bgcolor="#1e1e1e",
                border_radius=5,
                padding=10
            )
        ], expand=True),
        expand=True
    )

    # Tab navigation
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(
                text="TSDF Reconstruction",
                icon=ft.Icons.VIEW_IN_AR,
                content=tsdf_tab_content
            ),
            nerfstudio_ui.get_tab(),
        ],
        expand=True
    )

    main_layout = ft.Column([tabs], expand=True)

    page.add(main_layout)
    page.update()
    
    # Start NerfStudio installation check after page is ready
    nerfstudio_ui.start_installation_check()

if __name__ == "__main__":
    ft.app(target=main)
