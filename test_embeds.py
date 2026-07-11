import embeds


def test_embed_buildings_list_formats_buildings_and_progress():
    buildings = [
        {"name": "Казармы", "tier": 1, "is_builded": 1, "build_cost": 10, "build_progress": 10},
        {"name": "Башня", "tier": 2, "is_builded": 0, "build_cost": 20, "build_progress": 8},
    ]

    embed = embeds.embed_buildings_list(buildings)

    assert embed.title == "🏗️ Постройки"
    assert len(embed.fields) == 2
    assert "Казармы" in embed.fields[0].name
    assert "✅ Завершено" in embed.fields[0].value


def test_embed_researches_list_formats_researches_and_progress():
    researches = [
        {"name": "Астрология", "tier": 2, "is_researched": 0, "research_cost": 12, "research_progress": 4},
    ]

    embed = embeds.embed_researches_list(researches)

    assert embed.title == "🔬 Научные исследования"
    assert len(embed.fields) == 1
    assert "Астрология" in embed.fields[0].name
    assert "⏳ В процессе" in embed.fields[0].value
