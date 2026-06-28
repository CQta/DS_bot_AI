"""
test_database.py
Запуск:
    pytest -v test_database.py
"""

import pytest
import database


@pytest.fixture(autouse=True)
async def setup_db(tmp_path):
    """Создает новую тестовую БД перед каждым тестом."""
    database.DB_PATH = str(tmp_path / "test.db")
    await database.init_db()


@pytest.mark.asyncio
async def test_create_faction():
    faction_id = await database.create_faction(
        discord_user_id="123456",
        discord_name="Player",
        faction_name="Empire",
        race="Human",
        god_name="Zeus",
        path="MAGIC",
        alignment="GOOD",
        body=5,
        mind=6,
        energy=7,
        conc=8
    )

    assert faction_id == 1

    faction = await database.get_faction("123456")

    assert faction is not None
    assert faction["discord_name"] == "Player"
    assert faction["faction_name"] == "Empire"
    assert faction["food"] == 150


@pytest.mark.asyncio
async def test_update_resource():
    faction_id = await database.create_faction(
        "1",
        "User",
        "Empire",
        "Human",
        "God",
        "MAGIC",
        "GOOD",
        5, 5, 5, 5
    )

    await database.update_resource(faction_id, "food", 50)

    faction = await database.get_faction("1")

    assert faction["food"] == 200


@pytest.mark.asyncio
async def test_update_population():
    faction_id = await database.create_faction(
        "2",
        "Player2",
        "Kingdom",
        "Elf",
        "Nature",
        "HOLY",
        "GOOD",
        5, 5, 5, 5
    )

    await database.update_faction_field(faction_id, "population", 120)

    faction = await database.get_faction("2")

    assert faction["population"] == 120


@pytest.mark.asyncio
async def test_log_event():
    await database.log_event(
        turn_number=1,
        faction_id=None,
        event_type="INFO",
        title="Test Event",
        description="This is a test."
    )

    log = await database.fetch_one(
        "SELECT * FROM turn_log"
    )

    assert log is not None
    assert log["title"] == "Test Event"


@pytest.mark.asyncio
async def test_create_technology():
    faction_id = await database.create_faction(
        "3",
        "Researcher",
        "Scientists",
        "Human",
        "Knowledge",
        "TECHNOLOGY",
        "NEUTRAL",
        5, 5, 5, 5
    )

    await database.create_technology(
        faction_id=faction_id,
        name="Steam Engine",
        tier=1,
        research_cost=100
    )

    techs = await database.get_technologies(faction_id)

    assert len(techs) == 1
    assert techs[0]["name"] == "Steam Engine"
    assert techs[0]["progress"] == 0


@pytest.mark.asyncio
async def test_update_technology_progress():
    faction_id = await database.create_faction(
        "4",
        "Scientist",
        "Lab",
        "Human",
        "Science",
        "TECHNOLOGY",
        "GOOD",
        5, 5, 5, 5
    )

    await database.create_technology(
        faction_id,
        "Electricity",
        1,
        100
    )
    tech = (await database.get_technologies(faction_id))[0]
    
    await database.update_technology_progress(
        faction_id,
        tech["id"],
        40
    )

    tech = (await database.get_technologies(faction_id))[0]

    assert tech["progress"] == 40


@pytest.mark.asyncio
async def test_reset_turn_flags():
    faction_id = await database.create_faction(
        "5",
        "Tester",
        "Empire",
        "Human",
        "God",
        "MAGIC",
        "GOOD",
        5, 5, 5, 5
    )

    await database.update_faction_field(
        faction_id,
        "free_pop",
        10
    )

    await database.reset_turn_flags()

    faction = await database.get_faction("5")

    assert faction["free_pop"] == faction["population"]