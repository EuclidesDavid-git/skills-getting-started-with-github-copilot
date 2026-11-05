import unittest

from fastapi.testclient import TestClient

from src.app import activities, app


class ActivityApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.original_participants = {
            name: list(activity["participants"])
            for name, activity in activities.items()
        }

    def tearDown(self):
        for name, participants in self.original_participants.items():
            activities[name]["participants"][:] = participants

    def test_homepage_and_activity_catalog(self):
        homepage = self.client.get("/")
        response = self.client.get("/activities")
        activity_data = response.json()

        self.assertEqual(homepage.status_code, 200)
        self.assertIn("Mergington High School", homepage.text)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            {"Chess Club", "Programming Class", "Gym Class"}.issubset(activity_data)
        )
        self.assertTrue(
            {
                "Basketball Team",
                "Soccer Club",
                "Track and Field",
                "Art Club",
                "Drama Club",
                "Debate Club",
                "Science Club",
            }.issubset(activity_data)
        )
        required_fields = {"description", "schedule", "max_participants", "participants"}
        for activity in activity_data.values():
            self.assertTrue(required_fields.issubset(activity))

    def test_signup_rejects_duplicate_and_updates_available_spots(self):
        email = "duplicate-regression@mergington.edu"
        signup_url = "/activities/Art%20Club/signup"
        original_spots = activities["Art Club"]["max_participants"] - len(
            activities["Art Club"]["participants"]
        )

        first_response = self.client.post(signup_url, params={"email": email})
        duplicate_response = self.client.post(signup_url, params={"email": email})
        current_activity = self.client.get("/activities").json()["Art Club"]

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 400)
        self.assertEqual(
            duplicate_response.json()["detail"], "Student is already signed up"
        )
        self.assertEqual(current_activity["participants"].count(email), 1)
        self.assertEqual(
            current_activity["max_participants"] - len(current_activity["participants"]),
            original_spots - 1,
        )

    def test_unregister_removes_participant_and_frees_spot(self):
        email = "unregister-regression@mergington.edu"
        activity_url = "/activities/Art%20Club"
        self.client.post(activity_url + "/signup", params={"email": email})
        delete_response = self.client.delete(
            activity_url + "/participants", params={"email": email}
        )
        current_activity = self.client.get("/activities").json()["Art Club"]

        self.assertEqual(delete_response.status_code, 200)
        self.assertNotIn(email, current_activity["participants"])
        self.assertEqual(
            current_activity["max_participants"] - len(current_activity["participants"]),
            activities["Art Club"]["max_participants"]
            - len(self.original_participants["Art Club"]),
        )

    def test_frontend_renders_participants_and_refreshes_after_signup(self):
        script = self.client.get("/static/app.js?v=2")
        stylesheet = self.client.get("/static/styles.css")

        self.assertEqual(script.headers.get("cache-control"), "no-store")
        self.assertIn("details.participants.forEach", script.text)
        self.assertIn("signupForm.reset();\n        await fetchActivities();", script.text)
        self.assertIn('method: "DELETE"', script.text)
        self.assertIn("list-style: none", stylesheet.text)


if __name__ == "__main__":
    unittest.main()