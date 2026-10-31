# 📡 TriCoach AI — REST API Documentation

The unified web server (`app/web_server.py`) exposes the following endpoints:

---

## 1. System Endpoints

### `GET /health`
Verifies service availability and database connectivity.

* **Method**: `GET`
* **Response**: `200 OK`
```json
{
  "status": "healthy",
  "service": "tricoach-fitness-agent",
  "database": "connected"
}
```

### `GET /`
Serves the mobile-responsive sports chat web interface (`frontend/static/index.html`).

---

## 2. Chatbot Endpoint

### `POST /chat`
Receives user messages and returns conversational reasoning or A2UI rich surface cards.

* **Method**: `POST`
* **Headers**: `Content-Type: application/json`
* **Request Body**:
```json
{
  "message": "What are my Karvonen training zones?",
  "user_id": "athlete-01"
}
```
* **Response**: `200 OK`
```json
{
  "parts": [
    {
      "kind": "text",
      "text": "❤️ Karvonen Training Zones: Zone 1 (Recovery 50-60%), Zone 2 (Aerobic Base 60-70%), Zone 3 (Tempo 70-80%), Zone 4 (Threshold 80-90%), Zone 5 (Anaerobic / VO2 Max 90-100%)."
    }
  ]
}
```
* **Error Responses**:
  * `400 Bad Request`: Message is empty or whitespace only.
  * `422 Unprocessable Entity`: Missing `message` key.

---

## 3. Nutrition & Calorie Calculation Endpoint

### `POST /api/calories`
Calculates Basal Metabolic Rate (BMR), Total Daily Energy Expenditure (TDEE), goal-adjusted daily calories, and endurance macronutrient targets.

* **Method**: `POST`
* **Headers**: `Content-Type: application/json`
* **Request Body**:
```json
{
  "weight_kg": 72.5,
  "height_cm": 178.0,
  "age": 28,
  "gender": "male",
  "activity_level": "very_active",
  "goal": "endurance_fuel"
}
```
* **Validation Bounds**:
  * `weight_kg`: $20 < \text{weight} \le 350$
  * `height_cm`: $80 < \text{height} \le 260$
  * `age`: $10 \le \text{age} \le 120$
  * `gender`: `"male"`, `"female"` (case-insensitive)
  * `activity_level`: `"sedentary"`, `"light"`, `"moderate"`, `"very_active"`, `"extra_active"`
  * `goal`: `"fat_loss"`, `"aggressive_loss"`, `"maintenance"`, `"lean_bulk"`, `"endurance_fuel"`
* **Response**: `200 OK`
```json
{
  "status": "success",
  "data": {
    "bmr": 1702.5,
    "tdee": 2936.8,
    "goal": "endurance_fuel",
    "calorie_adjustment": 500,
    "target_calories": 3437,
    "macros": {
      "protein_grams": 130.5,
      "protein_calories": 522.0,
      "carbs_grams": 515.6,
      "carbs_calories": 2062.5,
      "fat_grams": 95.5,
      "fat_calories": 859.25
    }
  }
}
```
* **Error Responses**:
  * `400 Bad Request`: Unknown activity level or goal string.
  * `422 Unprocessable Entity`: Input outside realistic physiological bounds.

---

## 4. Workout Logging & History Endpoints

### `POST /api/workouts`
Logs an endurance workout session to the database.

* **Method**: `POST`
* **Request Body**:
```json
{
  "activity_type": "Bike",
  "duration_minutes": 75,
  "distance_km": 38.5,
  "avg_heart_rate": 142,
  "intensity_zone": "Zone 2 (Endurance)",
  "notes": "Steady aerobic ride along river path.",
  "athlete_id": "athlete-01"
}
```
* **Validation Bounds**:
  * `duration_minutes`: $1 \le \text{duration} \le 1440$
  * `distance_km`: $\ge 0$
  * `avg_heart_rate`: $30 < \text{HR} \le 240$
* **Response**: `200 OK`
```json
{
  "status": "success",
  "workout": {
    "workout_id": "workout-1793441897942-a1b2c3",
    "athlete_id": "athlete-01",
    "activity_type": "Bike",
    "duration_minutes": 75,
    "distance_km": 38.5,
    "avg_heart_rate": 142,
    "intensity_zone": "Zone 2 (Endurance)",
    "notes": "Steady aerobic ride along river path.",
    "date": "2026-10-31"
  }
}
```

### `GET /api/workouts`
Retrieves recent workout logs for a given athlete, ordered by date descending.

* **Method**: `GET`
* **Query Parameters**:
  * `athlete_id` (string, optional, default: `"athlete-01"`)
  * `limit` (integer, optional, default: `10`)
* **Response**: `200 OK`
```json
{
  "status": "success",
  "count": 1,
  "workouts": [
    {
      "workout_id": "workout-1793441897942-a1b2c3",
      "athlete_id": "athlete-01",
      "activity_type": "Bike",
      "duration_minutes": 75,
      "distance_km": 38.5,
      "avg_heart_rate": 142,
      "intensity_zone": "Zone 2 (Endurance)",
      "notes": "Steady aerobic ride along river path.",
      "date": "2026-10-31"
    }
  ]
}
```

---

## 5. Feedback Endpoint

### `POST /feedback`
Records athlete satisfaction feedback scores.

* **Method**: `POST`
* **Request Body**:
```json
{
  "score": 5,
  "comment": "Accurate zone recommendations!"
}
```
* **Response**: `200 OK`
```json
{
  "status": "received",
  "feedback": {
    "score": 5,
    "comment": "Accurate zone recommendations!"
  }
}
```
