from duolingo_anki.wikis import first_parameter, plain_text, template_bodies


def test_example_templates_with_nested_markup():
    wikitext = "{{-noun-|nld}}\n{{bijv-1|Hij eet veel '''{{pn}}'''.|He eats a lot of sprinkles.}}\n{{bijv-1|Op [[brood|boterhammen]].}}"
    bodies = template_bodies(wikitext, "{{bijv-1|")
    assert [plain_text(first_parameter(body), "hagelslag") for body in bodies] == [
        "Hij eet veel hagelslag.",
        "Op boterhammen.",
    ]


def test_unknown_templates_are_dropped():
    assert plain_text("Een {{Q|123}}appelflap{{ref|x}}.", "appelflap") == "Een appelflap."
