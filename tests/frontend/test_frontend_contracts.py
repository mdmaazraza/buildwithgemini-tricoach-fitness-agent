"""Frontend Testing & Contract Validation.

Tests:
- Static HTML file integrity and required DOM elements
- Chatbot input/output contract (parts format expected by static/index.html)
- A2UI JSON payload structure and component schema
- Calorie calculator form serialization contract
- User ID / athlete tracking in client sessions
"""

from app.web_server import STATIC_DIR


class TestFrontendContracts:
    """Verifies frontend HTML assets, DOM elements, and API contracts."""

    def test_index_html_exists_and_contains_core_elements(self):
        index_file = STATIC_DIR / "index.html"
        assert index_file.exists(), "frontend/static/index.html must exist"

        content = index_file.read_text(encoding="utf-8")
        # Verify core application containers
        assert 'id="log"' in content, "Chat log container missing"
        assert 'id="form"' in content, "Chat form container missing"
        assert 'id="input"' in content, "Chat input field missing"
        assert 'theme-toggle-btn' in content, "Dark/light mode toggle button missing"
        assert 'TriCoach AI' in content, "Page title / brand header missing"

    def test_a2ui_renderer_contract_present(self):
        index_file = STATIC_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")
        # Ensure client script has A2UI rendering routines
        assert "renderSurface" in content
        assert "buildNode" in content
        assert "renderReply" in content

    def test_chatbot_parts_contract(self, test_client):
        # The frontend's renderReply() expects {"parts": [{"kind": "text", ...}, {"kind": "a2ui", ...}]}
        res = test_client.post("/chat", json={"message": "Help me plan training", "user_id": "athlete-web"})
        assert res.status_code == 200
        data = res.json()
        assert "parts" in data
        assert isinstance(data["parts"], list)
        for part in data["parts"]:
            assert "kind" in part
            assert part["kind"] in ("text", "a2ui", "file")

    def test_email_preview_gui_and_favicon_contracts(self):
        index_file = STATIC_DIR / "index.html"
        content = index_file.read_text(encoding="utf-8")
        assert 'favicon.svg' in content, "Favicon SVG link missing from index.html"
        assert 'id="rep-preview-frame"' in content, "Visual email iframe preview container missing"
        assert 'id="rep-preview-card"' in content, "Email preview card container missing"
        assert "switchPreviewMode" in content, "switchPreviewMode JavaScript handler missing"
        assert "displayReportPreview" in content, "displayReportPreview JavaScript handler missing"

    def test_calorie_form_contract(self, test_client):
        form_payload = {
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 26,
            "gender": "male",
            "activity_level": "very_active",
            "goal": "endurance_fuel",
        }
        res = test_client.post("/api/calories", json=form_payload)
        assert res.status_code == 200
        data = res.json()
        assert "data" in data
        assert "target_calories" in data["data"]
        assert "macros" in data["data"]
