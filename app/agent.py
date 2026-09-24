# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import pathlib
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore, storage

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback


load_dotenv()

# Hardcoded GCP Project ID string (required for Agent Platform compatibility)
PROJECT_ID = "qwiklabs-gcp-02-c57180f0ec07"
BUCKET_NAME = "tricoach-media-qwiklabs-gcp-02-c57180f0ec07"

db = firestore.Client(project=PROJECT_ID, database="(default)")
storage_client = storage.Client(project=PROJECT_ID)
genai_client_global = genai.Client(
    vertexai=True,
    project=PROJECT_ID,
    location="global",
)

# Load Agent Engine resource name from deployment_metadata.json if available
agent_engine_resource_name = None
metadata_path = pathlib.Path(__file__).parent.parent / "deployment_metadata.json"
if metadata_path.exists():
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Could not read deployment_metadata.json: {e}")

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback executed after each turn to store durable session facts (like allergies, dietary preferences) into Vertex AI Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def memory_service_builder():
    """Provides a VertexAiMemoryBankService instance for memory persistence."""
    memory_bank_id = agent_engine_resource_name.split("/")[-1] if agent_engine_resource_name else "2354039001905627136"
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=memory_bank_id,
    )




def generate_motivational_visual(prompt: str, tool_context: ToolContext) -> str:
    """Generates a motivational visual image for an athlete or workout using Gemini 3.1 Flash Lite Image, saves it as a session artifact, and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the image to generate (e.g. "A motivational triathlon athlete crossing the finish line").
        tool_context: The ADK tool context for saving artifacts.

    Returns:
        JSON string containing the public Cloud Storage image URL and status.
    """
    try:
        response = genai_client_global.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return "Error: Image generation model did not return image bytes."

        # 1. Save as artifact in Playground's Artifacts panel using tool_context
        filename = f"visual_{int(datetime.datetime.now().timestamp())}.jpg"
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public Cloud Storage bucket
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"visuals/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

        result = {
            "status": "success",
            "artifact_filename": filename,
            "public_url": public_url,
            "prompt": prompt,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error generating motivational visual: {str(e)}"


def generate_workout_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short video for an item in the triathlon & fitness domain using Google's Omni model (gemini-omni-flash-preview) in the global region. Saves the video as a session artifact and uploads it to public Cloud Storage.

    Args:
        prompt: Detailed description of the video to generate (e.g. "A short video of a triathlon athlete swimming with powerful technique").
        tool_context: The ADK tool context for saving artifacts.

    Returns:
        JSON string containing the public Cloud Storage video URL and status.
    """
    try:
        response = genai_client_global.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["VIDEO"],
            ),
        )

        video_bytes = None
        mime_type = "video/mp4"
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    video_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "video/mp4"
                    break

        if not video_bytes:
            return "Error: Video generation model did not return video bytes."

        # 1. Save as artifact in Playground's Artifacts panel using tool_context
        filename = f"video_{int(datetime.datetime.now().timestamp())}.mp4"
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public Cloud Storage bucket
        bucket = storage_client.bucket(BUCKET_NAME)
        blob_name = f"videos/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{blob_name}"

        result = {
            "status": "success",
            "artifact_filename": filename,
            "public_url": public_url,
            "prompt": prompt,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error generating workout video: {str(e)}"




def geocode_address(address: str) -> str:
    """Converts a street address or location name into geographic coordinates (latitude, longitude) using Google Maps Geocoding API.

    Args:
        address: The address or place name to geocode (e.g., "1600 Amphitheatre Pkwy, Mountain View, CA" or "Boulder, CO").

    Returns:
        JSON string containing the formatted address and location coordinates (latitude, longitude).
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is missing."

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={api_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for address '{address}'. Status: {data.get('status')}"

        first = data["results"][0]
        loc = first["geometry"]["location"]
        result = {
            "formatted_address": first.get("formatted_address"),
            "location": {
                "latitude": loc.get("lat"),
                "longitude": loc.get("lng"),
            },
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error geocoding address: {str(e)}"


def find_nearby_places(latitude: float, longitude: float, place_type: str = "gym", radius_meters: float = 5000.0) -> str:
    """Finds nearby places of a specific type (e.g., gym, park, sports_complex, swimming_pool) near coordinates using Google Places API (New).

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        place_type: Type of place to search for (e.g. "gym", "park", "sports_complex", "swimming_pool").
        radius_meters: Radius in meters around the location (default: 5000 meters).

    Returns:
        JSON string containing a list of nearby places with name, formatted address, and coordinates.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is missing."

    try:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": [place_type],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                    "radius": float(radius_meters),
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby '{place_type}' places found within {radius_meters}m of ({latitude}, {longitude})."

        results = []
        for p in places:
            results.append({
                "name": p.get("displayName", {}).get("text", "Unknown"),
                "address": p.get("formattedAddress", ""),
                "location": {
                    "latitude": p.get("location", {}).get("latitude"),
                    "longitude": p.get("location", {}).get("longitude"),
                },
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error finding nearby places: {str(e)}"



def get_workout_weather(location: str = "New York") -> str:
    """Fetches real-time outdoor weather conditions (temperature, wind, precipitation) for planning outdoor workouts.

    Args:
        location: City name or location (default: "New York").

    Returns:
        JSON string containing current outdoor workout weather conditions.
    """
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(location)}&count=1"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "TriCoach/1.0"})
        with urllib.request.urlopen(req) as resp:
            geo_data = json.loads(resp.read().decode())

        if not geo_data.get("results"):
            return f"Location '{location}' not found."

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        city_name = f"{loc['name']}, {loc.get('admin1', loc.get('country', ''))}"

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m"
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "TriCoach/1.0"})
        with urllib.request.urlopen(req_w) as resp_w:
            weather_data = json.loads(resp_w.read().decode())

        current = weather_data.get("current", {})
        units = weather_data.get("current_units", {})

        result = {
            "location": city_name,
            "temperature": f"{current.get('temperature_2m')} {units.get('temperature_2m')}",
            "feels_like": f"{current.get('apparent_temperature')} {units.get('apparent_temperature')}",
            "humidity": f"{current.get('relative_humidity_2m')} {units.get('relative_humidity_2m')}",
            "precipitation": f"{current.get('precipitation')} {units.get('precipitation')}",
            "wind_speed": f"{current.get('wind_speed_10m')} {units.get('wind_speed_10m')}",
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error fetching workout weather: {str(e)}"



def list_workouts(athlete_id: str = "athlete-01", limit: int = 10) -> str:
    """Retrieves workout logs for an athlete from the Firestore database.

    Args:
        athlete_id: The ID of the athlete (default: "athlete-01").
        limit: Maximum number of workouts to return (default: 10).

    Returns:
        JSON string containing the list of workout documents.
    """
    try:
        query = db.collection("workouts").where("athlete_id", "==", athlete_id).limit(limit)
        docs = query.stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            results.append(data)
        if not results:
            return f"No workouts found for athlete '{athlete_id}'."
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"Error retrieving workouts: {str(e)}"


def get_workout_details(workout_id: str) -> str:
    """Retrieves details of a specific workout log from Firestore.

    Args:
        workout_id: The unique ID of the workout (e.g. "workout-101").

    Returns:
        JSON string containing the workout details or an error message if not found.
    """
    try:
        doc_ref = db.collection("workouts").document(workout_id)
        doc = doc_ref.get()
        if not doc.exists:
            return f"Workout '{workout_id}' not found."
        return json.dumps(doc.to_dict(), indent=2)
    except Exception as e:
        return f"Error retrieving workout '{workout_id}': {str(e)}"


def log_workout(
    activity_type: str,
    duration_minutes: int,
    distance_km: float,
    avg_heart_rate: int,
    intensity_zone: str,
    notes: str,
    athlete_id: str = "athlete-01",
) -> str:
    """Logs a new workout session into the Firestore database.

    Args:
        activity_type: Type of exercise (e.g., "Run", "Bike", "Swim", "Brick", "Strength").
        duration_minutes: Total workout duration in minutes.
        distance_km: Distance covered in kilometers.
        avg_heart_rate: Average heart rate during the workout in BPM.
        intensity_zone: Heart rate or intensity zone (e.g., "Zone 2 (Endurance)", "Zone 3 (Tempo)").
        notes: Personal workout notes or feedback.
        athlete_id: The ID of the athlete (default: "athlete-01").

    Returns:
        Confirmation message with the created workout ID.
    """
    try:
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        workout_id = f"workout-{int(datetime.datetime.now().timestamp())}"
        
        doc_data = {
            "workout_id": workout_id,
            "athlete_id": athlete_id,
            "activity_type": activity_type,
            "duration_minutes": duration_minutes,
            "distance_km": distance_km,
            "avg_heart_rate": avg_heart_rate,
            "intensity_zone": intensity_zone,
            "notes": notes,
            "date": timestamp,
        }
        
        db.collection("workouts").document(workout_id).set(doc_data)
        return f"Successfully logged workout '{workout_id}' ({activity_type}) for athlete '{athlete_id}'!"
    except Exception as e:
        return f"Error logging workout: {str(e)}"


def calculate_training_zones(max_heart_rate: int, resting_heart_rate: int = 60) -> str:
    """Calculates personalized 5-Zone heart rate training ranges using the Karvonen formula.

    Args:
        max_heart_rate: The athlete's maximum heart rate in BPM (e.g. 185).
        resting_heart_rate: The athlete's resting heart rate in BPM (default: 60).

    Returns:
        JSON string containing the calculated heart rate zones and target ranges.
    """
    try:
        hrr = max_heart_rate - resting_heart_rate
        zones = {
            "Zone 1 (Active Recovery)": f"{int(resting_heart_rate + 0.50 * hrr)} - {int(resting_heart_rate + 0.60 * hrr)} BPM",
            "Zone 2 (Endurance / Aerobic)": f"{int(resting_heart_rate + 0.60 * hrr) + 1} - {int(resting_heart_rate + 0.70 * hrr)} BPM",
            "Zone 3 (Tempo / Aerobic Power)": f"{int(resting_heart_rate + 0.70 * hrr) + 1} - {int(resting_heart_rate + 0.80 * hrr)} BPM",
            "Zone 4 (Lactate Threshold)": f"{int(resting_heart_rate + 0.80 * hrr) + 1} - {int(resting_heart_rate + 0.90 * hrr)} BPM",
            "Zone 5 (Anaerobic / VO2 Max)": f"{int(resting_heart_rate + 0.90 * hrr) + 1} - {max_heart_rate} BPM",
        }
        result = {
            "max_heart_rate": max_heart_rate,
            "resting_heart_rate": resting_heart_rate,
            "heart_rate_reserve": hrr,
            "training_zones": zones,
        }
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error calculating training zones: {str(e)}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "TriCoach AI, an elite AI triathlon and fitness coach. You help athletes track workouts, calculate intensity zones, check outdoor weather for training, geocode addresses, find nearby training facilities (gyms, parks, pools), generate motivational visuals, analyze performance trends, safely run Python code calculations in a sandbox, and remember athlete preferences, dietary restrictions, and allergies."
    ),
    workflow_description="Analyze the request, call tools or run python code as needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        list_workouts,
        get_workout_details,
        log_workout,
        calculate_training_zones,
        get_workout_weather,
        geocode_address,
        find_nearby_places,
        generate_motivational_visual,
        generate_workout_video,
        PreloadMemoryTool(),
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)


