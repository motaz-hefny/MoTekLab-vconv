# vconv — Image Assets

Generate these images and place them in this `public/` folder.
All prompts are designed for **Midjourney** (best results) and compatible with DALL-E 3 / Stable Diffusion XL.

---

## 1. App Icon

**File:** `public/vconv-icon-256.png`
**Size:** 256 × 256 pixels (PNG, square)
**Use:** Application icon, taskbar, window decoration, desktop file icon

**Prompt (Midjourney):**
```
A modern flat design app icon for a video converter app called "vconv".
A square video play button merged with a film reel and a subtle gear icon for settings.
Color palette: deep navy blue background (#0B1A2E), bright teal accent (#00B4D8),
and white foreground. Minimalist, clean, professional.
The icon should read clearly at both 256px and 48px sizes.
No text. Solid background, no transparency. Symmetrical composition.
--ar 1:1 --v 6.1 --style raw
```

**Prompt (DALL-E 3):**
```
Minimalist app icon for a video converter application. A square icon with a dark navy blue background. A geometric play button symbol in bright teal, integrated with a film strip element on the right side. Clean, flat vector style. Professional, modern tech feel. No text. Solid background. 256x256.
```

---

## 2. Logo (with transparency)

**File:** `public/vconv-logo-512.png`
**Size:** 512 × 512 pixels (PNG, transparent background)
**Use:** About dialog, splash screen, website, GitHub avatar

**Prompt (Midjourney):**
```
Simple elegant logo mark for "vconv" video converter.
Two interlocking letter "V" shapes forming a film frame or play button.
Thin clean lines, modern minimalist style, transparent background.
Teal (#00B4D8) and white lines on transparent.
Vector-style, scalable, symmetrical.
No background, no shadows, pure logo mark.
--ar 1:1 --v 6.1 --style raw
```

**Prompt (DALL-E 3):**
```
Clean minimal logo mark for a video converter app. Two interlocking V shapes forming a play button. Thin teal lines on transparent background. Vector illustration style. No background, just the logo. 512x512.
```

---

## 3. About Dialog Banner

**File:** `public/vconv-about-banner.png`
**Size:** 600 × 200 pixels (PNG)
**Use:** Header image in the About dialog window

**Prompt (Midjourney):**
```
Wide horizontal banner for "vconv" video converter About dialog.
Dark gradient background from deep navy to charcoal (#0B1A2E → #1A1A2E).
A cinematic curved waveform visualized as glowing teal (#00B4D8) and
soft cyan lines across the bottom half. Subtle floating video frame outlines
in very dark gray near the edges. The text area on the left should be dark
and clean for readability. Professional, tech atmosphere.
No text in the image itself. 600x200 format.
--ar 3:1 --v 6.1 --style raw
```

**Prompt (DALL-E 3):**
```
Horizontal banner 600x200 for video converter app About screen. Dark navy gradient background. Glowing teal audio waveform lines across the bottom. Subtle film frame corners. Cinematic, professional, modern tech feel. No text. Clean composition.
```

---

## 4. GitHub Social Preview

**File:** `public/vconv-github-social.png`
**Size:** 1280 × 640 pixels (PNG)
**Use:** Social preview card when sharing the GitHub repository link

**Prompt (Midjourney):**
```
Wide social media banner for GitHub repository "vconv - Video Converter".
Dark cinematic background transitioning from deep teal to charcoal.
A large central glowing play button icon made of geometric polygons.
Subtle video editing UI elements (timeline waveforms, progress bars) 
as faint background patterns in darker teal.
The left side has space for text "vconv" and subtitle.
Modern, tech startup aesthetic. Premium feel.
No actual text in the image. 1280x640 format.
--ar 2:1 --v 6.1 --style raw
```

**Prompt (DALL-E 3):**
```
Wide banner 1280x640 for GitHub social preview of vconv video converter. Dark teal and charcoal gradient background. Large geometric play button icon made of polygons in bright teal. Subtle video editing UI elements as faint background. Modern, professional tech startup aesthetic. No text.
```

---

## 5. Splash / Loading Screen

**File:** `public/vconv-splash.png`
**Size:** 800 × 480 pixels (PNG)
**Use:** Future splash screen shown during application startup

**Prompt (Midjourney):**
```
Splash screen for "vconv" video converter application launch.
Dark gradient background from #0B1A2E to #1A1A2E.
Centered subtle glowing film frame icon made of thin teal lines.
Very faint grid pattern overlay suggesting a video editing timeline.
The bottom third has a thin horizontal progress bar area in teal.
Clean, minimal, no clutter. Cinematic feel.
Professional software branding. No text.
800x480 format.
--ar 5:3 --v 6.1 --style raw
```

**Prompt (DALL-E 3):**
```
Splash screen 800x480 for video converter app. Dark navy gradient. Centered subtle glowing film frame icon in teal. Faint grid overlay suggesting video editing timeline. Thin progress bar area at bottom. Clean minimal cinematic professional feel. No text.
```

---

## 6. Folder Icon (Start Menu Category)

**File:** `public/vconv-folder-icon.png`
**Size:** 48 × 48 pixels (PNG)
**Use:** Start menu folder icon for Multimedia category (optional)

**Prompt (Midjourney):**
```
Tiny 48x48 app icon for a video converter. Must be readable at small size.
Simple geometric play button in teal (#00B4D8) on dark navy circle.
No text, no details. Ultra-minimalist. Glossy circular badge style.
Solid background. Pixel-perfect at 48px.
--ar 1:1 --v 6.1 --style raw
```

---

## Installation

After generating each image, place the file in this `public/` directory.

```bash
# Verify all assets are in place
ls -la public/
# Expected:
#   vconv-icon-256.png        (256x256)
#   vconv-logo-512.png        (512x512, transparent)
#   vconv-about-banner.png    (600x200)
#   vconv-github-social.png   (1280x640)
#   vconv-splash.png          (800x480)
#   vconv-folder-icon.png     (48x48)
```

Then run the install script which will copy them to the appropriate system locations:
```bash
# The install process will:
# - Copy vconv-icon-256.png to /usr/local/share/icons/vconv.png
# - Reference it from the .desktop file
# - Use it in the About dialog
# - Use vconv-github-social.png as the repo social preview
```

## Color Reference

| Name | Hex | Usage |
|------|-----|-------|
| Deep Navy | `#0B1A2E` | Backgrounds |
| Charcoal | `#1A1A2E` | Secondary backgrounds |
| Bright Teal | `#00B4D8` | Primary accent |
| Soft Cyan | `#48CAE4` | Secondary accent |
| White | `#FFFFFF` | Foreground text |
| Light Gray | `#90E0EF` | Muted accent |