"""The German and English workbooks must say the same things.

A translation that silently loses a key produces a workbook with a `KeyError`
in place of a footnote, or — worse, because it looks fine — a sheet built from
the other language's strings. These tests hold the two vocabularies to the same
shape so a string added to one has to be added to the other.
"""

import pytest

from winescraper.de import packaging as pkg
from winescraper.de.sources import UNAVAILABLE
from winescraper.de.text import (CHANNEL_LABELS, COLOUR_LABELS, LANGUAGES,
                                 PACKAGING_LABELS, REASON_HEADINGS, STRINGS,
                                 TRADE_FORMAT_LABELS, Texts)


class TestCompleteness:
    def test_every_string_exists_in_every_language(self):
        missing = {key: sorted(set(LANGUAGES) - set(entry))
                   for key, entry in STRINGS.items()
                   if set(LANGUAGES) - set(entry)}
        assert not missing, f"untranslated: {missing}"

    def test_no_string_is_left_as_the_other_language(self):
        # A copy-pasted German string in the English column is the failure mode
        # this catches; it renders without error and reads as a bug to whoever
        # asked for English.
        same = [key for key, entry in STRINGS.items()
                if entry["de"] == entry["en"] and len(entry["de"]) > 40]
        assert not same, f"identical in both languages: {same}"

    @pytest.mark.parametrize("mapping,name", [
        (PACKAGING_LABELS, "PACKAGING_LABELS"),
        (CHANNEL_LABELS, "CHANNEL_LABELS"),
        (COLOUR_LABELS, "COLOUR_LABELS"),
        (REASON_HEADINGS, "REASON_HEADINGS"),
        (TRADE_FORMAT_LABELS, "TRADE_FORMAT_LABELS"),
    ])
    def test_vocabularies_cover_the_same_keys(self, mapping, name):
        for language in LANGUAGES:
            assert language in mapping, f"{name} has no {language}"
        keys = [set(mapping[language]) for language in LANGUAGES]
        assert keys[0] == keys[1], f"{name} keys differ: {keys[0] ^ keys[1]}"


class TestVocabularies:
    def test_every_container_type_has_a_label(self):
        for language in LANGUAGES:
            for container in (pkg.BAG_IN_BOX, pkg.PET, pkg.CARTON, pkg.POUCH,
                              pkg.CAN, pkg.GLASS, pkg.KEG, pkg.UNKNOWN):
                assert PACKAGING_LABELS[language].get(container), container

    def test_every_channel_used_by_a_source_has_a_label(self):
        from winescraper.de.sources import all_sources
        channels = {cls.channel for cls in all_sources().values()}
        channels |= {channel for _, _, channel, _, _ in UNAVAILABLE}
        for language in LANGUAGES:
            for channel in channels:
                assert channel in CHANNEL_LABELS[language], (language, channel)

    def test_every_trade_format_a_source_uses_has_a_label(self):
        from winescraper.de.sources import TRADE_FORMATS, all_sources
        used = {cls.trade_format for cls in all_sources().values()}
        assert used <= set(TRADE_FORMATS), used - set(TRADE_FORMATS)
        for language in LANGUAGES:
            for value in TRADE_FORMATS:
                assert value in TRADE_FORMAT_LABELS[language], (language, value)

    def test_every_unavailable_reason_has_a_heading(self):
        reasons = {reason for _, _, _, reason, _ in UNAVAILABLE}
        for language in LANGUAGES:
            for reason in reasons:
                assert reason in REASON_HEADINGS[language], (language, reason)


class TestLookup:
    def test_formatting_is_applied(self):
        assert "14.08.2026" in Texts("de")("summary_sub", stamp="14.08.2026")
        assert "14 August 2026" in Texts("en")("summary_sub", stamp="14 August 2026")

    def test_price_basis_maps_to_words(self):
        assert Texts("en").basis("net") == "net (B2B)"
        assert Texts("de").basis("gross") == "brutto"

    def test_an_unknown_language_is_refused(self):
        with pytest.raises(ValueError):
            Texts("fr")

    def test_a_missing_key_names_itself(self):
        with pytest.raises(KeyError, match="no_such_key"):
            Texts("en")("no_such_key")

    def test_unmapped_values_pass_through(self):
        # Country names the parser records but the map does not translate stay
        # as collected rather than becoming blank.
        assert Texts("en").country("Chile") == "Chile"
        assert Texts("en").country("Deutschland") == "Germany"


class TestSheetNames:
    """Excel rejects five characters in a sheet name, and openpyxl raises at
    build time rather than at import — so a name like "Eigenmarke?" passes
    every unit test and breaks the deliverable."""

    FORBIDDEN = set(r"[]:*?/\\")

    def test_no_sheet_name_uses_a_character_excel_refuses(self):
        for key, entry in STRINGS.items():
            if not key.startswith("sheet_"):
                continue
            for language, title in entry.items():
                bad = self.FORBIDDEN & set(title)
                assert not bad, f"{key}/{language}: {title!r} contains {bad}"

    def test_no_sheet_name_exceeds_excels_limit(self):
        for key, entry in STRINGS.items():
            if key.startswith("sheet_"):
                for language, title in entry.items():
                    assert len(title) <= 31, f"{key}/{language}: {title!r}"

    def test_sheet_names_are_unique_within_a_language(self):
        for language in LANGUAGES:
            names = [e[language] for k, e in STRINGS.items() if k.startswith("sheet_")]
            assert len(names) == len(set(names)), f"{language}: duplicate sheet name"
