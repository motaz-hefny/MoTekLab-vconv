# vconv — Image Assets

Generate these images and place them in this `public/` folder.
**All prompts are optimized for Google Imagen** (and compatible with Midjourney / DALL-E 3).

**Style direction:** neon cyberpunk meets glassmorphism — dark backgrounds with glowing teal accents, frosted glass panels, light reflections, and translucent surfaces.

---

## Color & Style Reference

| Name | Hex | Usage |
|------|-----|-------|
| Deep Navy | `#0B1A2E` | Main backgrounds |
| Dark Slate | `#16213E` | Glass surface tint |
| Neon Teal | `#00F5FF` | Primary glow |
| Electric Cyan | `#00B4D8` | Secondary glow |
| Glass White | `rgba(255,255,255,0.15)` | Glass panels |
| Highlight | `rgba(0,245,255,0.3)` | Glass reflections |

---

## 1. App Icon

**File:** `vconv-icon-256.png`
**Size:** 256 × 256 pixels, PNG, square
**Use:** Application icon, taskbar, desktop file

**Prompt for Google Imagen:**
```
Square app icon 256x256 for a video converter app called vconv.
Dark navy background with a frosted glass hexagonal badge in the center.
Inside the glass hexagon, a glowing neon teal play button symbol made of
smooth glass material with inner light reflections.
A thin metallic frame around the hexagon with subtle cyan glow overflow.
Futuristic cyberpunk aesthetic, glassmorphism style, translucent surfaces,
soft lighting bloom around the edges. The icon must read well at small sizes.
No text. Solid dark background. 1:1 aspect ratio.
```

---

## 2. Logo (transparent background)

**File:** `vconv-logo-512.png`
**Size:** 512 × 512 pixels, PNG, transparent background
**Use:** About dialog, splash screen, website, GitHub avatar

**Prompt for Google Imagen:**
```
Logo mark for vconv video converter on transparent background.
Two letter V shapes intersecting to form a film frame and play button.
The lines are made of glowing neon teal tubes with glass-like reflections.
Subtle cyan glow effect around the neon tubes against the dark transparent void.
Clean minimalist vector-style silhouette with neon lighting details.
Glassmorphism material effect: the shapes look like bent glass tubes with
light traveling through them. No background, just the logo with glow.
512x512.
```

---

## 3. About Dialog Banner

**File:** `vconv-about-banner.png`
**Size:** 600 × 200 pixels, PNG
**Use:** Header image in the About dialog window

**Prompt for Google Imagen:**
```
Wide horizontal banner 600x200 for vconv video converter About dialog.
Dark navy gradient background with a glass panel overlay effect.
A cinematic neon audio waveform visualized as glowing teal and cyan
translucent glass bars floating above a frosted glass surface at the bottom.
Subtle floating hexagonal particles with glass texture and soft glow.
Film sprocket holes fading into the darkness on the left edge.
The right side has an empty dark area suitable for placing text over.
Cyberpunk glassmorphism style with neon lighting. No text in image.
```

---

## 4. GitHub Social Preview

**File:** `vconv-github-social.png`
**Size:** 1280 × 640 pixels, PNG
**Use:** Social preview card for GitHub repository

**Prompt for Google Imagen:**
```
Wide banner 1280x640 for GitHub social preview of vconv video converter.
Dark cinematic background with layers of frosted glass panels at different depths,
creating a 3D glassmorphism depth effect. A large central geometric play button
made of translucent neon teal glass with intense inner glow and light reflections
bouncing through the material. Subtle video editing UI elements in the background:
a faint glass timeline waveform, translucent progress bar shapes, all in darker
teal tones with soft neon glows. The left side has an empty dark glass panel area
for text placement. Premium cyberpunk aesthetic with glass reflections and
neon light bloom. No text in the image itself.
```

---

## 5. Splash Screen

**File:** `vconv-splash.png`
**Size:** 800 × 480 pixels, PNG
**Use:** Splash screen shown during application startup

**Prompt for Google Imagen:**
```
Splash screen 800x480 for vconv video converter application startup.
Deep navy to dark slate gradient background. A centered frosted glass circle
with a glowing neon play icon inside, the glass surface having subtle
reflection highlights. A faint glowing ring around the glass circle pulsing
with teal light. A thin horizontal neon glass progress bar at the bottom
with a soft glow trail. Very faint translucent grid lines suggesting a video
editing timeline in the background at low opacity. Clean minimal composition,
cinematic glassmorphism style with neon accents. No text. 5:3 aspect ratio.
```

---

## 6. Start Menu Folder Icon

**File:** `vconv-folder-icon.png`
**Size:** 48 × 48 pixels, PNG
**Use:** Start menu folder icon (Multimedia category)

**Prompt for Google Imagen:**
```
Tiny 48x48 pixel app icon for vconv video converter. Must be crystal clear
at small size. A dark navy circular badge with a glass-like glossy surface.
A simple neon teal play triangle in the center with a tiny glow effect.
The glass surface has a subtle white reflection highlight in the upper left.
Ultra-minimalist, pixel-perfect at 48px. Solid dark background circle.
No text, no details. Glossy glassmorphism badge style.
```

---

## Generation Tips for Google Imagen

1. **Aspect ratio:** Use the `--ar` parameter format listed for each image
2. **Style keywords:** Include "glassmorphism", "neon glow", "translucent", "frosted glass", "cyberpunk" in every prompt
3. **Iteration:** Generate 2-3 variations of each, pick the one with cleanest glass effects
4. **Post-processing:** If the glass effect is subtle, increase contrast slightly
5. **No text:** All prompts explicitly say "no text" — the text overlay is done in code

---

## File Placement

After generating, place files here:

```
public/
├── vconv-icon-256.png        # 256×256 — App icon
├── vconv-logo-512.png        # 512×512 — Transparent logo
├── vconv-about-banner.png    # 600×200 — About dialog
├── vconv-github-social.png   # 1280×640 — GitHub preview
├── vconv-splash.png          # 800×480 — Splash screen
├── vconv-folder-icon.png     # 48×48 — Start menu icon
└── README.md                 # This file
```