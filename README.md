# SafeWalk Intelligence API

SafeWalk Intelligence API is a Django-based community safety web application for reporting unsafe walking areas and turning those reports into useful safety intelligence for students, commuters, workers, and residents.

The project includes CRUD reports, JWT API authentication, Django template pages, a custom admin dashboard, Leaflet maps, community confirmations, route notes, saved routes, safety scoring, duplicate detection, report decay, and seed data.

## Unique Features

- Safety Intelligence Score from 0 to 100
- Time-based risk timeline for morning, afternoon, and night
- Community confirmation, dispute, resolved, and needs-review actions
- Duplicate report detection using category, words, location name, and coordinates
- Report decay so old reports lose urgency unless recently confirmed
- Evidence strength and credibility labels
- User trust score with automatic Trusted Reporter promotion
- Area clustering endpoint
- SafeRoute Notes for safer walking tips with map pinning
- Saved walking routes with start and end map pins
- Report location pinning with Leaflet and OpenStreetMap
- Auto location names from map pins using a Django Nominatim reverse-geocoding proxy
- Photo evidence uploads stored in `media/report_photos/`
- Anonymous public and admin-only report visibility
- Admin resolution history
- Auto status suggestions
- Safety heat analytics dashboard
- Interactive Leaflet dashboard map with colored risk markers
- Animated landing page hero video for a polished SafeWalk introduction

## Tech Stack

- Backend: Django
- API: Django REST Framework
- Auth: Django authentication and JWT via Simple JWT
- Database: SQLite for local development, PostgreSQL in production via `DATABASE_URL`
- Frontend: Django Templates, Bootstrap 5, custom CSS, Leaflet
- Filtering: django-filter
- Settings: python-decouple
- Images: Pillow for uploaded report photos

## Project Structure

```text
safewalk_intelligence/
|-- manage.py
|-- requirements.txt
|-- README.md
|-- .env.example
|-- safewalk_intelligence/
|   |-- settings.py
|   |-- urls.py
|   |-- wsgi.py
|   `-- asgi.py
|-- accounts/
|-- reports/
|-- routes/
|-- dashboard/
|-- templates/
`-- static/
```

## Installation

Create and activate a virtual environment:

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

Mac/Linux:

```bash
source venv/bin/activate
```

Install requirements:

```bash
pip install -r requirements.txt
```

Run migrations and seed sample data:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
```

Start the server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## Sample Accounts

| Role | Email | Username | Password |
| --- | --- | --- | --- |
| Admin | admin@safewalk.com | admin | admin123 |
| Normal User | user@safewalk.com | user | user123 |
| Trusted Reporter | trusted@safewalk.com | trusted | trusted123 |

## Main Template Pages

- `/` - Home page
- `/login/` - Login
- `/register/` - Register
- `/dashboard/` - User dashboard with filters and map
- `/reports/` - Safety report list
- `/reports/new/` - Create report
- `/reports/<id>/` - Report detail with Leaflet map, photo evidence, and community comments
- `/reports/<id>/edit/` - Edit report
- `/routes/` - My Safe Routes
- `/routes/notes/` - Route Notes
- `/admin-dashboard/` - Custom admin dashboard
- `/admin-dashboard/reports/` - Admin report verification
- `/admin/` - Django Admin

## API Endpoints

### Auth

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/me/`

### Reports

- `POST /api/reports/`
- `GET /api/reports/`
- `GET /api/reports/<id>/`
- `PUT /api/reports/<id>/`
- `PATCH /api/reports/<id>/`
- `DELETE /api/reports/<id>/`

### Report Intelligence

- `GET /api/reports/<id>/intelligence/`
- `GET /api/reports/duplicates/check/`
- `GET /api/areas/clusters/`
- `GET /api/areas/<location_name>/summary/`
- `GET /api/areas/<location_name>/timeline/`

### Geocoding

- `GET /api/geocoding/reverse/?lat=<latitude>&lng=<longitude>`

### Confirmations

- `POST /api/reports/<id>/confirmations/`
- `GET /api/reports/<id>/confirmations/`
- `DELETE /api/confirmations/<id>/`

### Route Notes

- `POST /api/route-notes/`
- `GET /api/route-notes/`
- `PUT /api/route-notes/<id>/`
- `DELETE /api/route-notes/<id>/`

### Saved Routes

- `POST /api/saved-routes/`
- `GET /api/saved-routes/`
- `GET /api/saved-routes/<id>/`
- `GET /api/saved-routes/<id>/nearby-reports/`
- `PUT /api/saved-routes/<id>/`
- `DELETE /api/saved-routes/<id>/`

### Admin

- `GET /api/admin/dashboard/`
- `GET /api/admin/reports/`
- `PATCH /api/admin/reports/<id>/status/`
- `GET /api/admin/reports/<id>/history/`
- `DELETE /api/admin/reports/<id>/`

## Example API Requests

Login:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"user\",\"password\":\"user123\"}"
```

Create a report:

```bash
curl -X POST http://127.0.0.1:8000/api/reports/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "title=Unsafe shortcut after class" \
  -F "category=unsafe_shortcut" \
  -F "description=The shortcut has very poor lighting and few people after evening classes." \
  -F "location_name=Campus Shortcut near the back gate" \
  -F "latitude=9.741000" \
  -F "longitude=118.735000" \
  -F "risk_level=high" \
  -F "time_observed=20:30:00" \
  -F "day_type=weekday" \
  -F "lighting_condition=dim" \
  -F "crowd_level=few_people" \
  -F "visibility_level=public" \
  -F "photo=@unsafe-area.jpg"
```

Check duplicate reports:

```bash
curl "http://127.0.0.1:8000/api/reports/duplicates/check/?category=dark_area&location_name=PSU%20Main%20Gate%20Road&latitude=9.74185&longitude=118.73508&title=Dark%20gate%20road&description=No%20lights%20near%20school%20gate"
```

## Validation

Safety report submissions validate required fields, text length, valid choices, and coordinate ranges on both the client and server. Anonymous reports automatically hide reporter identity from public users.

Users do not type latitude and longitude in the web forms. They click a Leaflet map to pin the unsafe report location, route note location, or saved route start/end points. The coordinates are saved automatically for duplicate detection, clustering, route analysis, nearby report lookup, safety scoring, and future map features.

Photo evidence is uploaded with Django `ImageField`. Photos are optional, must be JPG, JPEG, PNG, or WEBP, and must be 5MB or smaller. Uploaded files are stored under:

```text
media/report_photos/
```

Leaflet with OpenStreetMap tiles is used for all maps. No paid map API or API key is required.

## Landing Page Video

The homepage hero includes the SafeWalk walking animation as a silent looping MP4:

```text
static/videos/safewalk-walking-animation.mp4
```

The original uploaded `.mov` was converted to a browser-friendly MP4 and optimized to stay lightweight.

## Auto Location Names

When a user pins a location on the Create Report page, Route Notes page, or Saved Routes page, SafeWalk automatically calls:

```text
/api/geocoding/reverse/?lat=<latitude>&lng=<longitude>
```

That Django endpoint proxies OpenStreetMap Nominatim reverse geocoding, returns a short readable place name, and fills the related landmark field. Users can still edit the landmark text. The frontend only auto-fills if the field is empty or was previously auto-filled, so custom user wording is not overwritten.

The geocoding service:

- validates latitude and longitude
- sends a SafeWalk User-Agent to Nominatim
- caches rounded coordinate lookups for 24 hours
- throttles uncached Nominatim calls to about 1 request per second
- handles unavailable location names gracefully

No paid geocoding API key is required.

## Vercel Deployment

This project can run on Vercel through `@vercel/python`, but production should not rely on the local `db.sqlite3` file. That file is ignored by Git and Vercel functions do not provide persistent SQLite storage for user data.

If `DATABASE_URL` is not set on Vercel, the app copies `seed.sqlite3` into Vercel's temporary filesystem and uses that as an emergency database. This prevents the public site from crashing, but the data is not persistent. Use a hosted PostgreSQL database for real deployment data.

Set these Vercel environment variables before redeploying:

```text
SECRET_KEY=<long-random-secret>
DEBUG=False
ALLOWED_HOSTS=safe-walk-intelligence.vercel.app,.vercel.app
CORS_ALLOWED_ORIGINS=https://safe-walk-intelligence.vercel.app
CSRF_TRUSTED_ORIGINS=https://safe-walk-intelligence.vercel.app
DATABASE_URL=<postgres connection string>
OPENWEATHER_API_KEY=<optional>
GOOGLE_CLIENT_ID=<optional>
GOOGLE_CLIENT_SECRET=<optional>
```

## Google Cloud Console Configuration

To enable Google Authentication, configure your Google Cloud Console with these values:

**Authorized JavaScript origins:**
- `http://127.0.0.1:8000`
- `http://localhost:8000`
- `https://safe-walk-intelligence.vercel.app`

**Authorized redirect URIs:**
- `http://127.0.0.1:8000/accounts/google/login/callback/`
- `http://localhost:8000/accounts/google/login/callback/`
- `https://safe-walk-intelligence.vercel.app/accounts/google/login/callback/`

*Note: The redirect URI must exactly match the allauth callback URL.*

After adding `DATABASE_URL`, run the migrations against the production database:

```bash
python manage.py migrate
python manage.py seed_data
```

## Screenshots

Add screenshots here after running locally:

- Home page
- Dashboard map and filters
- Report details page
- Admin dashboard

## Future Improvements

- Interactive map integration
- GPS auto-location detection
- Image upload
- Heatmap visualization
- SMS or email alert system
- Barangay admin dashboard
- School campus safety mode
- Mobile app version
- Offline report saving
- AI-assisted report summary
