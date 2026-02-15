"""
NerfStudio GUI Module
Provides Flet UI components for NerfStudio integration including:
- Installation/Update manager
- Training configuration
- Progress monitoring
- Results viewer
"""

import flet as ft
import subprocess
import threading
import os
from pathlib import Path
from typing import Callable, Optional
from .nerfstudio_trainer import NerfStudioTrainer


class NerfStudioUI:
    """Manages NerfStudio UI components and state."""
    
    def __init__(self, page: ft.Page, on_log: Callable[[str], None], temp_dir_getter: Callable[[], str]):
        self.page = page
        self.on_log = on_log
        self.temp_dir_getter = temp_dir_getter  # Function to get current scan path
        self.trainer = NerfStudioTrainer()
        self.is_installed = False
        self.installation_thread = None
        
        # UI Components
        self.setup_ui()
        
        # DON'T check installation immediately - will be called after page is ready
        # Use start_installation_check() method from GUI after initialization
    
    def start_installation_check(self):
        """Start background installation check. Call this after page is fully loaded."""
        threading.Thread(target=self._check_installation_async, daemon=True).start()
    
    def _check_installation_async(self):
        """Check if NerfStudio is installed (in background)."""
        import time
        time.sleep(0.5)  # Small delay to ensure page is ready
        
        self.is_installed = NerfStudioTrainer.check_installation()
        
        # Update UI on main thread (safely)
        try:
            self._update_installation_status()
        except:
            # If page not ready, try with run_task
            try:
                self.page.run_task(self._update_installation_status)
            except:
                pass  # Silently fail if page still not ready
    
    def _update_installation_status(self):
        """Update UI based on installation status."""
        if self.is_installed:
            self.install_status_text.value = "✅ NerfStudio Installed"
            self.install_status_text.color = ft.Colors.GREEN
            self.btn_install.text = "Update NerfStudio"
            self.btn_install.icon = ft.Icons.SYSTEM_UPDATE
            self.training_container.disabled = False
        else:
            self.install_status_text.value = "❌ NerfStudio Not Found"
            self.install_status_text.color = ft.Colors.RED
            self.btn_install.text = "Install NerfStudio"
            self.btn_install.icon = ft.Icons.DOWNLOAD
            self.training_container.disabled = True
        
        self.page.update()
    
    def setup_ui(self):
        """Create all UI components."""
        
        # ====== Installation Section ======
        self.install_status_text = ft.Text("Checking...", color=ft.Colors.GREY)
        self.btn_install = ft.ElevatedButton(
            "Install NerfStudio",
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_install_click
        )
        self.install_progress = ft.ProgressBar(visible=False)
        self.install_log = ft.Text("", size=11, font_family="Consolas")
        
        # ====== Training Configuration ======
        self.method_dropdown = ft.Dropdown(
            label="Training Method",
            value="splatfacto",
            options=[
                ft.dropdown.Option("splatfacto", "⚡ Splatfacto (Gaussian Splatting) - Fast, Excellent"),
                ft.dropdown.Option("nerfacto", "🎯 Nerfacto (NeRF) - Balanced"),
                ft.dropdown.Option("instant-ngp", "🚀 Instant-NGP - Ultra Fast"),
                ft.dropdown.Option("depth-nerfacto", "📊 Depth-Nerfacto - Requires Depth"),
            ],
            width=400,
            on_change=self._on_method_change
        )
        
        self.method_description = ft.Text(
            NerfStudioTrainer.METHODS['splatfacto']['description'],
            size=11,
            color=ft.Colors.GREY_400
        )
        
        self.iterations_input = ft.TextField(
            label="Max Iterations",
            value="30000",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.btn_train = ft.ElevatedButton(
            "Start Training",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_train_click,
            disabled=True
        )
        
        self.btn_stop = ft.ElevatedButton(
            "Stop Training",
            icon=ft.Icons.STOP,
            on_click=self._on_stop_click,
            visible=False,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE
        )
        
        # ====== Progress Monitor ======
        self.training_progress = ft.ProgressBar(value=0, visible=False)
        self.progress_text = ft.Text("", size=12)
        self.eta_text = ft.Text("", size=11, color=ft.Colors.GREY_400)
        self.loss_text = ft.Text("", size=11, color=ft.Colors.BLUE_400)
        self.psnr_text = ft.Text("", size=11, color=ft.Colors.GREEN_400)
        
        # ====== Results ======
        self.btn_open_viewer = ft.ElevatedButton(
            "Open Viewer",
            icon=ft.Icons.VISIBILITY,
            on_click=self._on_open_viewer,
           visible=False
        )
        self.output_path_text = ft.Text("", size=11, selectable=True)
        
        # ====== Training Container (disabled when not installed) ======
        self.training_container = ft.Container(
            content=ft.Column([
                ft.Text("Training Configuration", weight="bold", size=16),
                self.method_dropdown,
                self.method_description,
                self.iterations_input,
                ft.Divider(),
                ft.Row([self.btn_train, self.btn_stop]),
                ft.Container(height=10),
                self.training_progress,
                self.progress_text,
                self.eta_text,
                ft.Row([self.loss_text, self.psnr_text]),
                ft.Divider(),
                self.btn_open_viewer,
                self.output_path_text,
            ]),
            padding=15,
            disabled=True
        )
    
    def get_tab(self) -> ft.Tab:
        """Return the NerfStudio tab for main GUI."""
        return ft.Tab(
            text="NerfStudio",
            icon=ft.Icons.AUTO_AWESOME,  # Star/sparkle icon for neural rendering
            content=ft.Container(
                content=ft.ListView([
                    ft.Container(
                        content=ft.Column([
                            ft.Text("🌟 NerfStudio Integration", size=20, weight="bold"),
                            ft.Text(
                                "Train Gaussian Splatting and NeRF models directly from your scans. "
                                "No depth required for color-only reconstruction!",
                                size=12,
                                color=ft.Colors.GREY_400
                            ),
                        ]),
                        padding=15,
                        bgcolor=ft.Colors.BLUE_900,
                        border_radius=10,
                        margin=10
                    ),
                    
                    ft.Container(
                        content=ft.Column([
                            ft.Text("Installation Status", weight="bold", size=16),
                            self.install_status_text,
                            self.btn_install,
                            self.install_progress,
                            self.install_log,
                        ]),
                        padding=15,
                        bgcolor="#2a2a2a",
                        border_radius=10,
                        margin=10
                    ),
                    
                    ft.Container(
                        content=self.training_container,
                        bgcolor="#2a2a2a",
                        border_radius=10,
                        margin=10
                    ),
                ], padding=10),
                expand=True
            )
        )
    
    def _on_method_change(self, e):
        """Update description when method changes."""
        method = e.control.value
        if method in NerfStudioTrainer.METHODS:
            info = NerfStudioTrainer.METHODS[method]
            self.method_description.value = f"{info['description']} | Speed: {info['speed']}, Quality: {info['quality']}"
            self.page.update()
    
    def _on_install_click(self, e):
        """Handle install/update button click."""
        if self.installation_thread and self.installation_thread.is_alive():
            self._show_message("Installation already in progress")
            return
        
        self.btn_install.disabled = True
        self.install_progress.visible = True
        self.install_log.value = "Starting installation..."
        self.page.update()
        
        self.installation_thread = threading.Thread(
            target=self._install_nerfstudio,
            daemon=True
        )
        self.installation_thread.start()
    
    def _install_nerfstudio(self):
        """Install/update NerfStudio using pip."""
        try:
            self._update_install_log("Installing NerfStudio (this may take 5-10 minutes)...")
            
            # Run pip install
            process = subprocess.Popen(
                ['pip', 'install', '-U', 'nerfstudio'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            # Stream output
            for line in process.stdout:
                self._update_install_log(line.strip())
            
            return_code = process.wait()
            
            if return_code == 0:
                self._update_install_log("✅ Installation successful!")
                self.on_log("NerfStudio installed successfully")
                # Re-check installation
                threading.Thread(target=self._check_installation_async, daemon=True).start()
            else:
                self._update_install_log(f"❌ Installation failed (exit code {return_code})")
                self.on_log(f"NerfStudio installation failed")
            
        except Exception as ex:
            self._update_install_log(f"❌ Error: {ex}")
            self.on_log(f"NerfStudio installation error: {ex}")
        
        finally:
            self._installation_complete()
    
    def _installation_complete(self):
        """Called when installation finishes."""
        self.btn_install.disabled = False
        self.install_progress.visible = False
        self.page.update()
    
    def _update_install_log(self, text: str):
        """Update installation log (thread-safe)."""
        current = self.install_log.value
        lines = current.split('\n') if current else []
        lines.append(text)
        # Keep last 10 lines
        self.install_log.value = '\n'.join(lines[-10:])
        self.page.update()

    
    def _on_train_click(self, e):
        """Start training."""
        temp_dir = self.temp_dir_getter()
        if not temp_dir:
            self._show_message("Please load a scan first")
            return
        
        if self.trainer.is_running:
            self._show_message("Training already in progress")
            return
        
        # Validate iterations
        try:
            max_iters = int(self.iterations_input.value)
            if max_iters < 1000:
                self._show_message("Iterations must be at least 1000")
                return
        except ValueError:
            self._show_message("Invalid iterations value")
            return
        
        method = self.method_dropdown.value
        
        self.on_log(f"Starting NerfStudio training: {method}")
        self.btn_train.disabled = True
        self.btn_stop.visible = True
        self.training_progress.visible = True
        self.training_progress.value = 0
        self.progress_text.value = "Initializing..."
        self.page.update()
        
        success = self.trainer.start_training(
            data_path=temp_dir,
            method=method,
            max_iterations=max_iters,
            progress_callback=self._on_training_progress,
            completion_callback=self._on_training_complete
        )
        
        if not success:
            self.btn_train.disabled = False
            self.btn_stop.visible = False
            self.training_progress.visible = False
            self._show_message("Failed to start training")
            self.page.update()
    
    def _on_stop_click(self, e):
        """Stop training."""
        self.trainer.stop_training()
        self.btn_stop.disabled = True
        self.btn_stop.text = "Stopping..."
        self.page.update()
    
    def _on_training_progress(self, info: dict):
        """Handle training progress updates."""
        step = info.get('step', 0)
        total = info.get('total_steps', 30000)
        loss = info.get('loss')
        psnr = info.get('psnr')
        eta = info.get('eta_seconds')
        
        # Update progress bar
        if total > 0:
            self.training_progress.value = step / total
        
        # Update text
        self.progress_text.value = f"Step {step:,} / {total:,}"
        
        if eta is not None:
            minutes = eta // 60
            seconds = eta % 60
            self.eta_text.value = f"ETA: {minutes}m {seconds}s"
        
        if loss is not None:
            self.loss_text.value = f"Loss: {loss:.5f}"
        
        if psnr is not None:
            self.psnr_text.value = f"PSNR: {psnr:.2f} dB"
        
        self.page.update()
    
    def _on_training_complete(self, success: bool, output_path: str):
        """Handle training completion."""
        self.btn_train.disabled = False
        self.btn_stop.visible = False
        self.training_progress.visible = False
        
        if success:
            self.on_log(f"✅ Training completed! Output: {output_path}")
            self.output_path_text.value = f"Model saved: {output_path}"
            self.btn_open_viewer.visible = True
            self._show_message("Training completed successfully!")
        else:
            self.on_log("❌ Training failed or was cancelled")
            self._show_message("Training failed or was cancelled")
        
        self.page.update()
    
    def _on_open_viewer(self, e):
        """Open NerfStudio viewer."""
        viewer_url = self.trainer.get_viewer_url("")
        self.on_log(f"Opening viewer: {viewer_url}")
        
        # Open in default browser
        import webbrowser
        webbrowser.open(viewer_url)
        
        self._show_message(f"Opening viewer at {viewer_url}")
    
    def _show_message(self, text: str):
        """Show snackbar message."""
        self.page.snack_bar = ft.SnackBar(content=ft.Text(text))
        self.page.snack_bar.open = True
        self.page.update()
