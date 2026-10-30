# Surface Brief: CareCompass Wellbeing Journal

- **World:** Light “field notes” journal for an individual noticing their own wellbeing.
- **Audience and use:** A person completing a screening, making a voluntary check-in, and revisiting their own dated records.
- **Visual language:** Ivory-green page ground, clean white surfaces, soft sage actions, concise app-scale headings, and one accessible inline SVG line-icon family. No emoji.
- **Content contract:** Dates anchor observations. History compares result categories and states plainly that the comparison is non-diagnostic and not a measure of progress. Keep next steps calm, direct, and safety-aware.
- **Motion:** Short route and assessment entry, 220ms with a 7px vertical/opacity transition and `cubic-bezier(.2,.72,.2,1)`; honor `prefers-reduced-motion`.
- **Safety and behavior:** Preserve existing non-diagnostic language, support guidance, scoring, consent, persistence, and data flow. Do not imply clinical claims or alter their meaning for visual consistency.
- **Responsive contract:** Centered content up to 1180px; reduce page padding and stack multi-column groups at narrow widths. CSS breakpoints are documented in DESIGN.md; mobile rendering has not been visually verified.
- **Token source:** `carecompass_ui.py` and `.streamlit/config.toml`. Light-only palette and 18px panel / 12px control radii.
