# vconv Implementation Roadmap

> ⚠️ **ARCHIVAL NOTICE:** This roadmap was drafted for the v8.0 PySimpleGUI rewrite. The project has since completed the PyQt6 migration (v9.0.0–v9.2.0). See `docs/future_plan.md` for the current feature roadmap and `CHANGELOG.md` for completed milestones.

## Version 8.0 - Major Rewrite

---

## Phase 1: Foundation (Weeks 1-2)

### Goals
- Establish project structure
- Set up Python environment
- Implement core utilities
- Create basic window

### Tasks

#### Project Setup
- [ ] Initialize git repository (if not already)
- [ ] Create `requirements.txt`
- [ ] Set up `pyproject.toml` for packaging
- [ ] Create modular directory structure:
  ```
  vconv/
  ├── vconv.py
  ├── core/
  ├── ui/
  ├── utils/
  ├── presets/
  └── locales/
  ```

#### Core Utilities
- [ ] **logging.py**: Setup logging with rotation, levels
- [ ] **config.py**: JSON-based config management
- [ ] **i18n.py**: Internationalization system
- [ ] **tools.py**: Dependency checker and installer

#### Dependency Manager
- [ ] Detect `HandBrakeCLI` presence
- [ ] Detect `ffprobe` presence
- [ ] Show install dialog if missing
- [ ] Option A: Auto-install via system package manager
- [ ] Option B: Internal download (download binary)
- [ ] Option C: Provide download link for manual install
- [ ] Verify after installation

#### Basic Window
- [ ] Create main window with PySimpleGUI
- [ ] Status bar showing GPU detection status
- [ ] Placeholder drop zone
- [ ] Basic menu (File, Settings, Help)

---

## Phase 2: Core Features (Weeks 3-4)

### Goals
- Hardware detection
- File handling
- Basic conversion
- Progress tracking

### Tasks

#### Hardware Detection
- [ ] `encoder.py` - Hardware detection module
- [ ] Detect NVIDIA GPU (`nvidia-smi`)
- [ ] Detect Intel GPU (`vainfo`)
- [ ] Detect AMD GPU (`vainfo`, `rocminfo`)
- [ ] Auto-select best encoder based on detection
- [ ] Display detected hardware in status bar
- [ ] Show "Recommended" badge for best encoder

#### File Operations
- [ ] Drag & drop zone implementation
- [ ] File browser dialog
- [ ] Folder drop with recursive scan
- [ ] File validation (check if valid video)
- [ ] `validator.py` - File validation module
- [ ] Show file list with thumbnails (optional)

#### Basic Conversion
- [ ] `converter.py` - HandBrakeCLI wrapper
- [ ] Build command from encoder/quality settings
- [ ] Execute encoding process
- [ ] Stream progress parsing
- [ ] Handle completion/failure

#### Progress Tracking
- [ ] Progress bar in main window
- [ ] ETA calculation
- [ ] Cancel button functionality
- [ ] Job completion notification

---

## Phase 3: Batch & Queue (Weeks 5-6)

### Goals
- Job queue management
- Batch pre-validation
- Individual job control

### Tasks

#### Queue Management
- [ ] `queue.py` - Queue management module
- [ ] Queue data structure (list of Job objects)
- [ ] Add/remove/reorder jobs
- [ ] Job states: pending, running, completed, failed, cancelled
- [ ] Queue window UI (modal dialog)

#### Batch Pre-validation
- [ ] "Check All" button functionality
- [ ] Validate all files BEFORE processing
- [ ] Check: file readable, valid video, exists
- [ ] Check: output path, disk space
- [ ] Collect conflicts and warnings
- [ ] Display resolution dialog
- [ ] Options: Overwrite, Rename, Skip

#### Job Control
- [ ] Cancel individual job
- [ ] Cancel all jobs
- [ ] Pause/Resume (if feasible)
- [ ] Retry failed jobs

---

## Phase 4: Polish & Features (Weeks 7-8)

### Goals
- UI improvements
- Presets system
- Filters
- Subtitle handling

### Tasks

#### UI Enhancements
- [ ] Tab-based interface (Convert, Analyze, Presets, Queue)
- [ ] Better styling with CustomTkinter or themed PySimpleGUI
- [ ] Keyboard shortcuts
- [ ] Tooltips for all controls

#### Presets System
- [ ] `presets/default_presets.json`
- [ ] Preset categories: Fast, Balanced, Quality, Archive
- [ ] Custom preset creation
- [ ] Preset import/export

#### Filters
- [ ] Denoise filter (Light, Medium, Strong)
- [ ] Deinterlace filter
- [ ] Crop/Scale option
- [ ] Rotation filter

#### Subtitle Handling
- [ ] Scan available subtitle tracks
- [ ] Select specific track
- [ ] Burn-in option
- [ ] External SRT loading
- [ ] Language filter

---

## Phase 5: Localization & Themes (Weeks 9-10)

### Goals
- Multi-language support
- Theme system
- RTL layout

### Tasks

#### Internationalization
- [ ] Create `locales/en.json` (English)
- [ ] Create `locales/ar.json` (Classical Arabic)
- [ ] Create `locales/ar_eg.json` (Egyptian Arabic)
- [ ] Language switcher in settings
- [ ] All UI strings externalized

#### RTL Support
- [ ] Detect RTL languages
- [ ] Mirror layout for Arabic
- [ ] Proper text alignment
- [ ] Icon placement adjustment

#### Theme System
- [ ] Dark theme (default)
- [ ] Light theme
- [ ] System theme (follow OS)
- [ ] Theme switcher in settings

---

## Phase 6: Advanced Features (Weeks 11-12)

### Goals
- Parallel processing
- Resume capability
- Advanced options

### Tasks

#### Parallel Processing
- [ ] Option to enable parallel processing
- [ ] Job count selector (2, 3, 4 jobs)
- [ ] Warning dialog about speed trade-off
- [ ] Auto-detect optimal based on CPU cores

#### Resume Capability
- [ ] Save queue state on exit
- [ ] Load queue on startup
- [ ] Option to resume or clear
- [ ] Store partial progress

#### Advanced Options
- [ ] Advanced encoder settings
- [ ] Custom HandBrakeCLI arguments
- [ ] Video filter tuning

---

## Phase 7: Testing & Release (Weeks 13-14)

### Goals
- Testing
- Documentation
- Packaging
- Release

### Tasks

#### Testing
- [ ] Unit tests for core modules
- [ ] Integration tests for conversion flow
- [ ] UI testing with automation
- [ ] Test on multiple distributions

#### Documentation
- [ ] Complete README
- [ ] Inline code documentation
- [ ] API documentation (if applicable)
- [ ] User manual / wiki

#### Packaging
- [ ] Create `setup.py` / `pyproject.toml`
- [ ] Create `.desktop` file for Linux
- [ ] Create AppImage (optional)
- [ ] Create .deb package (optional)

#### Release
- [ ] Version bump to 8.0.0
- [ ] Git tag
- [ ] GitHub release
- [ ] Announce on channels

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        UI Layer                              │
│   ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│   │ Main Window │ │ Dialogs  │ │ Widgets  │ │ Themes   │  │
│   └─────────────┘ └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      Core Layer                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│   │ Encoder  │ │Converter │ │ Analyzer │ │   Queue    │  │
│   │  Module  │ │  Module  │ │  Module  │ │   Manager   │  │
│   └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     Utils Layer                             │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│   │  Config │ │  Logging │ │    i18n  │ │   Tools    │  │
│   └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   External Tools                            │
│      HandBrakeCLI  │  FFprobe  │  System Tools             │
└─────────────────────────────────────────────────────────────┘
```

---

## Dependencies

### Python Packages
```
pysimplegui>=4.60.0
customtkinter>=5.2.0  # Optional, for better theming
```

### System Tools
```
handbrake-cli  # Required
ffmpeg         # Required
python3        # Required
```

---

## Code Standards

### Python Style
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints where beneficial
- Maximum line length: 100 characters
- Docstrings for all public functions

### Naming Conventions
- `snake_case` for functions and variables
- `PascalCase` for classes
- `SCREAMING_SNAKE_CASE` for constants

### Error Handling
- Use specific exception types
- Log all errors with context
- Show user-friendly messages
- Never crash silently

---

## Milestones

| Milestone | Target | Deliverables |
|-----------|--------|--------------|
| M1 | Week 2 | Project structure, basic window |
| M2 | Week 4 | Hardware detection, basic conversion |
| M3 | Week 6 | Queue management, batch processing |
| M4 | Week 8 | Presets, filters, subtitles |
| M5 | Week 10 | Localization, themes |
| M6 | Week 12 | Parallel processing, resume |
| M7 | Week 14 | Testing, packaging, release |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| HandBrakeCLI not available | High | Provide install options |
| GPU not detected | Medium | Fallback to CPU encoder |
| PySimpleGUI compatibility | Low | Test on target distros |
| Performance issues | Medium | Optimize with profiling |

---

*This roadmap is subject to change based on progress and feedback.*
*Last updated: 2026-02-14*