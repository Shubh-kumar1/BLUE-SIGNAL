import base64
import json
import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch


_test_directory = tempfile.TemporaryDirectory(prefix="bluesignal-api-tests-")
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{_test_directory.name}/test.db?check_same_thread=false",
        "SECRET_KEY": "test-secret-key-that-is-at-least-32-characters",
        "AUTHORITY_REGISTRATION_TOKEN": "test-authority-invitation",
        "CORS_ORIGINS": "http://testserver",
        "LOAD_AI_MODELS": "false",
        "UPLOAD_FOLDER": f"{_test_directory.name}/uploads",
    }
)

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import main
from app.database import Base, SessionLocal, engine
from app.models.ai_job import AIJob
from app.models.post import Post
from app.models.report import Report
from app.services.classification_service import ClassificationResult, ImageClassificationResult


class BlueSignalAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(engine)
        cls.client_context = TestClient(main.app)
        cls.client = cls.client_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client_context.__exit__(None, None, None)
        engine.dispose()
        _test_directory.cleanup()

    def setUp(self):
        main.app.state.ai_job_worker.stop()
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        main.app.state.ai_job_worker.start()

    def register(self, username: str, role: str = "citizen", **extra):
        return self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "testpass123",
                "role": role,
                "full_name": f"Test {username}",
                **extra,
            },
        )

    def login(self, username: str) -> str:
        response = self.client.post(
            "/api/auth/login",
            json={"username": username, "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["token"]

    def auth(self, token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def create_report(self, token: str) -> tuple[dict, str]:
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jX2sAAAAASUVORK5CYII="
        )
        with (
            patch.object(
                main.classification_service,
                "classify_urgency",
                return_value=ClassificationResult("Urgent Panic", 0.97),
            ),
            patch.object(
                main.classification_service,
                "classify_flood_type",
                return_value=ClassificationResult("Urban Flooding", 0.91),
            ),
            patch.object(
                main.classification_service,
                "classify_image",
                return_value=ImageClassificationResult("Urban Flooding", 0.9, "flood"),
            ),
            patch.object(main, "generate_summary", return_value="Flooding reported."),
        ):
            response = self.client.post(
                "/api/auth/citizen/posts",
                headers=self.auth(token),
                data={
                    "title": "Flooded street",
                    "description": "Water is rising near the bridge.",
                    "latitude": "19.076",
                    "longitude": "72.8777",
                    "location_name": "Mumbai",
                },
                files={"image": ("flood.png", png, "image/png")},
            )
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()["status"], "processing")
            deadline = time.monotonic() + 10
            job_status = None
            while time.monotonic() < deadline:
                with SessionLocal() as db:
                    job = db.scalar(
                        select(AIJob).where(
                            AIJob.report_id == response.json()["report_id"]
                        )
                    )
                    job_status = job.status if job else None
                if job_status in {"completed", "failed"}:
                    break
                time.sleep(0.01)
            self.assertEqual(job_status, "completed", "AI job did not finish")
        return response.json(), token

    def test_health_and_test_endpoints(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "success")
        self.assertEqual(self.client.get("/api/test").json()["status"], "success")

    def test_registration_login_and_validation(self):
        self.assertEqual(self.register("citizen1").status_code, 201)
        duplicate = self.register("citizen1")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["error"], "Username already exists")
        self.assertEqual(
            self.client.post(
                "/api/auth/login",
                json={"username": "citizen1", "password": "wrong-password"},
            ).status_code,
            401,
        )
        self.assertEqual(self.login("citizen1") != "", True)
        self.assertEqual(
            self.client.post(
                "/api/auth/register",
                json={
                    "username": "invalid-role",
                    "email": "invalid-role@example.com",
                    "password": "testpass123",
                    "role": "admin",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/auth/register",
                json={
                    "username": "bad-email",
                    "email": "not-an-email",
                    "password": "testpass123",
                },
            ).status_code,
            422,
        )

    def test_authority_registration_requires_invitation(self):
        self.assertEqual(self.register("authority1", role="authority").status_code, 403)
        invited = self.register(
            "authority1",
            role="authority",
            authority_registration_token="test-authority-invitation",
        )
        self.assertEqual(invited.status_code, 201, invited.text)
        token = self.login("authority1")
        self.assertEqual(
            self.client.get(
                "/api/auth/authority/hotspots",
                headers=self.auth(token),
            ).status_code,
            200,
        )

    def test_citizen_report_feed_votes_profiles_and_exports(self):
        self.register("citizen1")
        token = self.login("citizen1")
        self.assertEqual(
            self.client.get(
                "/api/auth/citizen/posts",
                headers=self.auth(token),
            ).json()["posts"],
            [],
        )

        report_response, _ = self.create_report(token)
        post_id = report_response["post_id"]
        report_id = report_response["report_id"]
        self.assertIsNone(report_response["image_classification"])
        own_posts = self.client.get(
            "/api/auth/citizen/posts",
            headers=self.auth(token),
        ).json()["posts"]
        self.assertEqual(own_posts[0]["status"], "verified")
        self.assertTrue(own_posts[0]["media_url"].startswith("/uploads/"))

        feed = self.client.get("/api/posts", headers=self.auth(token))
        self.assertEqual(feed.status_code, 200)
        self.assertEqual(feed.json()["posts"][0]["id"], post_id)
        self.assertEqual(feed.json()["posts"][0]["upvotes"], 0)
        self.assertEqual(
            self.client.post(
                f"/api/posts/{post_id}/vote",
                headers=self.auth(token),
                json={"vote_type": "up"},
            ).status_code,
            400,
        )

        self.register("citizen2")
        second_token = self.login("citizen2")
        for vote_type in ("up", "down"):
            vote = self.client.post(
                f"/api/posts/{post_id}/vote",
                headers=self.auth(second_token),
                json={"vote_type": vote_type},
            )
            self.assertEqual(vote.status_code, 200, vote.text)
        self.assertEqual(
            self.client.post(
                f"/api/posts/{post_id}/vote",
                headers=self.auth(second_token),
                json={"vote_type": "invalid"},
            ).status_code,
            400,
        )
        updated_feed = self.client.get(
            "/api/posts",
            headers=self.auth(second_token),
        ).json()["posts"]
        self.assertEqual(updated_feed[0]["upvotes"], 0)
        self.assertEqual(updated_feed[0]["downvotes"], 1)

        profile = self.client.get(
            "/api/users/citizen1",
            headers=self.auth(second_token),
        )
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.json()["user"]["posts"][0]["id"], post_id)
        self.assertEqual(
            self.client.get(
                "/api/users/99999",
                headers=self.auth(second_token),
            ).status_code,
            404,
        )
        self.assertEqual(report_id > 0, True)

        self.register(
            "authority1",
            role="authority",
            authority_registration_token="test-authority-invitation",
        )
        authority_token = self.login("authority1")
        hotspots = self.client.get(
            "/api/auth/authority/hotspots",
            headers=self.auth(authority_token),
        )
        self.assertEqual(hotspots.status_code, 200)
        self.assertEqual(hotspots.json()["hotspots"][0]["id"], report_id)
        self.assertEqual(
            hotspots.json()["hotspots"][0]["image_classification"]["type"],
            "Urban Flooding",
        )
        json_export = self.client.get(
            f"/api/auth/authority/reports/export?format=json&token={authority_token}"
        )
        self.assertEqual(json_export.status_code, 200)
        self.assertEqual(json.loads(json_export.text)[0]["report_id"], report_id)
        csv_export = self.client.get(
            f"/api/auth/authority/reports/export?format=csv&token={authority_token}"
        )
        self.assertEqual(csv_export.status_code, 200)
        self.assertIn("report_id,post_id,title", csv_export.text)
        self.assertEqual(
            main.csv_safe_value("=HYPERLINK(\"https://example.com\")"),
            "'=HYPERLINK(\"https://example.com\")",
        )

    def test_report_creation_returns_while_ai_inference_is_running(self):
        self.register("citizen1")
        token = self.login("citizen1")
        inference_started = threading.Event()
        release_inference = threading.Event()
        request_finished = threading.Event()
        responses = []
        request_errors = []

        def delayed_classification(text: str) -> ClassificationResult:
            inference_started.set()
            if not release_inference.wait(timeout=5):
                raise TimeoutError("Test did not release background inference")
            return ClassificationResult("Urgent Panic", 0.97)

        def submit_report() -> None:
            try:
                responses.append(
                    self.client.post(
                        "/api/auth/citizen/posts",
                        headers=self.auth(token),
                        json={
                            "title": "Flooded street",
                            "description": "Water is rising near the bridge.",
                        },
                    )
                )
            except Exception as exc:
                request_errors.append(exc)
            finally:
                request_finished.set()

        with (
            patch.object(
                main.classification_service,
                "classify_urgency",
                side_effect=delayed_classification,
            ),
            patch.object(
                main.classification_service,
                "classify_flood_type",
                return_value=ClassificationResult("Urban Flooding", 0.91),
            ),
            patch.object(main, "generate_summary", return_value="Flooding reported."),
        ):
            request_thread = threading.Thread(target=submit_report)
            request_thread.start()
            try:
                self.assertTrue(inference_started.wait(timeout=5))
                self.assertTrue(
                    request_finished.wait(timeout=1),
                    "Report creation waited for AI inference",
                )
                request_thread.join(timeout=5)
                self.assertFalse(request_errors, request_errors)
                self.assertEqual(responses[0].status_code, 202, responses[0].text)
                self.assertEqual(responses[0].json()["status"], "processing")
            finally:
                release_inference.set()
                request_thread.join(timeout=5)

            deadline = time.monotonic() + 5
            job_status = None
            while time.monotonic() < deadline:
                with SessionLocal() as db:
                    job = db.scalar(
                        select(AIJob).where(
                            AIJob.report_id == responses[0].json()["report_id"]
                        )
                    )
                    job_status = job.status if job else None
                if job_status in {"completed", "failed"}:
                    break
                time.sleep(0.01)
            self.assertEqual(job_status, "completed", "Background AI job did not finish")

    def test_ai_failure_marks_report_for_manual_review(self):
        self.register("citizen1")
        token = self.login("citizen1")
        with patch.object(
            main.classification_service,
            "classify_urgency",
            side_effect=RuntimeError("AI model unavailable"),
        ):
            response = self.client.post(
                "/api/auth/citizen/posts",
                headers=self.auth(token),
                json={
                    "title": "Flooded street",
                    "description": "Water is rising near the bridge.",
                },
            )
            self.assertEqual(response.status_code, 202, response.text)

            deadline = time.monotonic() + 5
            job_status = None
            while time.monotonic() < deadline:
                with SessionLocal() as db:
                    job = db.scalar(
                        select(AIJob).where(
                            AIJob.report_id == response.json()["report_id"]
                        )
                    )
                    job_status = job.status if job else None
                if job_status in {"completed", "failed"}:
                    break
                time.sleep(0.01)

        self.assertEqual(job_status, "failed", "Failed AI job was not marked failed")
        with SessionLocal() as db:
            post = db.get(Post, response.json()["post_id"])
            report = db.get(Report, response.json()["report_id"])
            self.assertEqual(post.status, "processing_failed")
            self.assertFalse(report.verified)
            self.assertIn("manually", report.ai_summary)

    def test_classification_endpoints_validate_and_return_results(self):
        with (
            patch.object(
                main.classification_service,
                "classify_urgency",
                return_value=ClassificationResult("Urgent Panic", 0.8),
            ),
            patch.object(
                main.classification_service,
                "classify_flood_type",
                return_value=ClassificationResult("Urban Flooding", 0.9),
            ),
            patch.object(
                main.classification_service,
                "classify_image",
                return_value=ImageClassificationResult("Urban Flooding", 0.9, "flood"),
            ),
        ):
            text_result = self.client.post(
                "/api/classify/text",
                json={"text": "Flood water is rising"},
            )
            self.assertEqual(text_result.status_code, 200)
            self.assertEqual(
                text_result.json()["data"]["urgency_classification"]["class_name"],
                "Urgent Panic",
            )
            self.assertEqual(
                self.client.post(
                    "/api/classify/image",
                    json={"image_path": "/etc/passwd"},
                ).status_code,
                400,
            )
            image_path = main.UPLOAD_FOLDER / "test-image.png"
            image_path.write_bytes(b"test")
            image_result = self.client.post(
                "/api/classify/image",
                json={"image_path": str(image_path)},
            )
            self.assertEqual(image_result.status_code, 200, image_result.text)

    def test_report_upload_rejects_invalid_coordinates_and_image_signatures(self):
        self.register("citizen1")
        token = self.login("citizen1")
        invalid_coordinates = self.client.post(
            "/api/auth/citizen/posts",
            headers=self.auth(token),
            json={"title": "Out of range", "latitude": 91, "longitude": 20},
        )
        self.assertEqual(invalid_coordinates.status_code, 422)

        invalid_image = self.client.post(
            "/api/auth/citizen/posts",
            headers=self.auth(token),
            data={"title": "Invalid image", "description": "Flood report"},
            files={"image": ("flood.png", b"not an image", "image/png")},
        )
        self.assertEqual(invalid_image.status_code, 400)
        self.assertEqual(
            self.client.get(
                "/api/auth/citizen/posts",
                headers=self.auth(token),
            ).json()["posts"],
            [],
        )

    def test_sse_streams_send_authorized_initial_snapshots(self):
        self.register("citizen1")
        citizen_token = self.login("citizen1")
        with self.client.stream(
            "GET",
            f"/api/posts/stream?token={citizen_token}",
        ) as response:
            self.assertEqual(response.status_code, 200)
            first_line = next(response.iter_lines())
            self.assertTrue(first_line.startswith("data: "))
            self.assertEqual(json.loads(first_line[6:]), {"type": "snapshot", "data": []})

        self.assertEqual(
            self.client.get("/api/posts/stream").status_code,
            401,
        )

        self.register(
            "authority1",
            role="authority",
            authority_registration_token="test-authority-invitation",
        )
        authority_token = self.login("authority1")
        with self.client.stream(
            "GET",
            f"/api/auth/authority/hotspots/stream?token={authority_token}",
        ) as response:
            self.assertEqual(response.status_code, 200)
            first_line = next(response.iter_lines())
            self.assertEqual(
                json.loads(first_line[6:]),
                {"type": "snapshot", "data": []},
            )

    def test_classification_unavailable_is_reported_as_service_unavailable(self):
        with patch.object(
            main.classification_service,
            "classify_urgency",
            side_effect=main.ClassificationUnavailableError("not loaded"),
        ):
            response = self.client.post(
                "/api/classify/text",
                json={"text": "flood"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"error": "AI classification is temporarily unavailable"},
        )


if __name__ == "__main__":
    unittest.main()
