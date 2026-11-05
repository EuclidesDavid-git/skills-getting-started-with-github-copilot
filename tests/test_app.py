from copy import deepcopy
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture
def client():
    original_activities = deepcopy(activities)
    with TestClient(app) as test_client:
        yield test_client
    activities.clear()
    activities.update(original_activities)


def activity_url(activity_name, suffix=""):
    return f"/activities/{quote(activity_name, safe='')}{suffix}"


def test_homepage_redirects_to_static_activity_page(client):
    # Arrange
    expected_page = "/static/index.html?v=2"

    # Act
    redirect = client.get("/", follow_redirects=False)
    page = client.get(expected_page)

    # Assert
    assert redirect.status_code == 307
    assert redirect.headers["location"] == expected_page
    assert page.status_code == 200
    assert "Mergington High School" in page.text


def test_activity_catalog_contains_original_and_added_activities(client):
    # Arrange
    expected_names = {
        "Chess Club",
        "Programming Class",
        "Gym Class",
        "Basketball Team",
        "Soccer Club",
        "Track and Field",
        "Art Club",
        "Drama Club",
        "Debate Club",
        "Science Club",
    }
    required_fields = {"description", "schedule", "max_participants", "participants"}

    # Act
    response = client.get("/activities")
    catalog = response.json()

    # Assert
    assert response.status_code == 200
    assert expected_names.issubset(catalog)
    assert all(required_fields.issubset(activity) for activity in catalog.values())
    assert "michael@mergington.edu" in catalog["Chess Club"]["participants"]


def test_signup_adds_participant_and_updates_remaining_spots(client):
    # Arrange
    activity_name = "Art Club"
    email = "pytest-signup@mergington.edu"
    activity_before = client.get("/activities").json()[activity_name]
    spots_before = activity_before["max_participants"] - len(activity_before["participants"])

    # Act
    response = client.post(activity_url(activity_name, "/signup"), params={"email": email})
    activity_after = client.get("/activities").json()[activity_name]

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Signed up {email} for {activity_name}"
    assert activity_after["participants"].count(email) == 1
    assert activity_after["max_participants"] - len(activity_after["participants"]) == spots_before - 1


def test_signup_rejects_duplicate_without_changing_participant_list(client):
    # Arrange
    activity_name = "Art Club"
    email = "pytest-duplicate@mergington.edu"
    signup_url = activity_url(activity_name, "/signup")
    client.post(signup_url, params={"email": email})
    participants_before_duplicate = client.get("/activities").json()[activity_name]["participants"]

    # Act
    response = client.post(signup_url, params={"email": email})
    participants_after_duplicate = client.get("/activities").json()[activity_name]["participants"]

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student is already signed up"
    assert participants_after_duplicate == participants_before_duplicate
    assert participants_after_duplicate.count(email) == 1


def test_signup_rejects_unknown_activity(client):
    # Arrange
    email = "pytest-unknown@mergington.edu"

    # Act
    response = client.post(activity_url("Unknown Activity", "/signup"), params={"email": email})

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_signup_requires_email_query_parameter(client):
    # Arrange
    signup_url = activity_url("Art Club", "/signup")

    # Act
    response = client.post(signup_url)

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "email"


def test_unregister_removes_participant_and_restores_spot(client):
    # Arrange
    activity_name = "Art Club"
    email = "pytest-unregister@mergington.edu"
    signup_url = activity_url(activity_name, "/signup")
    participants_before = client.get("/activities").json()[activity_name]["participants"]
    spots_before = client.get("/activities").json()[activity_name]["max_participants"] - len(participants_before)
    client.post(signup_url, params={"email": email})

    # Act
    response = client.delete(
        activity_url(activity_name, "/participants"), params={"email": email}
    )
    activity_after = client.get("/activities").json()[activity_name]

    # Assert
    assert response.status_code == 200
    assert response.json()["message"] == f"Unregistered {email} from {activity_name}"
    assert email not in activity_after["participants"]
    assert activity_after["max_participants"] - len(activity_after["participants"]) == spots_before


def test_unregister_rejects_unknown_activity(client):
    # Arrange
    email = "pytest-delete-unknown@mergington.edu"

    # Act
    response = client.delete(
        activity_url("Unknown Activity", "/participants"), params={"email": email}
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_unregister_rejects_unregistered_participant(client):
    # Arrange
    activity_name = "Art Club"
    email = "not-registered@mergington.edu"

    # Act
    response = client.delete(
        activity_url(activity_name, "/participants"), params={"email": email}
    )

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"


def test_unregister_requires_email_query_parameter(client):
    # Arrange
    delete_url = activity_url("Art Club", "/participants")

    # Act
    response = client.delete(delete_url)

    # Assert
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "email"


def test_frontend_participant_refresh_contract_and_static_cache(client):
    # Arrange
    script_url = "/static/app.js?v=2"

    # Act
    script = client.get(script_url)
    stylesheet = client.get("/static/styles.css")

    # Assert
    assert script.headers["cache-control"] == "no-store"
    assert "details.participants.forEach" in script.text
    assert "signupForm.reset();\n        await fetchActivities();" in script.text
    assert 'method: "DELETE"' in script.text
    assert "list-style: none" in stylesheet.text