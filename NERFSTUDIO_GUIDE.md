# 🧪 NerfStudio Integration Guide

QuestGear 3D Studio now features a **fully automated integration** with [NerfStudio](https://docs.nerf.studio/), allowing you to train state-of-the-art Neural Radiance Fields (NeRF) and Gaussian Splatting models directly from your Meta Quest 3 scans.

## 🌟 Key Features

*   **One-Click Installation**: No complex command-line setup. The app handles everything.
*   **Isolated Environment**: Creates a dedicated `nerfstudio_venv` to keep your system clean and avoid conflicts.
*   **Method Support**:
    *   ⚡ **Splatfacto** (Gaussian Splatting) - Fastest training, highest quality (Requires VS Build Tools).
    *   🎯 **Nerfacto** (NeRF) - Robust, high quality, easy to install.
    *   🚀 **Instant-NGP** - Ultra-fast legacy NeRF.
*   **Real-Time Monitoring**: Watch loss curves, PSNR, and rendering previews live in the GUI.
*   **Zero-Copy Workflow**: Uses your exported `transforms.json` directly.

---

## 🛠️ Prerequisites

*   **OS**: Windows 10 / 11
*   **GPU**: NVIDIA GeForce RTX 3060 or higher (6GB+ VRAM recommended)
*   **Drivers**: Latest NVIDIA Studio/Game Ready Drivers
*   **Visual Studio Build Tools** (Only for `splatfacto`):
    *   Required to compile the `gsplat` CUDA kernels on Windows.
    *   [Download VS Build Tools](https://visualstudio.microsoft.com/downloads/) -> Select **"Desktop development with C++"**.

> **ℹ️ Note:** If you don't want to install Visual Studio, you can use the **`nerfacto`** method which works out-of-the-box!

---

## 🚀 Getting Started

### 1. Installation
1.  Open **QuestGear 3D Studio**.
2.  Navigate to the **NerfStudio** tab.
3.  Click the **"Install NerfStudio"** button.
4.  Wait for the process to complete.
    *   The app will create a hidden folder `nerfstudio_venv`.
    *   It will install PyTorch (CUDA), gsplat, and NerfStudio.
    *   *This takes about 5-10 minutes.*

### 2. Training a Model
1.  **Select a Scan**: Ensure you have a processed scan available on the Dashboard.
2.  **Choose Method**:
    *   Use **`nerfacto`** for robust results without extra setup.
    *   Use **`splatfacto`** for cutting-edge Gaussian Splatting (requires VS Build Tools).
3.  **Configure**:
    *   **Max Iterations**: 30,000 is standard.
4.  **Start**: Click **"Start Training"**.
5.  **Monitor**: Watch the progress bar and log output.

### 3. Visualization
*   Once training is complete, an **"Open Viewer"** button will appear.
*   Click it to launch the web-based interactive viewer in your browser.
*   You can export videos or `.ply` files from the viewer.

---

## 🧩 Troubleshooting

### `ImportError: cannot import name 'csrc' from 'gsplat'`
*   **Cause**: You are trying to use `splatfacto` but missing the compiled CUDA binaries.
*   **Solution**:
    1.  Switch to **`nerfacto`** method (works immediately).
    2.  OR Install **Visual Studio Build Tools 2022** (Desktop C++) and re-install NerfStudio via the app.

### `CUDA out of memory`
*   **Cause**: Your GPU VRAM is full.
*   **Solution**:
    *   Close other apps (games, browser tabs with GPU usage).
    *   Use `nerfacto` instead of `splatfacto`.
    *   In `config.yml` (advanced), reduce batch size.

### `ModuleNotFoundError`
*   **Cause**: The isolated environment is corrupted.
*   **Solution**:
    *   Click **"Uninstall"** in the NerfStudio tab.
    *   Click **"Install"** again to rebuild the environment from scratch.

---

## 📂 Output Locations
Models are saved in:
`QuestGear3DStudio/outputs/<scan_name>/<method>/<timestamp>/`

*   **Config**: `config.yml` (Needed to load the model later)
*   **Checkpoints**: `nerfstudio_models/`
*   **Exports**: `exports/` (if exported from viewer)
