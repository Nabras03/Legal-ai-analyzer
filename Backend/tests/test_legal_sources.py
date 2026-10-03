from legal_sources import load_avtalslagen, parse_statute


def test_avtalslagen_has_all_41_sections_in_order():
    sections = load_avtalslagen()
    assert [s.id for s in sections] == [f"{n} §" for n in range(1, 42)]


def test_sections_carry_chapter_text_and_link():
    s36 = {s.id: s for s in load_avtalslagen()}["36 §"]
    assert s36.chapter == "3 kap. Om rättshandlingars ogiltighet"
    assert s36.text.startswith("36 § Avtalsvillkor får jämkas")
    assert s36.url == "https://lagen.nu/1915:218#P36"
    assert s36.citation() == "36 § AvtL"


def test_transitional_provisions_are_not_part_of_the_last_section():
    last = load_avtalslagen()[-1]
    assert "träder i kraft" not in last.text


def test_parse_statute_handles_chapters_and_multiline_sections():
    raw = (
        "Lag om test\r\n\r\n1 kap. Första\r\n\r\n1 § Första raden\r\nandra raden.\r\n\r\n"
        "2 §  Med dubbla mellanslag.\r\n\r\n2 kap. Andra\r\n\r\n3 § Sista.\r\n\r\n"
        "Övergångsbestämmelser\r\n\r\n4 § Ska inte med.\r\n"
    )
    sections = parse_statute(raw, "TL", lambda n: f"#P{n}")
    assert [(s.id, s.chapter) for s in sections] == [
        ("1 §", "1 kap. Första"), ("2 §", "1 kap. Första"), ("3 §", "2 kap. Andra"),
    ]
    assert sections[0].text == "1 § Första raden\nandra raden."
    assert sections[2].url == "#P3"
