# MessMate

MessMate is a Flask app for sharing and claiming meals on campus.

## Run it locally

From PowerShell in the project folder:

```powershell
cd C:\messmate
.\.venv\Scripts\python.exe app.py
```

Open <http://127.0.0.1:5000>. Keep the terminal open while using the app; press **Ctrl+C** there to stop it.

## Where things live

```text
messmate/
├── app.py                 Flask setup, routes, and meal workflows
├── config.py              App and database configuration
├── models.py              User and meal database models
├── init_db.py             Optional database and sample-data initializer
├── requirements.txt       Python package list
├── templates/             HTML pages rendered by Flask
├── static/
│   ├── css/style.css       Main stylesheet used by the pages
│   ├── js/main.js          Shared browser interactions
│   └── images/             Logo and page images
├── instance/               Local database and private meal QR uploads
└── .vscode/settings.json   VS Code workspace settings
```

### Main pages

The deployment entry point is `wsgi.py`; `.gitignore` excludes local-only files from GitHub.

| URL | Template | Purpose |
| --- | --- | --- |
| `/` | `index.html` | Landing page |
| `/login`, `/register` | `login.html`, `register.html` | Sign in and create an account |
| `/dashboard` | `dashboard.html` | Browse available and claimed meals |
| `/post-card` | `post_card.html` | Post a meal and upload its QR screenshot |
| `/my-cards` | `my_cards.html` | View meals you posted or claimed |
| `/card/<id>` | `card_detail.html` | Meal details and QR information |
| `/verify/<token>` | `verify.html` | Confirm meal handover |
| `/profile` | `profile.html` | Manage your account |

## How a meal moves through the app

1. `post_card.html` sends the meal form and QR image to the `post_card` route in `app.py`.
2. `app.py` validates the image, saves the original and a blurred preview under `instance/meal_qrs`, and stores its filename on the `MealCard` model.
3. Claiming a meal changes its status to `claimed`. The dashboard displays the blurred QR with a **CLAIMED** label to other students; the poster and claimant can view the original.
4. The poster confirms the handover on the verification page.

## Files that can look duplicated

- `static/css/style.css` is the stylesheet used by the pages. `style..css` is a legacy import stub for it.
- `static/js/main.js` is the shared script. `script.js` is a legacy placeholder.
- `/my-cards` uses `templates/my_cards.html`; `my_card.html` is an older unused template.
- `/register` uses `templates/register.html`; `registration.html` is an older unused template.

The legacy files are kept in place for reference. Generated Python cache files and the virtual environment are hidden from the VS Code Explorer by the workspace settings.

## Host it on Render

The app uses SQLite for its database and stores uploaded QR screenshots in `instance/`. On Render, both must be on persistent storage if you want account, meal, and QR data to survive restarts and deployments. A free Render web service has an ephemeral filesystem, so local SQLite data and uploaded images can be lost when it restarts or spins down. Use free hosting only with test data. See [Render's free service limits](https://render.com/docs/free) and [persistent disk guide](https://render.com/docs/disks).

### 1. Push the project to GitHub

Create an empty GitHub repository, then run these commands in PowerShell from `C:\messmate` (replace the remote URL with your repository URL):

```powershell
git init
git add .
git commit -m "Prepare MessMate for hosting"
git branch -M main
git remote add origin https://github.com/YOUR_NAME/messmate.git
git push -u origin main
```

`.gitignore` keeps your local virtual environment, database, QR uploads, and `.env` file out of GitHub.

### 2. Create the Render web service

In Render, choose **New → Web Service**, connect the GitHub repository, and enter:

| Setting | Value |
| --- | --- |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn wsgi:app` |

Add an environment variable named `SECRET_KEY` with a unique random value. You can generate one locally with:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Keep that value private. `wsgi.py` creates the database tables and applies the QR filename column when the hosted process starts.

### 3. Keep app data between restarts

For persistent data, choose a paid web service and attach a persistent disk with this mount path:

```text
/opt/render/project/src/instance
```

The app's SQLite database and QR uploads are both stored under that directory. A disk-backed Render service runs as one instance, which is suitable for this small app. Check Render's [current pricing](https://render.com/pricing) before creating a paid service.

After deployment, Render gives the app an `onrender.com` HTTPS address. Pushes to the connected GitHub branch trigger redeploys.
