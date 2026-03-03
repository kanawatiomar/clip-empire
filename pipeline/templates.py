
from typing import Dict, Any

# Placeholder for category-specific format packs
FORMAT_PACKS: Dict[str, Dict[str, Any]] = {
    "finance_v1": {
        "templates": {
            "pnl_shock": {
                "caption_style": {"font": "Impact", "color": "#00FF00", "emphasis_color": "#FF0000", "size_factor": 1.2},
                "pattern_interrupts": {"zoom_in_freq_s": 4, "punch_in_words": ["loss", "gain", "crash"]},
                "audio_preset": "loud_comp",
                "hook_overlay_text": """PnL Shock Alert!"""
            },
            "hot_take": {
                "caption_style": {"font": "Arial", "color": "#FFFFFF", "emphasis_color": "#FFFF00", "size_factor": 1.0},
                "pattern_interrupts": {"zoom_in_freq_s": 6},
                "audio_preset": "voice_enhance",
                "hook_overlay_text": """What's your take?"""
            }
        }
    },
    "true_crime_v1": {
        "templates": {
            "cold_open_fact": {
                "caption_style": {"font": "Roboto Mono", "color": "#CCCCCC", "emphasis_color": "#FF3333", "size_factor": 0.9},
                "pattern_interrupts": {"static_overlay_freq_s": 8},
                "audio_preset": "suspense_mix",
                "hook_overlay_text": """The truth will shock you.
"""
            }
        }
    }
}

def get_template_config(category_version: str, template_id: str) -> Optional[Dict[str, Any]]:
    pack = FORMAT_PACKS.get(category_version)
    if pack:
        return pack["templates"].get(template_id)
    return None

if __name__ == '__main__':
    finance_template = get_template_config("finance_v1", "pnl_shock")
    print(finance_template)
