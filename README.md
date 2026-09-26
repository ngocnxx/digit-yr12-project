# Spaced-repetition revision planner for NCEA students (Flask + SQLite API).

> Github Codespaces installation for "ncea-review-navigator"

## 1. Backend

```
cd back-end/

## 1.1. Installing Python libraries
pip install -r requirements.txt

## 1.2. Import Database
python -c "import db; db.init_db()"

## Import to Sqlite verification
sqlite3 navigator.db ".tables"

## 1.3. Flask
python3 -m flask run --host=0.0.0.0 --port=5050
```

## 2. Frondend

```
## 2.1. Move into your frontend folder
cd front-end/

## 2.2. Start Python's built-in light web server on port 5500
python3 -m http.server 5500
```
