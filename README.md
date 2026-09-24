# 🏊🚴🏃 TriCoach AI — Personal Triathlon & Fitness Coach

TriCoach AI is an intelligent triathlon and endurance fitness companion built with the **Google Agent Development Kit (ADK)**. It helps multi-sport athletes log workouts, calculate personalized Karvonen heart rate training zones, check outdoor weather for training sessions, locate nearby training facilities (gyms, pools, parks), generate motivational visual posters and short workout videos, run analytics in a Python code sandbox, and persist athlete preferences across sessions.

![TriCoach AI Demo](./agent_demo.gif)

---

## ⚡ Architecture & Features

### 🧠 Core Agent Reasoning & Models
* **Root Agent Model**: `gemini-flash-latest` (ADK Agent framework).
* **AI Image Generation**: `gemini-3.1-flash-lite-image` for generating motivational triathlon and workout posters.
* **AI Video Generation**: `gemini-omni-flash-preview` in the `global` region for generating short motion videos of athletic workouts.
* **A2UI Rich Display Rendering**: Emits A2UI catalog v0.8 surface updates (`A2uiSchemaManager`, `BasicCatalog`, `a2ui_callback`) for structured Cards, Columns, Rows, Text, and Images.

### 🛠️ Integrated Tools & Services
1. **Firestore Workout Database**:
   * Database: `qwiklabs-gcp-02-c57180f0ec07` (`(default)` database).
   * Tools: `list_workouts`, `get_workout_details`, `log_workout`. Stores workout history (distance, duration, average heart rate, intensity zone, notes).
2. **Cloud Storage Media Repository**:
   * Public Bucket: `tricoach-media-qwiklabs-gcp-02-c57180f0ec07`.
   * Tools: `generate_motivational_visual`, `generate_workout_video`. Saves generated media in-memory via `tool_context.save_artifact` and uploads directly to public GCS returning `https://storage.googleapis.com/<bucket>/<object>` URLs.
3. **Vertex AI Memory Bank Service**:
   * Service: `VertexAiMemoryBankService` (`us-east1`).
   * Tools/Callbacks: `PreloadMemoryTool` and `generate_memories_callback` for persisting athlete preferences, injuries, and dietary notes across sessions.
4. **Agent Engine Python Code Execution Sandbox**:
   * Executor: `AgentEngineSandboxCodeExecutor` for executing custom Python calculations and training metrics safely in an isolated sandbox.
5. **Location & Environmental Services**:
   * `get_workout_weather`: Queries Open-Meteo API for real-time temperature, humidity, wind, and precipitation.
   * `geocode_address`: Resolves street addresses to latitude/longitude via Google Maps Geocoding API.
   * `find_nearby_places`: Searches for nearby gyms, pools, parks, and running tracks via Google Maps Places API.

---

## 📁 Repository Structure

```
.
├── app/
│   ├── agent.py            # Main ADK Agent definition, system instructions, and tool implementations
│   ├── a2ui_utils.py       # A2UI callback transformer for Agent Engine & web renderers
│   └── fast_api_app.py     # FastAPI server hosting agent endpoints
├── frontend/
│   ├── main.py             # FastAPI proxy connecting browser to deployed Agent Engine via A2A
│   ├── static/index.html   # Rebranded sports dialogue chat UI with A2UI renderer
│   └── Dockerfile          # Container build definition for Cloud Run frontend
├── agents-cli-manifest.yaml# Manifest for deployment via agents-cli 1.1.0
├── project_brief.md        # Initial project specification
└── requirements.txt        # Python package dependencies
```

---

## 🚀 Running Locally

### Prerequisites
* Python 3.11+
* Google Cloud Project with Vertex AI, Firestore, and Cloud Storage APIs enabled
* Authenticated `gcloud` credentials (`gcloud auth application-default login`)

### 1. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the project root:
```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=qwiklabs-gcp-02-c57180f0ec07
GOOGLE_CLOUD_LOCATION=us-east1
GOOGLE_MAPS_API_KEY=<your_google_maps_api_key>
```

### 3. Run Agent Development Server (ADK Web)
```bash
adk web --reload_agents --port=8085 .
```
Access the ADK Developer UI in your browser at `http://localhost:8085`.

### 4. Run Custom Frontend Proxy Locally
Navigate to the `frontend/` directory and start the local proxy:
```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="<your_deployed_agent_resource_name>"
export AGENT_DIRECTORY="app"
python3 main.py
```
Open your browser at `http://localhost:8080`.

---

## 🚢 Deployment

### Deploying the Agent Engine Runtime
```bash
agents-cli deploy --project <your-gcp-project-id> --update-env-vars GOOGLE_MAPS_API_KEY="<your_api_key>"
```

### Deploying the Frontend to Cloud Run
```bash
cd frontend
gcloud run deploy tricoach-frontend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=<your_agent_resource_name>,AGENT_DIRECTORY=app"
```

---

## 📋 Status of Planned Features

* ✅ **Workout Logging & Firestore Database**: Implemented & active.
* ✅ **Karvonen Heart Rate Zones Calculator**: Implemented & active.
* ✅ **AI Motivational Image Generation**: Implemented (`gemini-3.1-flash-lite-image`).
* ✅ **AI Workout Video Generation**: Implemented (`gemini-omni-flash-preview`).
* ✅ **Weather & Location Tools**: Implemented (Open-Meteo & Google Maps APIs).
* ✅ **Cross-Session Memory Bank**: Implemented (`VertexAiMemoryBankService`).
* ✅ **A2UI Rich Components**: Implemented (Cards, Columns, Rows, Text, Images).
* ⏳ **Real-time Strava Sync**: *Planned, not yet implemented.*
