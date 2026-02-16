<p align="center">
  <img src="assets/banner2.png" width="800" alt="QuestStream 3D Banner">
</p>

# <p align="center">🥽 QuestGear 3D Studio</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://flet.dev/"><img src="https://img.shields.io/badge/UI-Flet/Flutter-02569B.svg" alt="UI: Flet"></a>
  <a href="http://www.open3d.org/"><img src="https://img.shields.io/badge/Engine-Open3D-green.svg" alt="Engine: Open3D"></a>
</p>

**QuestGear 3D Studio** is a premium tool for high-quality 3D scene reconstruction directly from data captured via **Meta Quest 3** headsets (using **QuestGear 3D Scan** or legacy Quest Recording Manager). Using advanced volumetric integration (TSDF), QuestGear converts raw YUV/JPG images and depth maps into detailed, textured 3D models.

**Supports both:**
- ✅ **QuestGear 3D Scan** - Modern format (scan_data.json + transforms.json + JPG/PNG)
- ✅ **Quest Recording Manager** - Legacy format (hmd_poses.csv + YUV/RAW)

---

## ✨ Key Features

- 🚀 **GPU Acceleration**: Built on **Open3D Tensor API**, utilizing CUDA for 10x-50x faster reconstruction.
- ⚡ **Asynchronous Pipeline**: Fast data processing without freezing the interface.
- 🎨 **Modern Deep UI**: Elegant interface built using the **Flet** platform with dynamic progress bars.
- ⭐ **NerfStudio Integration**: **One-Click Automated Install**! Train Gaussian Splatting and NeRF models directly from the GUI (isolated environment included). [See Guide](./NERFSTUDIO_GUIDE.md)
- 🛠️ **Advanced Processing**:
  - **YUV_420_888 Conversion**: Automatic conversion of Quest raw formats to RGB.
  - **JPG/PNG Support**: Modern image formats with auto-detection
  - **Depth Validation**: Smart detection of invalid/placeholder depth data
- 🌐 **Scalable VoxelBlockGrid**: Efficient sparse volume reconstruction for large scenes.
- 👓 **Stereo Reconstruction**: Utilize both Quest cameras for denser, more complete models.
- 🎬 **Smart Cropping & Live View**: Preview video before processing and watch real-time progress.
- 🧹 **Mesh Post-Processing**: Built-in smoothing and decimation tools for clean, optimized models.
- 💾 **Safe Storage**: Models are saved to a dedicated `Export` folder with persistent, timestamped naming.
- 🔍 **Robust Monitoring**: Accurate RAM usage tracking and high-quality reconstruction thumbnails.
- 🛑 **Full Control**: Native **Stop** buttons for both ZIP extraction and 3D reconstruction processes.
- 📐 **Customizable Layout**: Resizable panels to adjust the workspace to your preference.
- 🖼️ **Interactive Visualizer**: Focused 3D window for external model inspection with rotation, zoom, and shading support.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.11 |
| **Frontend** | Flet (Flutter-based) |
| **3D Engine** | Open3D |
| **Neural Rendering** | NerfStudio (Gaussian Splatting, NeRF) |
| **Computer Vision** | OpenCV & NumPy |
| **Data Format** | JSON / CSV / YAML |

---

## 🚀 Quick Start

### 📝 Prerequisites
- **OS**: Windows 10/11
- **Python**: 3.11 (Recommended)
- **Data**: Quest Capture data (ZIP or extracted folder)

### 💻 Installation
```powershell
# Clone the project
git clone https://github.com/blagojevicboban/QuestStream.git
cd QuestStream

# Environment setup
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install scipy
```

### 🎮 Running
```powershell
python main.py
```

---

## 📂 Project Structure

```text
QuestStream/
├── main.py            # Application entry point
├── config.yml         # Global reconstruction settings
├── modules/
│   ├── gui.py         # Flet UI and thread management
│   ├── reconstruction.py# TSDF Engine (Open3D)
│   ├── quest_adapter.py # Quest data adaptation
│   ├── quest_image_processor.py # YUV/Depth processing
│   ├── quest_reconstruction_utils.py # Poses/Depth Utils
│   └── config_manager.py# YAML Config loader
└── README_QUEST.md    # Detailed instructions for Quest 3 pipeline
```

---

## 🎓 Advanced Usage

For best results when recording with Meta Quest 3, we recommend:
1. **Frame Interval**: Use `1` in Settings for maximum detail.
2. **Voxel Size**: Set to `0.01` or `0.02` depending on processing power.
3. **Movement**: Move slowly and circle around objects for better data overlap.

A more detailed guide can be found in [README_QUEST.md](./README_QUEST.md).

---

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) for details.

---
*Developed with ❤️ for the Meta Quest Community*
