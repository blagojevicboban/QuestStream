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
    
    def _get_nerfstudio_python(self) -> str:
        """Get path to the dedicated NerfStudio python executable."""
        # Use a separate venv for NerfStudio to avoid conflicts
        venv_name = "nerfstudio_venv"
        return os.path.abspath(os.path.join(os.getcwd(), venv_name, "Scripts", "python.exe"))

    def _check_installation_async(self):
        """Check if NerfStudio is installed (in background)."""
        import time
        time.sleep(0.5)  # Small delay to ensure page is ready
        
        ns_python = self._get_nerfstudio_python()
        
        # Check if python exists in separate env
        if not os.path.exists(ns_python):
            self.is_installed = False
        else:
            # Check if nerfstudio is importable in that env
            try:
                cmd = [ns_python, "-c", "import nerfstudio; print('ok')"]
                # Use subprocess to check without raising exception if module missing
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                    check=False  # Don't raise CalledProcessError
                )
                self.is_installed = (result.returncode == 0)
            except Exception:
                self.is_installed = False
        
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
            self.install_status_text.value = "✅ NerfStudio Installed (Dedicated Env)"
            self.install_status_text.color = ft.Colors.GREEN
            self.btn_install.text = "Update NerfStudio"
            self.btn_install.icon = ft.Icons.SYSTEM_UPDATE
            self.btn_uninstall.visible = True  # Show uninstall when installed
            self.training_container.disabled = False
            self.btn_train.disabled = False  # Enable button - validation happens on click
        else:
            self.install_status_text.value = "❌ NerfStudio Not Found"
            self.install_status_text.color = ft.Colors.RED
            self.btn_install.text = "Install NerfStudio (Safe Mode)"
            self.btn_install.icon = ft.Icons.DOWNLOAD
            self.btn_uninstall.visible = False  # Hide uninstall when not installed
            self.training_container.disabled = True
            self.btn_train.disabled = True
        
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
        self.btn_uninstall = ft.ElevatedButton(
            "Uninstall",
            icon=ft.Icons.DELETE_FOREVER,
            on_click=self._on_uninstall_click,
            visible=False,
            bgcolor=ft.Colors.RED_700,
            color=ft.Colors.WHITE
        )
        self.install_progress = ft.ProgressBar(visible=False)
        
        # Use ListView for install log to enable scrolling
        self.install_log = ft.ListView(
            expand=True,
            spacing=2,
            padding=5,
            auto_scroll=True,
            height=150
        )
        self.install_log_container = ft.Container(
            content=self.install_log,
            bgcolor="#1e1e1e",
            border=ft.border.all(1, ft.Colors.GREY_800),
            border_radius=5,
            padding=5,
            height=150,
            visible=False # Hidden initially
        )
        
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
        # ====== Results ======
        self.btn_open_viewer = ft.ElevatedButton(
            "Open Viewer",
            icon=ft.Icons.VISIBILITY,
            on_click=self._on_open_viewer,
            visible=False
        )
        self.output_path_text = ft.Text("", size=11, selectable=True)
        
        # ====== Training Logs ======
        self.training_log = ft.ListView(
            expand=True,
            spacing=2,
            padding=5,
            auto_scroll=True,
            height=200
        )
        self.training_log_container = ft.Container(
            content=self.training_log,
            bgcolor="#1e1e1e",
            border=ft.border.all(1, ft.Colors.GREY_800),
            border_radius=5,
            padding=5,
            height=200,
            visible=False # Hidden initially until training starts
        )
        
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
                self.training_log_container, # Add log container here
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
                            ft.Row([self.btn_install, self.btn_uninstall]),
                            self.install_progress,
                            self.install_log_container,
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
    
    def _on_uninstall_click(self, e):
        """Show confirmation dialog for uninstallation."""
        def close_dlg(e):
            dlg.open = False
            self.page.update()
            
        def confirm_uninstall(e):
            dlg.open = False
            self.page.update()
            self._do_uninstall()

        dlg = ft.AlertDialog(
            title=ft.Text("Uninstall NerfStudio?"),
            content=ft.Text("This will remove NerfStudio and all its dependencies from the virtual environment. This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=close_dlg),
                ft.TextButton("Yes, Uninstall", on_click=confirm_uninstall, style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dlg.open = True
        self.page.overlay.append(dlg)
        self.page.update()

    def _do_uninstall(self):
        """Start the uninstallation thread."""
        if self.installation_thread and self.installation_thread.is_alive():
            self._show_message("A process is already in progress")
            return
            
        self.btn_install.disabled = True
        self.btn_uninstall.disabled = True
        self.install_progress.visible = True
        self.install_log.value = "Starting uninstallation..."
        self.page.update()
        
        self.installation_thread = threading.Thread(
            target=self._uninstall_nerfstudio,
            daemon=True
        )
        self.installation_thread.start()

    def _uninstall_nerfstudio(self):
        """Uninstall NerfStudio using pip."""
        import sys
        
        try:
            self._update_install_log("Uninstalling NerfStudio...")
            
            uninstall_cmd = [
                sys.executable,
                '-m', 'pip',
                'uninstall',
                '-y',  # Auto-confirm
                'nerfstudio'
            ]
            
            process = subprocess.Popen(
                uninstall_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            for line in process.stdout:
                line = line.strip()
                if line:
                    self._update_install_log(line)
            
            if process.wait() == 0:
                self._update_install_log("✅ Uninstallation successful!")
                self.on_log("NerfStudio uninstalled")
            else:
                self._update_install_log("❌ Uninstallation failed")
                self.on_log("NerfStudio uninstallation failed")
                
            # Re-check status
            threading.Thread(target=self._check_installation_async, daemon=True).start()
            
        except Exception as ex:
            self._update_install_log(f"❌ Error: {ex}")
            self.on_log(f"NerfStudio uninstall error: {ex}")
        
        finally:
            self.btn_install.disabled = False
            self.btn_uninstall.disabled = False
            self.btn_uninstall.visible = False # It's gone now
            self.install_progress.visible = False
            self.page.update()
    
    def _install_nerfstudio(self):
        """Install/update NerfStudio in dedicated env."""
        import sys
        
        target_python = self._get_nerfstudio_python()
        venv_dir = os.path.dirname(os.path.dirname(target_python)) # .../nerfstudio_venv
        
        try:
            self._update_install_log(f"Creating dedicated environment in: {venv_dir}...")
            
            # 1. Create venv if not exists
            if not os.path.exists(target_python):
                import venv
                self._update_install_log("Initializing new virtual environment...")
                venv.create(venv_dir, with_pip=True)
                self._update_install_log("✅ Environment created.")

            # 2. Upgrade pip
            self._update_install_log("Upgrading pip...")
            subprocess.run([target_python, "-m", "pip", "install", "--upgrade", "pip"], 
                           creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)

            # 3. Install PyTorch with CUDA (Critical Step!)
            self._update_install_log("Step 1/3: Installing PyTorch with CUDA support...")
            torch_cmd = [
                target_python, "-m", "pip", "install", 
                "torch", "torchvision", "torchaudio",
                "--index-url", "https://download.pytorch.org/whl/cu121",
                "--no-cache-dir"
            ]
            
            proc = subprocess.Popen(
                torch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            ) 
            for line in proc.stdout:
                if line.strip(): self._update_install_log(line.strip())
            proc.wait()

            # 4. Install NerfStudio & Dependencies
            self._update_install_log("Step 2/3: Installing NerfStudio & core libs...")
            
            # gsplat needs special handling - install from official wheel repo with CUDA binaries
            self._update_install_log("  → Installing gsplat with CUDA support...")
            gsplat_cmd = [
                target_python, "-m", "pip", "install", 
                "gsplat",
                "--find-links", "https://docs.gsplat.studio/whl/",
                "--no-cache-dir"
            ]
            proc_gsplat = subprocess.Popen(
                gsplat_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            for line in proc_gsplat.stdout:
                 if line.strip() and ('ERROR' in line or 'Successfully' in line): 
                     self._update_install_log(f"    {line.strip()}")
            proc_gsplat.wait()
            
            # Install remaining components
            self._update_install_log("  → Installing nerfstudio and dependencies...")
            ns_cmd = [
                target_python, "-m", "pip", "install", 
                "nerfstudio", "nerfacc", "viser", "tensorboard",
                "--no-warn-script-location"
            ]
            
            proc = subprocess.Popen(
                ns_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            for line in proc.stdout:
                 if line.strip(): self._update_install_log(line.strip())
            
            if proc.wait() == 0:
                # Verify gsplat installation (silently)
                try:
                    verify_cmd = [target_python, "-c", "from gsplat import csrc; print('OK')"]
                    verify_result = subprocess.run(
                        verify_cmd, 
                        capture_output=True, 
                        text=True,
                        stderr=subprocess.DEVNULL,  # Suppress error output to avoid debugger breaks
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                        timeout=10  # Prevent hanging
                    )
                    gsplat_ok = (verify_result.returncode == 0)
                except Exception:
                    gsplat_ok = False
                
                if not gsplat_ok:
                    self._update_install_log("⚠️  gsplat installation incomplete (missing CUDA binaries)")
                    self._update_install_log("ℹ️  This is a known issue on Windows.")
                    self._update_install_log("📌 SOLUTION: Use 'nerfacto' method instead of 'splatfacto'")
                    self._update_install_log("   OR install Visual Studio Build Tools:")
                    self._update_install_log("   https://visualstudio.microsoft.com/downloads/")
                    self._update_install_log("")
                    self._update_install_log("✅ NerfStudio installed (nerfacto method available)")
                    self.is_installed = True
                    self.on_log("NerfStudio installed (nerfacto only - gsplat build failed)")
                else:
                    self._update_install_log("✅ Installation successful (all methods available)!")
                    self.is_installed = True
                    self.on_log("NerfStudio installed in dedicated env")
            else:
                self._update_install_log("❌ Installation failed.")
            
            # Refresh status
            self._check_installation_async()
            
        except Exception as ex:
            self._update_install_log(f"❌ Error: {ex}")
            import traceback
            self._update_install_log(traceback.format_exc())
        
        finally:
            self.btn_install.disabled = False
            self.install_progress.visible = False
            self.page.update()
            self._installation_complete()
    
    def _installation_complete(self):
        """Called when installation finishes."""
        self.btn_install.disabled = False
        self.install_progress.visible = False
        self.page.update()
    
    def _update_install_log(self, text: str):
        """Append text to install log."""
        self.install_log.controls.append(ft.Text(text, size=11, font_family="Consolas"))
        if len(self.install_log.controls) > 1000:
            self.install_log.controls.pop(0)

        # Ensure log container is visible
        if hasattr(self, 'install_log_container'):
            self.install_log_container.visible = True

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
            completion_callback=self._on_training_complete,
            log_callback=self._on_training_log
        )
        
        if success:
            self.training_log.controls.clear()
            self.training_log_container.visible = True
            self.page.update()
        else:
            self.btn_train.disabled = False
            self.btn_stop.visible = False
            self.training_progress.visible = False
            self._show_message("Failed to start training")
            self.page.update()
    
    def _on_training_log(self, line: str):
        """Handle raw log output from training."""
        self.training_log.controls.append(
            ft.Text(line, size=10, font_family="Consolas", color=ft.Colors.GREEN_400)
        )
        if len(self.training_log.controls) > 500: # Limit history
            self.training_log.controls.pop(0)
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
