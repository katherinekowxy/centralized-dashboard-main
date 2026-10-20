"""Brand tokens: the confirmed colours, readable text, distinct status vocabularies and no leftover dark palette."""

import re
from pathlib import Path

from demo import brand

ROOT = Path(__file__).resolve().parents[1]
STYLED = [ROOT / "app.py", *sorted((ROOT / "demo").glob("*.py"))]
OLD_DARK = re.compile(r"#(0d1928|122237|13233a|101e30|0f1b2b|142337|294056|2c4560|3b5a7[57]|e9f0f5|c7d6e1|9baebc|8a9eae|83aef3|20354a|101f31)\b", re.I)


def test_brand_colours_are_the_confirmed_values() -> None:
    assert (brand.PINK, brand.GREY, brand.WHITE) == ("#E2124F", "#55595C", "#FFFFFF")


def test_text_tokens_meet_wcag_aa_on_white_and_marks_meet_3_to_1() -> None:
    for colour in (brand.INK, brand.INK_2, brand.INK_3, brand.PINK, brand.PINK_DARK, brand.LINK):
        assert brand.contrast(colour) >= 4.5, colour
    assert brand.contrast("#FFFFFF", brand.PINK) >= 4.5  # white text on a primary button
    for vocabulary in (brand.ASSET_STATE, brand.DIAGNOSTIC, brand.WORK_ORDER, brand.PTW_TIMING, brand.PTW_APPROVAL):
        for colour, _, _ in vocabulary.values():
            assert brand.contrast(colour) >= 3, colour


def test_pink_is_never_a_status_colour() -> None:
    for vocabulary in (brand.ASSET_STATE, brand.DIAGNOSTIC, brand.WORK_ORDER, brand.PTW_TIMING, brand.PTW_APPROVAL):
        assert all(colour.upper() not in {brand.PINK, brand.PINK_DARK} for colour, _, _ in vocabulary.values())


def test_states_sharing_a_vocabulary_differ_in_word_and_in_colour_or_shape() -> None:
    for vocabulary in (brand.ASSET_STATE, brand.DIAGNOSTIC, brand.WORK_ORDER, brand.PTW_TIMING, brand.PTW_APPROVAL):
        words = [word for _, word, _ in vocabulary.values()]
        looks = [(colour, shape) for colour, _, shape in vocabulary.values()]
        assert len(set(words)) == len(words) and len(set(looks)) == len(looks)


def test_status_and_source_badges_carry_words() -> None:
    assert "Down" in brand.status_html(brand.ASSET_STATE, "down") and "<svg" in brand.status_html(brand.ASSET_STATE, "down")
    assert "Demo / synthetic data" in brand.demo_badge()
    assert "dashed" in brand.source_badge("synthetic") and "Planned, not built" in brand.source_badge("planned")


def test_no_module_still_uses_the_old_dark_palette() -> None:
    leftovers = {path.name: OLD_DARK.findall(path.read_text(encoding="utf-8")) for path in STYLED}
    assert not {name: found for name, found in leftovers.items() if found}
