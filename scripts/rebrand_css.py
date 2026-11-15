"""One-off: move frontend/src/index.css from the old dark NVIDIA theme to the Assay palette."""
import pathlib

CSS = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "src" / "index.css"

TOKENS = """  /* Assay palette: ink, lime (fills only), assay green (text), bench */
  --color-ink: #0E1510;
  --color-body: #56605A;
  --color-muted: #8A948C;
  --color-rule: #E4E8E0;
  --color-bench: #F5F7F2;
  --color-paper: #FFFFFF;
  --color-lime: #C6F432;
  --color-lime-wash: #E3F9A6;
  --color-assay: #137A3F;
  --color-assay-wash: #EAF3E3;
  --color-dropped: #D9422F;
  --color-conflict: #B07A00;

  /* Legacy scales remapped so older screens inherit the brand */
  --color-primary-50: #f3faeb;
  --color-primary-100: #eaf3e3;
  --color-primary-200: #d3ebc2;
  --color-primary-300: #a9d98a;
  --color-primary-400: #5fb36a;
  --color-primary-500: #1f9150;
  --color-primary-600: #137a3f;
  --color-primary-700: #0f6232;
  --color-primary-800: #0d4d28;
  --color-primary-900: #0b3d20;
  --color-primary-950: #062613;
  --color-nvidia: #C6F432;
  --color-nvidia-dark: #137A3F;

  /* dark-* was a dark slate theme; inverted onto Assay's light ground */
  --color-dark-50: #0E1510;
  --color-dark-100: #1A241D;
  --color-dark-200: #2B332D;
  --color-dark-300: #3E4640;
  --color-dark-400: #56605A;
  --color-dark-500: #7B847D;
  --color-dark-600: #B7BEB3;
  --color-dark-700: #E4E8E0;
  --color-dark-800: #EEF1EA;
  --color-dark-900: #F5F7F2;
  --color-dark-950: #FFFFFF;

  /* Fonts */
  --font-sans: 'Geist', system-ui, -apple-system, sans-serif;
  --font-display: 'Funnel Display', 'Geist', system-ui, sans-serif;
  --font-prose: 'Newsreader', Georgia, serif;

"""

SWAPS = [
    ("linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)", "#FFFFFF"),
    ("background: #1e293b;", "background: #F5F7F2;"),
    ("background: #475569;", "background: #C9D0C4;"),
    ("background: #64748b;", "background: #8A948C;"),
    ("background: #0f172a !important;", "background: #F5F7F2 !important;"),
    ("border: 1px solid #334155;", "border: 1px solid #E4E8E0;"),
    ("color: #f1f5f9;", "color: #0E1510;"),
    ("color: #cbd5e1;", "color: #2B332D;"),
    ("color: #e2e8f0;", "color: #2B332D;"),
    ("color: #76b900;", "color: #137A3F;"),
    ("#76b900", "#C6F432"),
    ("#22c55e", "#C6F432"),
    ("rgba(30, 41, 59, 0.7)", "rgba(255, 255, 255, 0.92)"),
    ("rgba(71, 85, 105, 0.3)", "#E4E8E0"),
    ("rgba(15, 23, 42, 0.3)", "#F5F7F2"),
    ("rgba(118, 185, 0,", "rgba(198, 244, 50,"),
    ("rgba(34, 197, 94,", "rgba(198, 244, 50,"),
    ("'Fira Code', 'Consolas', monospace", "'Geist Mono', ui-monospace, monospace"),
]


def main() -> None:
    s = CSS.read_text(encoding="utf-8")
    a, b = s.index("  /* Colors */"), s.index("  /* Animations */")
    s = s[:a] + TOKENS + s[b:]
    for old, new in SWAPS:
        s = s.replace(old, new)
    s += """
/* Assay type roles */
.font-display { font-family: var(--font-display); letter-spacing: -0.02em; }
.font-prose { font-family: var(--font-prose); }
"""
    CSS.write_text(s, encoding="utf-8")
    print("rebranded", CSS)


if __name__ == "__main__":
    main()
