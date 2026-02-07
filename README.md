# 🥽 QuestStream 3D Processor

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![UI: Flet](https://img.shields.io/badge/UI-Flet/Flutter-02569B.svg)](https://flet.dev/)
[![Engine: Open3D](https://img.shields.io/badge/Engine-Open3D-green.svg)](http://www.open3d.org/)

**QuestStream** je premium alat za rekonstrukciju 3D scena visokog kvaliteta direktno iz podataka snimljenih putem **Meta Quest 3** headset-a. Koristeći naprednu volumetrijsku integraciju (TSDF), QuestStream pretvara sirove YUV slike i depth mape u detaljne, teksturirane 3D modele.

---

## ✨ Glavne Funkcionalnosti

- 🚀 **Asinhroni Pipeline**: Brza obrada podataka bez zamrzavanja interfejsa.
- 🎨 **Modern Deep UI**: Elegantan interfejs izgrađen pomoću **Flet** platforme sa dinamičkim progres barovima.
- 🛠️ **Napredna Obrada**:
  - **YUV_420_888 Conversion**: Automatska konverzija Quest sirovih formata u RGB.
  - **Depth Optimization**: Filtriranje šuma, Infinity/NaN vrednosti i precizno skaliranje dubine.
- 🌐 **Scalable TSDF**: Rekonstrukcija velikih scena uz minimalnu potrošnju memorije.
- 🔍 **Real-time Logging**: Detaljan uvid u svaki korak procesa direktno u aplikaciji.
- 🖼️ **Interactive Visualizer**: Eksterna inspekcija modela sa podrškom za rotaciju, zoom i promenu shading-a.

---

## 🛠️ Tehnološki Stack

| Komponenta | Tehnologija |
| :--- | :--- |
| **Jezik** | Python 3.11 |
| **Frontend** | Flet (Flutter based) |
| **3D Engine** | Open3D |
| **Computer Vision** | OpenCV & NumPy |
| **Data Format** | JSON / CSV / YAML |

---

## 🚀 Brzi Početak

### 📝 Preduslovi
- **OS**: Windows 10/11
- **Python**: 3.11 (Preporučeno)
- **Podaci**: Quest Capture podaci (ZIP ili raspakovan folder)

### 💻 Instalacija
```powershell
# Klonirajte projekt
git clone https://github.com/blagojevicboban/QuestStream.git
cd QuestStream

# Postavljanje okruženja
python -m venv venv
.\venv\Scripts\activate

# Instalacija zavisnosti
pip install -r requirements.txt
```

### 🎮 Pokretanje
```powershell
python main.py
```

---

## 📂 Struktura Projekta

```text
QuestStream/
├── main.py            # Ulazna tačka aplikacije
├── config.yml         # Globalna podešavanja rekonstrukcije
├── modules/
│   ├── gui.py         # Flet UI i thread management
│   ├── reconstruction.py# TSDF Engine (Open3D)
│   ├── quest_adapter.py # Adaptacija Quest podataka
│   ├── quest_image_processor.py # YUV/Depth obrada
│   └── config_manager.py# YAML Config loader
└── README_QUEST.md    # Detaljna uputstva za Quest 3 pipeline
```

---

## 🎓 Napredna Upotreba

Za najbolje rezultate pri snimanju sa Meta Quest 3, preporučujemo:
1. **Frame Interval**: Koristite `1` u Settings za maksimalne detalje.
2. **Voxel Size**: Postavite na `0.01` ili `0.02` u zavisnosti od procesorske snage.
3. **Pomeranje**: Krećite se polako i kružite oko objekata radi boljeg preklapanja podataka.

Detaljniji vodič možete pronaći u [README_QUEST.md](./README_QUEST.md).

---

## 📄 Licenca

Ovaj projekat je licenciran pod **MIT Licencom** - pogledajte [LICENSE](LICENSE) za detalje.

---
*Developed with ❤️ for the Meta Quest Community*
