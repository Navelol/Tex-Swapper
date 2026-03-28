# Animated Texture Swap — Blender Addon

A Blender addon that animates texture swaps across multiple meshes and materials by cycling through folders of images frame-by-frame.

![Blender](https://img.shields.io/badge/Blender-2.8%2B-orange?logo=blender&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)
---

## Features

- **Multiple mesh slots** — configure any number of mesh/material pairs, each running in parallel
- **Multiple texture nodes per slot** — swap several Image Texture nodes within the same material simultaneously
- **Label-based node lookup** — reference nodes by their display label in the shader editor, with fallback to internal node name
- **Adjustable timing** — set frames per swap and start frame globally
- **Optional timeline shortening** — automatically trim the scene end frame to match the last swap

---

## Requirements

- Blender **2.80 or later**

---

## Installation

1. Download the latest `Texture_Swap_vX.X.py` from the [Releases](../../releases) page
2. In Blender, go to **Edit → Preferences → Add-ons → Install**
3. Select the downloaded `.py` file and click **Install Add-on**
4. Enable the addon by ticking the checkbox next to **"Animated Texture Swap (Multi-Material)"**

The panel will appear in the **3D Viewport sidebar** (`N` key) under the **Texture Swap** tab.

---

## Usage

### 1. Add a Mesh Slot

Click **Add Mesh Slot** at the top of the panel. Each slot represents one mesh + material pair.

- **Mesh** — pick any mesh object in your scene
- **Material** — pick one of that object's materials

### 2. Add Texture Nodes

Inside a slot, click **Add Node** to add a node mapping entry.

- **Node Label / Name** — enter the label you've set on the Image Texture node in the shader editor (or its internal name if no label is set)
- **Folder** — point to a directory containing your image sequence (PNG, JPG, JPEG, TIF, TIFF, EXR supported)

> **Tip:** To set a label on a node in Blender, double-click the node's header in the Shader Editor, or press `F2` while the node is selected.

Images in the folder are loaded in **alphabetical/sorted order**, so name your files accordingly (e.g. `frame_001.png`, `frame_002.png`, …).

### 3. Set Global Timing

| Setting | Description |
|---|---|
| **Frames per Swap** | How many frames each image is held before advancing |
| **Start Frame** | Which scene frame the sequence begins on |
| **Shorten Timeline** | If enabled, sets the scene end frame to the last swap frame |

### 4. Apply

Click **Apply Texture Swap**. Scrub or play the timeline — textures will swap automatically.

---

## Multiple Meshes Example

| Slot | Mesh | Material | Node Label | Folder |
|---|---|---|---|---|
| 1 | `CharacterBody` | `Skin` | `skin_diffuse` | `/textures/skin/` |
| 2 | `CharacterBody` | `Skin` | `skin_normal` | `/textures/skin_normals/` |
| 3 | `CharacterEyes` | `Eyes` | `eye_tex` | `/textures/eyes/` |

All slots advance together using the same **Frames per Swap** and **Start Frame**.

---

## Notes

- The addon hooks into Blender's `frame_change_post` handler. Removing or re-registering the addon mid-session will clear the active swap — just hit **Apply** again.
- If two nodes share a label, the first match found is used. Keep labels unique within a material.
- Images are loaded with `check_existing=True`, so re-applying won't duplicate data blocks.

---

## License

MIT — do whatever you want with it.