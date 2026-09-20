"""Central definition of Flatscreen's appearance design system.

A preset is a complete collection of design-system configuration values split
into concerns: typography, colour, geometry, components, navigation, layout,
dashboard and the household display. The household and one base preset's
resolved configuration drive the generated stylesheets and the semantic
data-attributes on the page.

Resolution order: PRESETS[base_preset] merged with sparse user overrides.
Overrides use dotted keys such as "typography.heading_font" and always win.
"""

import copy

BASELINE_KEY = 'classic'

FONT_STACKS = {
    'humanist': "Arial, Helvetica, sans-serif",
    'system': "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    'rounded': "ui-rounded, 'SF Pro Rounded', 'Segoe UI', 'Hiragino Maru Gothic ProN', Verdana, sans-serif",
    'serif': "Georgia, 'Times New Roman', serif",
    'display-serif': "'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif",
    'monospace': "ui-monospace, 'Cascadia Mono', Consolas, monospace",
}

CONTENT_WIDTHS = {'narrow': 1080, 'standard': 1440, 'wide': 1560, 'full': 0}
DENSITY_SPACE = {'compact': 0.85, 'standard': 1.0, 'spacious': 1.15}
RADIUS_TOKENS = {
    'small': {'--radius': 2, '--radius-lg': 4, '--radius-panel': 2},
    'standard': {'--radius': 4, '--radius-lg': 8, '--radius-panel': 3},
    'large': {'--radius': 8, '--radius-lg': 14, '--radius-panel': 12},
    'xlarge': {'--radius': 14, '--radius-lg': 22, '--radius-panel': 20},
}
SHADOW_TOKENS = {
    'none': 'none',
    'soft': '0 8px 22px rgba(40,40,30,.10)',
    'medium': '0 12px 30px rgba(20,25,20,.14)',
    'strong': '0 18px 44px rgba(15,20,15,.20)',
}


def _presets():
    classic = {
        'name': 'Classic',
        'description': 'The original Flatscreen design, exactly as it shipped.',
        'typography': {
            'body_font': 'humanist', 'heading_font': 'serif',
            'base_size': 16, 'heading_scale': 1.0,
            'h1_min': 2.8, 'h1_max': 5.0, 'h2': 2.0, 'h3': 1.05,
            'body_weight': 400, 'heading_weight': 400,
            'body_line_height': 1.5, 'heading_line_height': 1.05,
            'body_tracking': 0, 'heading_tracking': -0.045,
        },
        'colour': {
            'background': '#f4f1e9', 'surface': '#fffcf5', 'wash': '#e8ebdf',
            'accent': '#bd633b', 'text': '#283e31', 'muted': '#6b7268',
            'border': '#d3d6c9', 'border_strong': '#a9b09f',
            'danger': '#a33728', 'ok': '#657552',
        },
        'geometry': {'radius': 'standard', 'shadow': 'none', 'border': 'standard'},
        'components': {
            'button': 'filled', 'input': 'outlined', 'card': 'flat',
            'status': 'labels', 'list': 'separated',
        },
        'navigation': {'desktop': 'topbar'},
        'layout': {'content_width': 'standard', 'density': 'standard', 'page_header': 'standard'},
        'dashboard': {'style': 'grid', 'cols': 4, 'gutter': 'standard'},
        'display': {'density': 'standard', 'cols': 2, 'clock': 'standard', 'type': 'standard'},
    }
    minimal = {
        'name': 'Minimal',
        'description': 'A restrained, flat, low-noise dashboard with a thin sidebar.',
        'typography': {
            'body_font': 'system', 'heading_font': 'system',
            'base_size': 16, 'heading_scale': 1.0,
            'h1_min': 2.2, 'h1_max': 3.8, 'h2': 1.5, 'h3': 1.0,
            'body_weight': 400, 'heading_weight': 600,
            'body_line_height': 1.55, 'heading_line_height': 1.18,
            'body_tracking': 0, 'heading_tracking': -0.01,
        },
        'colour': {
            'background': '#f7f7f4', 'surface': '#ffffff', 'wash': '#eeeeea',
            'accent': '#73806a', 'text': '#2a2f2a', 'muted': '#70776f',
            'border': '#deded6', 'border_strong': '#b6bab0',
            'danger': '#b0402f', 'ok': '#5f7a58',
        },
        'geometry': {'radius': 'small', 'shadow': 'none', 'border': 'standard'},
        'components': {
            'button': 'flat', 'input': 'underline', 'card': 'flat',
            'status': 'labels', 'list': 'separated',
        },
        'navigation': {'desktop': 'sidebar'},
        'layout': {'content_width': 'narrow', 'density': 'compact', 'page_header': 'compact'},
        'dashboard': {'style': 'sections', 'cols': 1, 'gutter': 'standard'},
        'display': {'density': 'standard', 'cols': 2, 'clock': 'small', 'type': 'standard'},
    }
    soft = {
        'name': 'Soft',
        'description': 'A friendly, rounded, tactile household interface with gentle shadows.',
        'typography': {
            'body_font': 'rounded', 'heading_font': 'rounded',
            'base_size': 17, 'heading_scale': 1.0,
            'h1_min': 2.6, 'h1_max': 4.5, 'h2': 1.75, 'h3': 1.1,
            'body_weight': 500, 'heading_weight': 700,
            'body_line_height': 1.6, 'heading_line_height': 1.12,
            'body_tracking': 0, 'heading_tracking': -0.02,
        },
        'colour': {
            'background': '#fdf2e7', 'surface': '#fffaf3', 'wash': '#f9e9d7',
            'accent': '#d07a47', 'text': '#493726', 'muted': '#97795f',
            'border': '#eeddc6', 'border_strong': '#d9c2a5',
            'danger': '#b25a3c', 'ok': '#7d9968',
        },
        'geometry': {'radius': 'xlarge', 'shadow': 'soft', 'border': 'standard'},
        'components': {
            'button': 'pill', 'input': 'filled', 'card': 'elevated',
            'status': 'pills', 'list': 'roomy',
        },
        'navigation': {'desktop': 'topbar'},
        'layout': {'content_width': 'wide', 'density': 'spacious', 'page_header': 'standard'},
        'dashboard': {'style': 'cards', 'cols': 2, 'gutter': 'large'},
        'display': {'density': 'spacious', 'cols': 2, 'clock': 'large', 'type': 'large'},
    }
    editorial = {
        'name': 'Editorial',
        'description': 'A typography-first layout with strong hierarchy and a structured, publication-like plan.',
        'typography': {
            'body_font': 'humanist', 'heading_font': 'display-serif',
            'base_size': 17, 'heading_scale': 1.0,
            'h1_min': 3.1, 'h1_max': 6.5, 'h2': 2.5, 'h3': 1.25,
            'body_weight': 400, 'heading_weight': 700,
            'body_line_height': 1.7, 'heading_line_height': 1.0,
            'body_tracking': 0, 'heading_tracking': -0.015,
        },
        'colour': {
            'background': '#faf7ef', 'surface': '#fffdf6', 'wash': '#f0ebdd',
            'accent': '#a23c2a', 'text': '#211e17', 'muted': '#6f675a',
            'border': '#d7d0bf', 'border_strong': '#a89f8c',
            'danger': '#9c3626', 'ok': '#60795a',
        },
        'geometry': {'radius': 'small', 'shadow': 'none', 'border': 'standard'},
        'components': {
            'button': 'outlined', 'input': 'underline', 'card': 'minimal',
            'status': 'labels', 'list': 'separated',
        },
        'navigation': {'desktop': 'slim'},
        'layout': {'content_width': 'wide', 'density': 'standard', 'page_header': 'prominent'},
        'dashboard': {'style': 'editorial', 'cols': 2, 'gutter': 'standard'},
        'display': {'density': 'spacious', 'cols': 2, 'clock': 'large', 'type': 'large'},
    }
    dense = {
        'name': 'Dashboard',
        'description': 'A compact, information-dense layout built for busy screens and wall displays.',
        'typography': {
            'body_font': 'system', 'heading_font': 'system',
            'base_size': 15, 'heading_scale': 0.95,
            'h1_min': 2.0, 'h1_max': 3.4, 'h2': 1.4, 'h3': 0.95,
            'body_weight': 500, 'heading_weight': 700,
            'body_line_height': 1.45, 'heading_line_height': 1.2,
            'body_tracking': -0.005, 'heading_tracking': -0.02,
        },
        'colour': {
            'background': '#f2f3ef', 'surface': '#ffffff', 'wash': '#e8ebe3',
            'accent': '#b04a22', 'text': '#1d221e', 'muted': '#4c544d',
            'border': '#cdd2c8', 'border_strong': '#98a093',
            'danger': '#a23025', 'ok': '#3f6f55',
        },
        'geometry': {'radius': 'small', 'shadow': 'none', 'border': 'standard'},
        'components': {
            'button': 'square', 'input': 'outlined', 'card': 'bordered',
            'status': 'dots', 'list': 'compact',
        },
        'navigation': {'desktop': 'compact'},
        'layout': {'content_width': 'full', 'density': 'compact', 'page_header': 'compact'},
        'dashboard': {'style': 'grid', 'cols': 4, 'gutter': 'compact'},
        'display': {'density': 'dense', 'cols': 3, 'clock': 'small', 'type': 'compact'},
    }
    return {
        'classic': classic,
        'minimal': minimal,
        'soft': soft,
        'editorial': editorial,
        'dense': dense,
    }


PRESETS = _presets()

PRESET_CHOICES = [(key, preset['name']) for key, preset in PRESETS.items()]


classic_defaults = lambda: {'base_preset': 'classic', 'overrides': {}}


def classic_overrides():
    return {}


def preset_keys():
    return list(PRESETS)


def preset_config(key):
    return dict(PRESETS[key])


def apply_override(config, dotted_key, value):
    section, _, field = dotted_key.partition('.')
    config.setdefault(section, {})[field] = value


def resolve_config(base_preset, overrides=None):
    """Resolved nested configuration for a preset plus sparse overrides."""
    config = copy.deepcopy(PRESETS.get(base_preset, PRESETS[BASELINE_KEY]))
    for dotted_key, value in (overrides or {}).items():
        apply_override(config, dotted_key, value)
    return config


def _heading_size(value, scale):
    return f'{value * scale:.2f}'


def build_appearance_css(config):
    """Flatten a resolved config into the :root token stylesheet."""
    typo = config['typography']
    colour = config['colour']
    geometry = config['geometry']
    layout = config['layout']
    scale = typo['heading_scale']
    radius = RADIUS_TOKENS[geometry['radius']]
    base = typo['base_size']
    width = CONTENT_WIDTHS.get(layout['content_width'], 1440)
    lines = [':root{']
    lines.append(f'--paper:{colour["background"]};')
    lines.append(f'--ink:{colour["text"]};')
    lines.append(f'--muted:{colour["muted"]};')
    lines.append(f'--line:{colour["border"]};')
    lines.append(f'--accent:{colour["accent"]};')
    lines.append(f'--wash:{colour["wash"]};')
    lines.append(f'--white:{colour["surface"]};')
    lines.append(f'--danger:{colour["danger"]};')
    lines.append(f'--ok:{colour["ok"]};')
    lines.append(f'--border-strong:{colour["border_strong"]};')
    lines.append(f'--font-body:{FONT_STACKS[typo["body_font"]]};')
    lines.append(f'--font-heading:{FONT_STACKS[typo["heading_font"]]};')
    lines.append(f'--base-size:{base}px;')
    h1min = _heading_size(typo['h1_min'], scale)
    h1max = _heading_size(typo['h1_max'], scale)
    lines.append(f'--h1-size:clamp({h1min}rem,5vw,{h1max}rem);')
    lines.append(f'--h2-size:{_heading_size(typo["h2"], scale)}rem;')
    lines.append(f'--h3-size:{_heading_size(typo["h3"], scale)}rem;')
    lines.append(f'--body-weight:{typo["body_weight"]};')
    lines.append(f'--heading-weight:{typo["heading_weight"]};')
    lines.append(f'--body-lh:{typo["body_line_height"]};')
    lines.append(f'--heading-lh:{typo["heading_line_height"]};')
    lines.append(f'--h2-lh:{typo["heading_line_height"] + 0.1:.2f};')
    lines.append(f'--body-ls:{typo["body_tracking"]}em;')
    lines.append(f'--heading-ls:{typo["heading_tracking"]}em;')
    lines.append(f'--radius:{radius["--radius"]}px;')
    lines.append(f'--radius-lg:{radius["--radius-lg"]}px;')
    lines.append(f'--radius-panel:{radius["--radius-panel"]}px;')
    lines.append(f'--shadow-card:{SHADOW_TOKENS[geometry["shadow"]]};')
    lines.append(f'--border-width:{"2px" if geometry["border"] == "strong" else "1px"};')
    lines.append(f'--space:{DENSITY_SPACE.get(layout["density"], 1) * 1:.2f};')
    if width:
        lines.append(f'--content-max:{width}px;')
    lines.append(f'font-size:{base}px;line-height:{typo["body_line_height"]};')
    lines.append('}')
    return '\n'.join(lines)


def build_display_css(config):
    """Flatten a resolved config's display section into a small token sheet."""
    display = config['display']
    colour = config['colour']
    lines = [':root{']
    lines.append(f'--display-scale:{"1" if display["type"] == "standard" else "0.92" if display["type"] == "compact" else "1.1"};')
    lines.append(f'--ok:{colour["ok"]};--paper:{colour["background"]};--ink:{colour["text"]};--muted:{colour["muted"]};')
    lines.append('}')
    return '\n'.join(lines)


_ATTR_ORDER = [
    ('nav', 'navigation', 'desktop'),
    ('page-width', 'layout', 'content_width'),
    ('density', 'layout', 'density'),
    ('page-header', 'layout', 'page_header'),
    ('dashboard', 'dashboard', 'style'),
    ('dashboard-cols', 'dashboard', 'cols'),
    ('card-style', 'components', 'card'),
    ('button-style', 'components', 'button'),
    ('input-style', 'components', 'input'),
    ('status-style', 'components', 'status'),
    ('list-style', 'components', 'list'),
    ('radius', 'geometry', 'radius'),
    ('shadow', 'geometry', 'shadow'),
]


def appearance_attrs(config):
    return ' '.join(f'data-{name}="{config[section][field]}"' for name, section, field in _ATTR_ORDER)


_DISPLAY_ATTR_ORDER = [
    ('display-density', 'density'),
    ('display-cols', 'cols'),
    ('display-clock', 'clock'),
    ('display-type', 'type'),
]


def display_attrs(config):
    display = config['display']
    return ' '.join(f'data-{name}="{display[field]}"' for name, field in _DISPLAY_ATTR_ORDER)


def theme_color(config):
    return config['colour']['background']


def overrides_diff(base_preset, overrides):
    """Keep only overrides that genuinely differ from the preset's stock values."""
    cleaned = {}
    stock = resolve_config(base_preset)
    for key, value in (overrides or {}).items():
        section, _, field = key.partition('.')
        if section in stock and field in stock[section] and str(value) != str(stock[section][field]):
            cleaned[key] = value
    return cleaned


def is_customised(overrides):
    return bool(overrides)


def overrides_from_legacy(base_preset, legacy_values):
    """Map the old flat appearance_values into sparse overrides for base_preset.

    Used by migration 0005 and kept for any debugging tooling.
    """
    stock = PRESETS.get(base_preset, PRESETS[BASELINE_KEY])
    colour = stock['colour']
    typo = stock['typography']
    overrides = {}
    legacy = legacy_values or {}

    def keep(section, field, value):
        if section in stock and field in stock[section] and str(value) != str(stock[section][field]):
            overrides[f'{section}.{field}'] = value

    for old, path in {
        'background': ('colour', 'background'), 'surface': ('colour', 'surface'),
        'wash': ('colour', 'wash'), 'accent': ('colour', 'accent'),
        'text': ('colour', 'text'), 'muted': ('colour', 'muted'),
        'border': ('colour', 'border'),
    }.items():
        if old in legacy and str(legacy[old]).lower() != colour[path[1]].lower():
            keep(*path, legacy[old].lower())

    radius_buckets = {0: 'small', 1: 'small', 2: 'small', 3: 'standard', 4: 'standard',
                      5: 'standard', 6: 'standard', 7: 'large', 8: 'large', 9: 'large',
                      10: 'large', 11: 'large', 12: 'large', 13: 'xlarge', 14: 'xlarge'}
    if 'radius' in legacy:
        keep('geometry', 'radius', radius_buckets.get(int(legacy['radius']), 'standard'))
    if 'shadow' in legacy:
        keep('geometry', 'shadow', {0: 'none', 1: 'soft', 2: 'strong'}.get(int(legacy['shadow']), 'none'))
    if 'font_scale' in legacy:
        base = round(16 * int(legacy['font_scale']) / 100)
        if base != typo['base_size']:
            keep('typography', 'base_size', base)
    if 'spacing' in legacy:
        spacing = int(legacy['spacing'])
        density = 'compact' if spacing < 95 else 'standard' if spacing <= 105 else 'spacious'
        keep('layout', 'density', density)
    return overrides