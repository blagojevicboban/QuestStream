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

from .config_manager import ConfigManager
from .ingestion import ZipValidator, AsyncExtractor
from .reconstruction import QuestReconstructor
from .image_processing import yuv_to_rgb, filter_depth

class ReconstructionThread(threading.Thread):
    """
    Worker thread that handles the 3D reconstruction process for Quest data.
    Uses QuestReconstructionPipeline to process YUV images and raw depth.
    """
    def __init__(self, data_dir, config_manager, on_progress=None, on_status=None, on_log=None, on_finished=None, on_error=None):
        super().__init__()
        self.data_dir = data_dir
        self.config_manager = config_manager
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_log = on_log
        self.on_finished = on_finished
        self.on_error = on_error
        self._is_running = True

    def run(self):
        try:
            from modules.quest_reconstruction_pipeline import QuestReconstructionPipeline
            
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
                camera=self.config_manager.get("reconstruction.camera", "left"),
                frame_interval=int(self.config_manager.get("reconstruction.frame_interval", 5))
            )
            
            if result and result.get('mesh'):
                mesh = result['mesh']
                if self.on_log:
                    self.on_log(f"✓ Reconstruction complete!")
                    if hasattr(mesh, 'vertices'):
                        self.on_log(f"  Vertices: {len(mesh.vertices)}")
                if self.on_finished:
                    self.on_finished(mesh)
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
    page.title = "QuestStream 3D Processor"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1024
    page.window_height = 768
    
    config_manager = ConfigManager()
    
    # State
    temp_dir = None
    current_mesh = None
    
    # Controls
    status_text = ft.Text("Ready")
    progress_bar = ft.ProgressBar(value=0, visible=False)
    log_list = ft.ListView(expand=True, spacing=2, auto_scroll=True)
    
    btn_process = ft.ElevatedButton("Start Reconstruction", disabled=True)
    btn_visualize = ft.ElevatedButton("Visualizer (External)", disabled=True)

    def add_log(msg):
        now = datetime.now().strftime("%H:%M:%S")
        log_list.controls.append(ft.Text(f"[{now}] {msg}", font_family="Consolas", size=12))
        if len(log_list.controls) > 100:
            log_list.controls.pop(0)
        page.update()

    def get_memory_usage():
        """Get current memory usage in MB."""
        import os, subprocess
        try:
            # efficient windows approach
            pid = os.getpid()
            cmd = f'tasklist /FI "PID eq {pid}" /FO CSV /NH'
            output = subprocess.check_output(cmd, shell=True).decode()
            # Parse CSV: "python.exe","55892","Console","1","56,789 K"
            parts = output.split('","')
            if len(parts) > 4:
                mem_str = parts[4].replace('"', '').replace(' K', '').replace(',', '')
                return int(mem_str) / 1024.0
        except:
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

    def on_img_load_progress(val):
        progress_bar.value = val / 100.0
        page.update()

    def on_img_load_finished(path):
        nonlocal temp_dir
        temp_dir = path
        progress_bar.visible = False
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
        
        btn_process.disabled = False
        show_msg("Data loaded successfully.")

    def on_img_load_error(err):
        progress_bar.visible = False
        status_text.value = "Extraction Failed"
        add_log(f"Extraction Error: {err}")
        show_msg(f"Error: {err}")

    def load_zip_result(e):
        if e.files and len(e.files) > 0:
            file_path = e.files[0].path
            log_list.controls.clear()
            add_log(f"Selected file: {file_path}")
            
            status_text.value = "Validating ZIP structure..."
            page.update()
            
            add_log("Starting ZIP validation...")
            valid, msg = ZipValidator.validate(file_path, log_callback=add_log)
            if not valid:
                status_text.value = "Invalid ZIP"
                show_msg(f"Invalid ZIP: {msg}")
                add_log(f"Validation FAILED: {msg}")
                return

            status_text.value = "Extracting..."
            progress_bar.visible = True
            progress_bar.value = None
            page.update()
            
            extractor = AsyncExtractor(
                file_path,
                on_progress=on_img_load_progress,
                on_finished=on_img_load_finished,
                on_error=on_img_load_error,
                on_log=add_log
            )
            extractor.start()

    file_picker = ft.FilePicker()
    file_picker.on_result = load_zip_result
    page.overlay.append(file_picker)

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
            btn_process.disabled = False
            page.update()
            show_msg("Folder loaded successfully.")

    folder_picker = ft.FilePicker()
    folder_picker.on_result = load_folder_result
    page.overlay.append(folder_picker)

    def on_reconstruct_progress(val):
        progress_bar.value = val
        page.update()

    thumb_img = ft.Image(src="", width=320, height=240, fit=ft.ImageFit.CONTAIN, visible=False)
    
    def on_reconstruct_finished(mesh):
        nonlocal current_mesh
        current_mesh = mesh
        status_text.value = "Reconstruction Complete"
        btn_process.disabled = False
        btn_visualize.disabled = False
        add_log(f"Reconstruction finished with {len(mesh.vertices)} vertices.")
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
        status_text.value = "Reconstruction Failed"
        btn_process.disabled = False
        add_log(f"Reconstruction Error: {err}")
        progress_bar.visible = False
        show_msg(f"Error: {err}")

    def start_reconstruction(e):
        if not temp_dir:
            return
        
        btn_process.disabled = True
        status_text.value = "Initializing..."
        progress_bar.visible = True
        progress_bar.value = 0
        page.update()
        
        thread = ReconstructionThread(
            temp_dir,
            config_manager,
            on_progress=on_reconstruct_progress,
            on_status=lambda s: (setattr(status_text, "value", s) or page.update()),
            on_log=add_log,
            on_finished=on_reconstruct_finished,
            on_error=on_reconstruct_error
        )
        thread.start()

    btn_process.on_click = start_reconstruction

    def show_visualizer(e):
        if not HAS_OPEN3D:
            show_msg("Visualizer not available (Open3D missing).")
            return
            
        if current_mesh and hasattr(current_mesh, 'vertices') and len(current_mesh.vertices) > 0:
            o3d.visualization.draw_geometries([current_mesh], window_name="QuestStream Result")
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
            ft.dropdown.Option("left", "Left Camera"),
            ft.dropdown.Option("right", "Right Camera"),
            ft.dropdown.Option("both", "Stereo (Both)"),
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

    # Layout
    page.appbar = ft.AppBar(
        title=ft.Text("QuestStream 3D Processor"),
        bgcolor=ft.Colors.BLUE_800,
        actions=[
            ft.IconButton(icon=ft.Icons.SETTINGS, on_click=open_settings),
        ]
    )

    main_layout = ft.Column([
        ft.Row([
            ft.ElevatedButton("Load ZIP", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(
                dialog_title="Open Quest Capture ZIP",
                allowed_extensions=["zip"],
                initial_directory="D:\\METAQUEST" if os.path.exists("D:\\METAQUEST") else None
            )),
            ft.ElevatedButton("Load Folder", icon=ft.Icons.FOLDER_OPEN, on_click=lambda _: folder_picker.get_directory_path(
                dialog_title="Open Extracted Quest Data Folder",
                initial_directory="D:\\METAQUEST" if os.path.exists("D:\\METAQUEST") else None
            )),
            btn_process,
            btn_visualize,
            ft.Container(content=mem_text, padding=10)
        ]),
        progress_bar,
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
    ], expand=True)

    page.add(main_layout)
    page.update()

if __name__ == "__main__":
    ft.app(target=main)
