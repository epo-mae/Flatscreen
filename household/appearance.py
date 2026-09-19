"""Central definition of household appearance presets.

A preset is a convenient collection of customisation values. The values stored
on the household are always authoritative; a preset only supplies defaults.
All templates, the generated appearance stylesheet and the settings page read
their values from here so nothing is duplicated.
"""


APPEARANCE_FIELDS = (
    'background', 'surface', 'wash', 'accent', 'text', 'muted', 'border',
    'radius', 'font_scale', 'shadow', 'spacing',
)

COLOR_FIELDS = ('background', 'surface', 'wash', 'accent', 'text', 'muted', 'border')

_CSS_VARIABLES = {
    'background': '--paper',
    'surface': '--white',
    'wash': '--wash',
    'accent': '--accent',
    'text': '--ink',
    'muted': '--muted',
    'border': '--line',
}

_SHADOW_VALUES = {
    0: 'none',
    1: '0 6px 16px rgba(40,62,49,.08)',
    2: '0 10px 28px rgba(40,62,49,.16)',
}


def build_presets():
    classic = {
        'background': '#f4f1e9',
        'surface': '#fffcf5',
        'wash': '#e8ebdf',
        'accent': '#bd633b',
        'text': '#283e31',
        'muted': '#6b7268',
        'border': '#d3d6c9',
        'radius': 4,
        'font_scale': 100,
        'shadow': 0,
        'spacing': 100,
    }
    minimal = {
        'background': '#f6f5f1',
        'surface': '#ffffff',
        'wash': '#ecece5',
        'accent': '#94a28e',
        'text': '#202b25',
        'muted': '#767e74',
        'border': '#d8dbd2',
        'radius': 6,
        'font_scale': 100,
        'shadow': 0,
        'spacing': 106,
    }
    warm = {
        'background': '#f6ecdd',
        'surface': '#fffaf0',
        'wash': '#f0e5d3',
        'accent': '#c06a3f',
        'text': '#483728',
        'muted': '#8c7b66',
        'border': '#e0d4c0',
        'radius': 10,
        'font_scale': 100,
        'shadow': 1,
        'spacing': 102,
    }
    contrast = {
        'background': '#fafaf6',
        'surface': '#ffffff',
        'wash': '#e3e7de',
        'accent': '#a63f24',
        'text': '#141c18',
        'muted': '#3f4a43',
        'border': '#9aa39a',
        'radius': 2,
        'font_scale': 105,
        'shadow': 0,
        'spacing': 100,
    }
    modern = {
        'background': '#f2f5f1',
        'surface': '#ffffff',
        'wash': '#e7ece5',
        'accent': '#c05c2e',
        'text': '#22332b',
        'muted': '#6f796f',
        'border': '#c9d3c9',
        'radius': 12,
        'font_scale': 103,
        'shadow': 2,
        'spacing': 106,
    }
    return {
        'classic': {
            'name': 'Classic',
            'description': 'The original Flatscreen look exactly as it shipped.',
            'values': classic,
        },
        'minimal': {
            'name': 'Minimal',
            'description': 'Cleaner, quieter, with gentler colours and more air.',
            'values': minimal,
        },
        'warm': {
            'name': 'Warm',
            'description': 'Softer colours and warmer, more golden surfaces.',
            'values': warm,
        },
        'contrast': {
            'name': 'Contrast',
            'description': 'Stronger separation and crisper readability.',
            'values': contrast,
        },
        'modern': {
            'name': 'Modern',
            'description': 'Rounded cards, lighter shadows and roomier spacing.',
            'values': modern,
        },
    }


PRESETS = build_presets()

PRESET_CHOICES = [(key, preset['name']) for key, preset in PRESETS.items()]

# The Classic preset is the baseline visual design and the upgrade default.
BASELINE_KEY = 'classic'


def classic_defaults():
    """Mutable copy of the stock Classic values (used as model default)."""
    return dict(PRESETS[BASELINE_KEY]['values'])


def preset_keys():
    return list(PRESETS)


def preset_values(key):
    """Stock values for a preset as a fresh dict."""
    return dict(PRESETS[key]['values'])


def values_to_css(values):
    """Turn one set of appearance values into a `:root` stylesheet."""
    lines = [':root{']
    for field in COLOR_FIELDS:
        lines.append(f'{_CSS_VARIABLES[field]}:{values[field]};')
    lines.append(f'--radius:{int(values["radius"])}px;')
    lines.append(f'--shadow:{_SHADOW_VALUES.get(int(values.get("shadow", 0)), "none")};')
    lines.append(f'--space:{int(values["spacing"]) / 100:.2f};')
    lines.append(f'font-size:calc(16px * {int(values["font_scale"]) / 100:.2f});')
    lines.append('}')
    return ''.join(lines)


def swatch_classes():
    """Preset key -> (background, surface, accent, text) for the settings picker.

    The picker renders fixed swatches per preset. The application refuses
    inline style attributes and injected stylesheets, so the swatch colours
    are repeated in app.css under preset card classes instead of being set
    inline from Python.
    """
    return {key: preset['values'] for key, preset in PRESETS.items()}