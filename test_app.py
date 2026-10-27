import json
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

from app import ChatbotHandler, search_documents


class ChatbotHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ChatbotHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.port)
        encoded_body = json.dumps(body).encode("utf-8") if body is not None else None
        connection.request(
            method,
            path,
            body=encoded_body,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        return response.status, payload

    def test_health_endpoint(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ok"})

    def test_chat_endpoint_requires_a_question(self):
        status, payload = self.request("POST", "/chat", {})
        self.assertEqual(status, 400)
        self.assertIn("question", payload["error"])

    def test_chat_endpoint_retrieves_document_context(self):
        status, payload = self.request(
            "POST", "/chat", {"question": "What is Docker?"}
        )
        self.assertEqual(status, 200)
        self.assertIn("docker", payload["answer"].lower())
        self.assertIn("knowledge/docker.md", payload["answer"])
        self.assertNotIn("knowledge/ci-cd.md", payload["answer"])

    def test_volume_question_returns_one_focused_chunk(self):
        status, payload = self.request(
            "POST", "/chat", {"question": "How do I remove unused Docker volumes?"}
        )
        self.assertEqual(status, 200)
        self.assertIn("docker volume prune", payload["answer"])
        self.assertNotIn("docker image ls", payload["answer"])

    def test_background_container_question_returns_detached_run(self):
        status, payload = self.request(
            "POST",
            "/chat",
            {"question": "How do I run a container in the background?"},
        )
        self.assertEqual(status, 200)
        self.assertIn("docker run -d", payload["answer"])
        self.assertNotIn("docker start <container-name>", payload["answer"])

    def test_create_repository_question_returns_git_init(self):
        status, payload = self.request(
            "POST", "/chat", {"question": "How to create a git repository?"}
        )
        self.assertEqual(status, 200)
        self.assertIn("git init", payload["answer"])
        self.assertNotIn("git clone", payload["answer"])

    def test_combined_question_returns_both_answers(self):
        status, payload = self.request(
            "POST",
            "/chat",
            {
                "question": (
                    "How to create a git repository? "
                    "and how to build a container from compose.yaml file"
                )
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("git init", payload["answer"])
        self.assertIn("docker compose build", payload["answer"])
        self.assertIn("docker compose up --build", payload["answer"])

    def test_create_and_deploy_question_returns_both_answers(self):
        status, payload = self.request(
            "POST",
            "/chat",
            {
                "question": (
                    "How do I create a Git repository and deploy the application "
                    "with Docker Compose?"
                )
            },
        )
        self.assertEqual(status, 200)
        self.assertIn("git init", payload["answer"])
        self.assertIn("docker compose up --build", payload["answer"])
        self.assertIn("docker compose up -d", payload["answer"])

    def test_search_returns_no_results_for_unknown_question(self):
        self.assertEqual(search_documents("What is the weather today?"), [])


if __name__ == "__main__":
    unittest.main()
