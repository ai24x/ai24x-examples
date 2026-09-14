"""高端钓友展示平台 API"""
from __future__ import annotations

import time as _time

import psycopg as _pg

from .config import settings


def _get_pg():
    """Build psycopg-compatible connection params from SQLAlchemy URL"""
    from sqlalchemy.engine import make_url
    u = make_url(settings.database_url)
    return _pg.connect(
        host=u.host or "127.0.0.1",
        port=u.port or 5432,
        dbname=u.database or "",
        user=u.username or "",
        password=u.password or "",
    )


# ── 钓友主页 ──

def get_angler_profile(player_id: int):
    c = _get_pg()
    row = c.execute("SELECT * FROM fisher_angler_profiles WHERE player_id = %s", (player_id,)).fetchone()
    assets = c.execute("SELECT * FROM fisher_asset_showcase WHERE player_id = %s ORDER BY created_at DESC", (player_id,)).fetchall()
    catches = c.execute("SELECT * FROM fisher_catch_gallery WHERE player_id = %s ORDER BY created_at DESC LIMIT 12", (player_id,)).fetchall()
    diaries = c.execute("SELECT * FROM fisher_diaries WHERE player_id = %s ORDER BY created_at DESC LIMIT 5", (player_id,)).fetchall()
    player = c.execute("SELECT id,coins,score,rod_level,nickname FROM fisher_players WHERE id = %s", (player_id,)).fetchone()
    fisheries = c.execute("SELECT COUNT(*) FROM fisher_fisheries WHERE owner_id = %s", (player_id,)).fetchone()[0]
    c.close()
    return {"profile": row, "assets": assets, "catches": catches, "diaries": diaries, "player": player, "fisheries": fisheries}


def update_angler_profile(player_id: int, body: dict):
    c = _get_pg()
    c.execute("""
        INSERT INTO fisher_angler_profiles (player_id, bio, real_name, city, years_fishing, favorite_target, gear_list, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (player_id) DO UPDATE SET bio=EXCLUDED.bio, real_name=EXCLUDED.real_name, city=EXCLUDED.city,
        years_fishing=EXCLUDED.years_fishing, favorite_target=EXCLUDED.favorite_target, gear_list=EXCLUDED.gear_list
    """, (player_id, str(body.get("bio",""))[:512], str(body.get("real_name",""))[:64],
          str(body.get("city",""))[:64], max(0,int(body.get("years_fishing",0))),
          str(body.get("favorite_target",""))[:64], str(body.get("gear_list",""))[:512], _time.time()))
    c.commit(); c.close()


def add_asset_showcase(player_id: int, body: dict):
    c = _get_pg()
    c.execute("INSERT INTO fisher_asset_showcase (player_id, asset_type, name, description, price_value, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
              (player_id, str(body.get("asset_type",""))[:32], str(body.get("name",""))[:128],
               str(body.get("description",""))[:512], max(0,int(body.get("price_value",0))), _time.time()))
    c.commit(); c.close()


def add_catch_gallery(player_id: int, body: dict):
    c = _get_pg()
    c.execute("INSERT INTO fisher_catch_gallery (player_id, species, weight_kg, location, story, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
              (player_id, str(body.get("species",""))[:64], max(0,float(body.get("weight_kg",0))),
               str(body.get("location",""))[:128], str(body.get("story",""))[:1024], _time.time()))
    c.execute("UPDATE fisher_angler_profiles SET total_real_catches = COALESCE(total_real_catches,0) + 1 WHERE player_id = %s", (player_id,))
    c.commit(); c.close()


def add_fishing_diary(player_id: int, body: dict):
    c = _get_pg()
    c.execute("INSERT INTO fisher_diaries (player_id, title, content, location, weather, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
              (player_id, str(body.get("title","")).strip()[:128], str(body.get("content",""))[:2048],
               str(body.get("location",""))[:128], str(body.get("weather",""))[:32], _time.time()))
    c.commit(); c.close()


def get_showcase_feed():
    c = _get_pg()
    catches = c.execute("SELECT c.*, p.nickname FROM fisher_catch_gallery c JOIN fisher_players p ON c.player_id=p.id ORDER BY c.created_at DESC LIMIT 20").fetchall()
    diaries = c.execute("SELECT d.*, p.nickname FROM fisher_diaries d JOIN fisher_players p ON d.player_id=p.id ORDER BY d.created_at DESC LIMIT 10").fetchall()
    assets = c.execute("SELECT a.*, p.nickname FROM fisher_asset_showcase a JOIN fisher_players p ON a.player_id=p.id ORDER BY a.created_at DESC LIMIT 10").fetchall()
    c.close()
    return {"catches": catches, "diaries": diaries, "assets": assets}
