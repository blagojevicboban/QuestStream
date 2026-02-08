# QuestStream Project Architecture

This document describes the technical design and data flow within the application.

## 1. Component Overview

The application is divided into a UI layer and a logic layer (backend) that communicate via callback functions within parallel threads (threading).

### UI Layer (`modules/gui.py`)
- Uses **Flet** for interface rendering.
- Manages application state (paths to temporary folders, loaded meshes).
- Launches asynchronous processes in background threads to keep the UI responsive.
- Contains the `add_log` function which centralizes the output of all operations.

### Ingestion Layer (`modules/ingestion.py`)
- **ZipValidator**: Checks if the ZIP file has a correct structure (presence of `frames.json` and required folders).
- **AsyncExtractor**: Inherits from `threading.Thread`. Extracts the ZIP into a system temporary folder (`tempfile`).

### Processing Layer (`modules/image_processing.py`)
- Implements low-level image transformations.
- **yuv_to_rgb**: Conversion from NV12/NV21 format (standard for Quest) to RGB using OpenCV.
- **filter_depth**: Application of a bilateral filter to depth maps for noise reduction before integration.

### Reconstruction Layer (`modules/reconstruction.py`)
- Central part of the backend using **Open3D Tensor API**.
- **QuestReconstructor**: Initializes `VoxelBlockGrid` on GPU (CUDA) if available, falling back to CPU.
- **Integration**: Converts numerical data into Tensor images and integrates them into the sparse volume.

## 2. Data Flow

1. **User selects ZIP** -> `FilePicker` in the GUI.
2. **Validation** -> `ZipValidator` checks CRC and structure.
3. **Extraction** -> `AsyncExtractor` extracts files to `_extracted` folder next to the zip (or system tmp previously).
4. **Launch Reconstruction**:
    - `ReconstructionThread` reads `frames.json`.
    - For each frame:
        - Read BIN/YUV file -> `yuv_to_rgb`.
        - Read Depth file -> `filter_depth` (if configured).
        - Frame is integrated into the `Volume`.
        - **Stereo Mode**: If enabled, both Left and Right camera frames are integrated. The system calculates the world pose for each camera using the Head Pose and known Extrinsics (IPD offset).
5. **Finalization**: 
    - `extract_mesh()` generates a mesh.
    - **Post-Processing**: Smoothing and decimation are applied.
    - **Export**: Mesh is saved as .obj/.glb.
    - **Thumbnail**: A preview image is captured using an off-screen visualizer.

## 3. Configuration Management

All parameters are stored in `config.yml`. `ConfigManager` enables:
- Loading default values if the file does not exist.
- Dynamic updating of values via the Settings dialog without restarting the application.

## 4. Error Handling

The application uses `try-except` blocks in all critical threads. Errors are sent back to the GUI via the `on_error` callback and are printed in the logs (or SnackBar notifications).
