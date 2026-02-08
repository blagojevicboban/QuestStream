<p align="center">
  <img src="assets/banner2.png" width="800" alt="QuestStream 3D Banner">
</p>

# <p align="center">🥽 QuestStream 3D Processor</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://flet.dev/"><img src="https://img.shields.io/badge/UI-Flet/Flutter-02569B.svg" alt="UI: Flet"></a>
  <a href="http://www.open3d.org/"><img src="https://img.shields.io/badge/Engine-Open3D-green.svg" alt="Engine: Open3D"></a>
</p>

**QuestStream** is a premium tool for high-quality 3D scene reconstruction directly from data captured via **Meta Quest 3** headsets. Using advanced volumetric integration (TSDF), QuestStream converts raw YUV images and depth maps into detailed, textured 3D models.

---

## ✨ Key Features

- 🚀 **GPU Acceleration**: Built on **Open3D Tensor API**, utilizing CUDA for 10x-50x faster reconstruction.
- ⚡ **Asynchronous Pipeline**: Fast data processing without freezing the interface.
- 🎨 **Modern Deep UI**: Elegant interface built using the **Flet** platform with dynamic progress bars.
- 🛠️ **Advanced Processing**:
  - **YUV_420_888 Conversion**: Automatic conversion of Quest raw formats to RGB.
  - **Depth Optimization**: Filtering noise, Infinity/NaN values, and precise depth scaling.
- 🌐 **Scalable VoxelBlockGrid**: Efficient sparse volume reconstruction for large scenes.
- 👓 **Stereo Reconstruction**: Utilize both Quest cameras for denser, more complete models.
- 🧹 **Mesh Post-Processing**: Built-in smoothing and decimation tools for clean, optimized models.
- 💾 **Multi-Format Export**: Save results as **.OBJ**, **.GLB** (Web/AR ready), or **.PLY**.
- 🔍 **Real-time Monitoring**: RAM usage tracking and reconstruction thumbnails directly in the app.
- 🖼️ **Interactive Visualizer**: External model inspection with support for rotation, zoom, and shading changes.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.11 |
| **Frontend** | Flet (Flutter-based) |
| **3D Engine** | Open3D |
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
