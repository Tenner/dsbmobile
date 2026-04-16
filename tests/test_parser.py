"""Regression tests for the Untis HTML parser."""
import pytest
from bs4 import BeautifulSoup
from dataclasses import dataclass


# ── Replicate the parser code for standalone testing ───────────────────────

@dataclass
class SubstitutionEntry:
    day: str
    art: str
    class_name: str
    lesson: str
    subject: str
    room: str
    vertr_von: str
    nach: str
    text: str
    raw_text: str


def _cell_text(cell) -> str:
    """Extract text from a table cell, converting <s> to ~~strikethrough~~."""
    parts = []
    for child in cell.children:
        if hasattr(child, "name") and child.name == "s":
            text = child.get_text(strip=True)
            if text:
                parts.append(f"~~{text}~~")
        else:
            text = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
            if text and text != "\xa0":
                parts.append(text)
    return " ".join(parts) if parts else ""


def parse_plan_html(html: str, class_filter: str) -> list[SubstitutionEntry]:
    """Parse Untis substitution plan HTML."""
    soup = BeautifulSoup(html, "html.parser")
    results: list[SubstitutionEntry] = []
    current_day = ""

    for el in soup.find_all(["div", "tr"]):
        if el.name == "div" and "mon_title" in (el.get("class") or []):
            current_day = el.get_text(" ", strip=True)
            continue

        if el.name != "tr":
            continue

        if el.find("th"):
            continue

        cells = el.find_all("td")
        if not cells:
            continue

        raw = el.get_text(" ", strip=True)
        if not raw:
            continue

        if class_filter and class_filter.lower() not in raw.lower():
            continue

        c = [_cell_text(cell) for cell in cells]
        entry = SubstitutionEntry(
            day=current_day,
            art=c[0] if len(c) > 0 else "",
            class_name=c[1] if len(c) > 1 else "",
            lesson=c[2] if len(c) > 2 else "",
            subject=c[3] if len(c) > 3 else "",
            room=c[4] if len(c) > 4 else "",
            vertr_von=c[5] if len(c) > 5 else "",
            nach=c[6] if len(c) > 6 else "",
            text=c[7] if len(c) > 7 else "",
            raw_text=raw,
        )
        results.append(entry)

    return results


# ── Sample HTML fixtures ───────────────────────────────────────────────────

UNTIS_SINGLE_DAY = """
<html><head><title>Untis 2026</title>
<meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1">
</head><body>
<div class="mon_title">16.4.2026 Donnerstag</div>
<table class="mon_list">
<tr class='list'>
  <th class="list">Art</th><th class="list">Klasse(n)</th>
  <th class="list">Stunde</th><th class="list">(Fach)</th>
  <th class="list">Raum</th><th class="list">Vertr. von</th>
  <th class="list">(Le.) nach</th><th class="list">Text</th>
</tr>
<tr class='list odd'>
  <td class="list">Entfall</td><td class="list">05a</td>
  <td class="list">6</td><td class="list"><s>En</s></td>
  <td class="list">---</td><td class="list">&nbsp;</td>
  <td class="list">Entfall</td><td class="list"></td>
</tr>
<tr class='list even'>
  <td class="list">Vertretung</td><td class="list">06a</td>
  <td class="list">3</td><td class="list">Ma</td>
  <td class="list">A110</td><td class="list">&nbsp;</td>
  <td class="list">Oper</td><td class="list">Zusaetzliche Musikstunde</td>
</tr>
</table>
</body></html>
"""

UNTIS_MULTI_DAY = """
<html><body>
<div class="mon_title">16.4.2026 Donnerstag</div>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
<tr class='list odd'>
  <td>Entfall</td><td>08b</td><td>3</td><td><s>Ma</s></td>
  <td>---</td><td></td><td>Entfall</td><td>Klausur</td>
</tr>
</table>
<div class="mon_title">17.4.2026 Freitag</div>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
<tr class='list odd'>
  <td>Raum-Vtr.</td><td>08b</td><td>1</td><td>De</td>
  <td>B103</td><td></td><td></td><td></td>
</tr>
<tr class='list even'>
  <td>Vertretung</td><td>05a</td><td>4</td><td>Ku</td>
  <td>A204</td><td></td><td>Oper</td><td></td>
</tr>
</table>
</body></html>
"""

UNTIS_MULTI_CLASS_ROW = """
<html><body>
<div class="mon_title">16.4.2026 Donnerstag</div>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
<tr class='list odd'>
  <td>Raum-Vtr.</td><td>08b, 08a</td><td>5 - 6</td><td>Re</td>
  <td>C197</td><td></td><td></td><td>Dauerhaft in C14</td>
</tr>
</table>
</body></html>
"""

UNTIS_STRIKETHROUGH_MULTIPLE = """
<html><body>
<div class="mon_title">16.4.2026 Donnerstag</div>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
<tr class='list odd'>
  <td>Vertretung</td><td>06a</td><td>3</td>
  <td><s>Ma</s>Mu</td><td><s>A110</s>MZ1</td>
  <td></td><td>Oper</td><td></td>
</tr>
</table>
</body></html>
"""

UNTIS_EMPTY_TABLE = """
<html><body>
<div class="mon_title">16.4.2026 Donnerstag</div>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
</table>
</body></html>
"""

UNTIS_NO_MON_TITLE = """
<html><body>
<table class="mon_list">
<tr class='list'><th>Art</th><th>Klasse(n)</th><th>Stunde</th>
<th>(Fach)</th><th>Raum</th><th>Vertr. von</th><th>(Le.) nach</th><th>Text</th></tr>
<tr class='list odd'>
  <td>Entfall</td><td>10a</td><td>2</td><td>Ph</td>
  <td>---</td><td></td><td></td><td></td>
</tr>
</table>
</body></html>
"""


# ── Tests: Basic parsing ──────────────────────────────────────────────────

class TestParserBasic:
    """Test basic HTML parsing functionality."""

    def test_parse_single_day(self):
        """Two entries on one day are parsed correctly."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        assert len(entries) == 2

    def test_day_header_extracted(self):
        """Day header from div.mon_title is captured."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        assert entries[0].day == "16.4.2026 Donnerstag"
        assert entries[1].day == "16.4.2026 Donnerstag"

    def test_columns_mapped_correctly(self):
        """Untis columns map to the correct fields."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        e = entries[1]  # Vertretung 06a
        assert e.art == "Vertretung"
        assert e.class_name == "06a"
        assert e.lesson == "3"
        assert e.subject == "Ma"
        assert e.room == "A110"
        assert e.nach == "Oper"
        assert e.text == "Zusaetzliche Musikstunde"

    def test_header_row_skipped(self):
        """Header row with <th> cells is not included in results."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        for e in entries:
            assert e.art != "Art"
            assert e.class_name != "Klasse(n)"

    def test_empty_table_returns_empty(self):
        """Table with only header row returns no entries."""
        entries = parse_plan_html(UNTIS_EMPTY_TABLE, "")
        assert len(entries) == 0

    def test_no_mon_title_uses_empty_day(self):
        """Missing div.mon_title results in empty day string."""
        entries = parse_plan_html(UNTIS_NO_MON_TITLE, "")
        assert len(entries) == 1
        assert entries[0].day == ""


# ── Tests: Multi-day ──────────────────────────────────────────────────────

class TestParserMultiDay:
    """Test parsing across multiple days."""

    def test_multi_day_count(self):
        """Entries from multiple days are all parsed."""
        entries = parse_plan_html(UNTIS_MULTI_DAY, "")
        assert len(entries) == 3

    def test_multi_day_headers(self):
        """Each entry gets the correct day header."""
        entries = parse_plan_html(UNTIS_MULTI_DAY, "")
        assert entries[0].day == "16.4.2026 Donnerstag"
        assert entries[1].day == "17.4.2026 Freitag"
        assert entries[2].day == "17.4.2026 Freitag"

    def test_unique_days(self):
        """Unique days can be extracted from entries."""
        entries = parse_plan_html(UNTIS_MULTI_DAY, "")
        days = list(dict.fromkeys(e.day for e in entries))
        assert days == ["16.4.2026 Donnerstag", "17.4.2026 Freitag"]


# ── Tests: Class filter ───────────────────────────────────────────────────

class TestParserClassFilter:
    """Test class-based filtering."""

    def test_filter_single_class(self):
        """Filter returns only matching class entries."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "05a")
        assert len(entries) == 1
        assert entries[0].class_name == "05a"

    def test_filter_no_match(self):
        """Filter with non-existent class returns empty."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "99z")
        assert len(entries) == 0

    def test_filter_case_insensitive(self):
        """Filter is case-insensitive."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "05A")
        assert len(entries) == 1

    def test_filter_empty_returns_all(self):
        """Empty filter returns all entries."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        assert len(entries) == 2

    def test_filter_multi_class_row(self):
        """Row with multiple classes (08b, 08a) matches either class."""
        entries_b = parse_plan_html(UNTIS_MULTI_CLASS_ROW, "08b")
        entries_a = parse_plan_html(UNTIS_MULTI_CLASS_ROW, "08a")
        assert len(entries_b) == 1
        assert len(entries_a) == 1
        assert entries_b[0].class_name == "08b, 08a"

    def test_filter_across_days(self):
        """Filter works correctly across multiple days."""
        entries = parse_plan_html(UNTIS_MULTI_DAY, "08b")
        assert len(entries) == 2
        assert entries[0].day == "16.4.2026 Donnerstag"
        assert entries[1].day == "17.4.2026 Freitag"

    def test_filter_excludes_other_classes(self):
        """Filter for 08b does not include 05a entries."""
        entries = parse_plan_html(UNTIS_MULTI_DAY, "08b")
        for e in entries:
            assert "05a" not in e.class_name


# ── Tests: Strikethrough ──────────────────────────────────────────────────

class TestParserStrikethrough:
    """Test <s> tag to ~~strikethrough~~ conversion."""

    def test_strikethrough_basic(self):
        """<s>En</s> becomes ~~En~~."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "05a")
        assert entries[0].subject == "~~En~~"

    def test_strikethrough_with_replacement(self):
        """<s>Ma</s>Mu becomes ~~Ma~~ Mu."""
        entries = parse_plan_html(UNTIS_STRIKETHROUGH_MULTIPLE, "")
        assert "~~Ma~~" in entries[0].subject
        assert "Mu" in entries[0].subject

    def test_strikethrough_in_room(self):
        """<s>A110</s>MZ1 becomes ~~A110~~ MZ1 in room field."""
        entries = parse_plan_html(UNTIS_STRIKETHROUGH_MULTIPLE, "")
        assert "~~A110~~" in entries[0].room
        assert "MZ1" in entries[0].room

    def test_no_strikethrough_preserved(self):
        """Normal text without <s> tags is unchanged."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "06a")
        assert entries[0].subject == "Ma"
        assert "~~" not in entries[0].subject


# ── Tests: Edge cases ─────────────────────────────────────────────────────

class TestParserEdgeCases:
    """Test edge cases and robustness."""

    def test_nbsp_handled(self):
        """&nbsp; in cells is treated as empty."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "05a")
        # vertr_von column has &nbsp;
        assert entries[0].vertr_von == ""

    def test_raw_text_populated(self):
        """raw_text contains the full row text."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "05a")
        assert "Entfall" in entries[0].raw_text
        assert "05a" in entries[0].raw_text

    def test_empty_html(self):
        """Empty HTML returns no entries."""
        entries = parse_plan_html("", "")
        assert len(entries) == 0

    def test_garbage_html(self):
        """Non-Untis HTML returns no entries."""
        entries = parse_plan_html("<html><body><p>Hello</p></body></html>", "")
        assert len(entries) == 0

    def test_lesson_range(self):
        """Lesson ranges like '5 - 6' are preserved."""
        entries = parse_plan_html(UNTIS_MULTI_CLASS_ROW, "")
        assert entries[0].lesson == "5 - 6"

    def test_entry_is_dataclass(self):
        """Entries are SubstitutionEntry dataclass instances."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        assert isinstance(entries[0], SubstitutionEntry)

    def test_all_fields_are_strings(self):
        """All fields in SubstitutionEntry are strings."""
        entries = parse_plan_html(UNTIS_SINGLE_DAY, "")
        for e in entries:
            assert isinstance(e.day, str)
            assert isinstance(e.art, str)
            assert isinstance(e.class_name, str)
            assert isinstance(e.lesson, str)
            assert isinstance(e.subject, str)
            assert isinstance(e.room, str)
            assert isinstance(e.vertr_von, str)
            assert isinstance(e.nach, str)
            assert isinstance(e.text, str)
            assert isinstance(e.raw_text, str)
