# Folder structure

```
kalyanigoswami/                    ← your profile repo (same name as your username)
├── README.md                      ← the profile page
├── assets/
│   ├── images/
│   │   ├── about.gif              ← animated whoami illustration
│   │   ├── sections/              ← full sections, exported 1:1 from the design (animated SVG)
│   │   │   ├── 01-banner.svg
│   │   │   ├── 02-status.svg
│   │   │   ├── 03-whoami-text.svg
│   │   │   ├── 05-projects.svg
│   │   │   ├── 06-toolkit.svg
│   │   │   ├── 07-beyond-code.svg
│   │   │   └── 08-footer.svg
│   │   ├── headings/              ← section titles that sit above live/linked content
│   │   │   ├── 01-whoami.png
│   │   │   ├── 02-ping-me.png
│   │   │   └── 05-by-the-numbers.png
│   │   └── cards/                 ← one clickable card per contact link
│   │       └── email / github / linkedin / x / instagram / medium / devto / portfolio .svg (animated)
│   └── fonts/                     ← embedded into the live stats card
├── scripts/
│   └── stats.py                   ← draws the live badges, stats card and contribution graph
└── .github/
    └── workflows/
        └── profile.yml            ← daily: badges + stats card + contribution graph → "output" branch
```

The `output` branch is created automatically by the workflow.
