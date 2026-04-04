"""Unit tests for Telegram MarkdownV2 formatting utilities."""

from utils.telegram_format import bold, escape, format_correction, italic, md_to_telegram


class TestEscape:
    def test_plain_text_unchanged(self):
        assert escape("Hallo Welt") == "Hallo Welt"

    def test_escapes_dots(self):
        assert escape("Satz Nr. 1.") == r"Satz Nr\. 1\."

    def test_escapes_exclamation(self):
        assert escape("Gut gemacht!") == r"Gut gemacht\!"

    def test_escapes_parentheses(self):
        assert escape("(Beispiel)") == r"\(Beispiel\)"

    def test_escapes_brackets(self):
        assert escape("[link]") == r"\[link\]"

    def test_escapes_hyphens(self):
        assert escape("A1-B2") == r"A1\-B2"

    def test_escapes_plus(self):
        assert escape("Dativ + Akkusativ") == r"Dativ \+ Akkusativ"

    def test_escapes_equals(self):
        assert escape("a = b") == r"a \= b"

    def test_escapes_pipes(self):
        assert escape("a | b") == r"a \| b"

    def test_escapes_tildes(self):
        assert escape("~text~") == r"\~text\~"

    def test_escapes_backticks(self):
        assert escape("`code`") == r"\`code\`"

    def test_escapes_hash(self):
        assert escape("#topic") == r"\#topic"

    def test_escapes_curly_braces(self):
        assert escape("{key}") == r"\{key\}"

    def test_escapes_backslash(self):
        assert escape("a\\b") == r"a\\b"

    def test_escapes_asterisk(self):
        assert escape("*bold*") == r"\*bold\*"

    def test_escapes_underscore(self):
        assert escape("_italic_") == r"\_italic\_"

    def test_escapes_gt(self):
        assert escape(">quote") == r"\>quote"

    def test_multiple_special_chars(self):
        assert escape("Gut! (Nr. 1)") == r"Gut\! \(Nr\. 1\)"

    def test_german_umlauts_preserved(self):
        assert escape("Über Größe äußern") == "Über Größe äußern"

    def test_emoji_preserved(self):
        assert escape("Weiter so! 💪") == r"Weiter so\! 💪"


class TestBold:
    def test_wraps_in_asterisks(self):
        assert bold("text") == "*text*"

    def test_with_escaped_content(self):
        assert bold(escape("Hallo!")) == r"*Hallo\!*"


class TestItalic:
    def test_wraps_in_underscores(self):
        assert italic("text") == "_text_"

    def test_with_escaped_content(self):
        assert italic(escape("Gut.")) == r"_Gut\._"


class TestMdToTelegram:
    def test_plain_text_escaped(self):
        assert md_to_telegram("Hallo Welt!") == r"Hallo Welt\!"

    def test_bold_preserved(self):
        assert md_to_telegram("Das ist **wichtig** hier.") == r"Das ist *wichtig* hier\."

    def test_italic_preserved(self):
        assert md_to_telegram("Das ist *kursiv* hier.") == r"Das ist _kursiv_ hier\."

    def test_bold_italic_preserved(self):
        result = md_to_telegram("Das ist ***beides*** hier.")
        assert result == r"Das ist *_beides_* hier\."

    def test_inline_code_preserved(self):
        assert md_to_telegram("Nutze `der Tisch` hier.") == r"Nutze `der Tisch` hier\."

    def test_heading_becomes_bold(self):
        assert md_to_telegram("# Der Dativ") == "*Der Dativ*"

    def test_h2_becomes_bold(self):
        assert md_to_telegram("## Verwendung") == "*Verwendung*"

    def test_heading_with_special_chars(self):
        assert md_to_telegram("# Gut gemacht!") == r"*Gut gemacht\!*"

    def test_list_item(self):
        assert md_to_telegram("- Erster Punkt") == "• Erster Punkt"

    def test_list_item_with_bold(self):
        result = md_to_telegram("- *Ich gebe **dem Kind** ein Buch.*")
        assert result == "• _Ich gebe *dem Kind* ein Buch\\._"

    def test_table_row(self):
        result = md_to_telegram("| Maskulin | **dem** |")
        assert result == "Maskulin \\| *dem*"

    def test_table_separator_removed(self):
        assert md_to_telegram("|---|---|") == ""

    def test_multiline(self):
        md = "# Titel\n\nDas ist **wichtig**.\n\n- Punkt eins\n- Punkt zwei"
        result = md_to_telegram(md)
        lines = result.split("\n")
        assert lines[0] == "*Titel*"
        assert lines[1] == ""
        assert lines[2] == r"Das ist *wichtig*\."
        assert lines[3] == ""
        assert lines[4] == "• Punkt eins"
        assert lines[5] == "• Punkt zwei"

    def test_nested_bold_in_italic(self):
        result = md_to_telegram("*Ich sehe **den Mann**.*")
        assert result == "_Ich sehe *den Mann*\\._"

    def test_special_chars_in_plain_text(self):
        result = md_to_telegram("Frage: (wem?) → Dativ")
        assert result == r"Frage: \(wem?\) → Dativ"

    def test_real_llm_output_snippet(self):
        md = "**1. Indirekte Objekte (wem?)**\n- *Ich gebe **dem Kind** ein Buch.* (Wem?)"
        result = md_to_telegram(md)
        lines = result.split("\n")
        assert "*1\\. Indirekte Objekte \\(wem?\\)*" == lines[0]
        assert lines[1].startswith("• _Ich gebe *dem Kind*")


class TestFormatCorrection:
    def test_error_correction(self):
        result = format_correction(
            has_error=True,
            corrected="Gestern bin ich ins Kino gegangen.",
            error_type="Verbzweitstellung",
            explanation="Das Verb muss an zweiter Stelle stehen.",
            follow_up="Kannst du einen ähnlichen Satz bilden?",
        )
        lines = result.split("\n")
        assert lines[0] == r"✏️ *Gestern bin ich ins Kino gegangen\.*"
        assert lines[1] == r"_Fehlertyp: Verbzweitstellung_"
        assert lines[2] == ""
        assert lines[3] == r"Das Verb muss an zweiter Stelle stehen\."
        assert lines[4] == ""
        assert lines[5] == r"_Kannst du einen ähnlichen Satz bilden?_"

    def test_error_without_type(self):
        result = format_correction(
            has_error=True,
            corrected="Ich habe einen Film gesehen.",
            error_type=None,
            explanation="Akkusativ: einen, nicht ein.",
            follow_up="Versuch es nochmal!",
        )
        lines = result.split("\n")
        assert lines[0] == r"✏️ *Ich habe einen Film gesehen\.*"
        assert lines[1] == ""
        assert lines[2] == r"Akkusativ: einen, nicht ein\."
        assert lines[3] == ""
        assert lines[4] == r"_Versuch es nochmal\!_"

    def test_no_error(self):
        result = format_correction(
            has_error=False,
            corrected=None,
            error_type=None,
            explanation="Perfekt! Dein Satz ist grammatisch korrekt.",
            follow_up="Probier einen Satz mit dem Konjunktiv!",
        )
        lines = result.split("\n")
        assert lines[0] == r"✅ Perfekt\! Dein Satz ist grammatisch korrekt\."
        assert lines[1] == ""
        assert lines[2] == r"_Probier einen Satz mit dem Konjunktiv\!_"

    def test_special_chars_in_all_fields(self):
        result = format_correction(
            has_error=True,
            corrected="Er sagte: (Hallo!)",
            error_type="Zeichensetzung",
            explanation='Nutze „..." statt "...".',
            follow_up="Wie würdest du das anders schreiben?",
        )
        assert r"\(" in result
        assert r"\!" in result
        assert r"\." in result
