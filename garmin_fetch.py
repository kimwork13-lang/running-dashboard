"""
garmin_fetch.py
---------------
從 Garmin Connect 抓取最近的跑步數據
安裝依賴：pip install garminconnect
執行方式：python garmin_fetch.py
"""

import json
from datetime import date, timedelta
from garminconnect import Garmin

# ── 設定 ──────────────────────────────────────────
EMAIL = "banc9999@hotmail.com"   # 換成你的 Garmin Connect Email
PASSWORD = "0204tksM"          # 換成你的密碼
DAYS_BACK = 30                      # 抓取最近幾天的數據
# ──────────────────────────────────────────────────


def connect_garmin():
    """登入 Garmin Connect"""
    print("🔗 連線 Garmin Connect...")
    client = Garmin(EMAIL, PASSWORD)
    client.login()
    print("✅ 登入成功！")
    return client


def fetch_running_activities(client, days=30):
    """抓取跑步活動"""
    today = date.today()
    start_date = today - timedelta(days=days)

    print(f"📦 抓取 {start_date} ~ {today} 的活動...")
    activities = client.get_activities_by_date(
        start_date.isoformat(),
        today.isoformat(),
        activitytype="running"
    )
    print(f"✅ 找到 {len(activities)} 筆跑步紀錄")
    return activities


def parse_activity(activity):
    """整理單筆跑步數據成乾淨格式"""
    duration_sec = activity.get("duration", 0)
    distance_m = activity.get("distance", 0)
    distance_km = round(distance_m / 1000, 2)

    # 配速 (min/km)
    pace_sec_per_km = (duration_sec / distance_km) if distance_km > 0 else 0
    pace_min = int(pace_sec_per_km // 60)
    pace_sec = int(pace_sec_per_km % 60)

    return {
        "date": activity.get("startTimeLocal", "")[:10],
        "name": activity.get("activityName", "跑步"),
        "distance_km": distance_km,
        "duration_min": round(duration_sec / 60, 1),
        "pace": f"{pace_min}'{pace_sec:02d}\"",
        "avg_hr": activity.get("averageHR"),
        "max_hr": activity.get("maxHR"),
        "calories": activity.get("calories"),
        "avg_cadence": activity.get("averageRunningCadenceInStepsPerMinute"),
        "elevation_gain_m": activity.get("elevationGain"),
        "avg_stride_length_m": activity.get("avgStrideLength"),
    }


def summarize(runs):
    """計算整體統計"""
    if not runs:
        return {}

    total_distance = sum(r["distance_km"] for r in runs)
    total_duration = sum(r["duration_min"] for r in runs)
    avg_hr_list = [r["avg_hr"] for r in runs if r["avg_hr"]]
    cadence_list = [r["avg_cadence"] for r in runs if r["avg_cadence"]]

    return {
        "total_runs": len(runs),
        "total_distance_km": round(total_distance, 2),
        "total_duration_min": round(total_duration, 1),
        "avg_distance_km": round(total_distance / len(runs), 2),
        "avg_hr": round(sum(avg_hr_list) / len(avg_hr_list), 1) if avg_hr_list else None,
        "avg_cadence": round(sum(cadence_list) / len(cadence_list), 1) if cadence_list else None,
    }


def main():
    client = connect_garmin()
    raw_activities = fetch_running_activities(client, days=DAYS_BACK)

    if not raw_activities:
        print("⚠️ 沒有找到跑步紀錄")
        return

    # 整理數據
    runs = [parse_activity(a) for a in raw_activities]
    stats = summarize(runs)

    # 印出摘要
    print("\n📊 整體統計")
    print(f"  總跑步次數 : {stats['total_runs']} 次")
    print(f"  總距離     : {stats['total_distance_km']} km")
    print(f"  總時間     : {stats['total_duration_min']} 分鐘")
    print(f"  平均距離   : {stats['avg_distance_km']} km / 次")
    print(f"  平均心率   : {stats['avg_hr']} bpm")
    print(f"  平均步頻   : {stats['avg_cadence']} spm")

    print("\n🏃 最近跑步紀錄")
    for r in runs[:5]:
        print(f"  {r['date']}  {r['distance_km']}km  配速 {r['pace']}  HR {r['avg_hr']} bpm")

    # 儲存成 JSON，之後 UI 可以直接讀
    output_path = "running_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"summary": stats, "runs": runs}, f, ensure_ascii=False, indent=2)

    print(f"\n💾 數據已儲存到 {output_path}")


if __name__ == "__main__":
    main()
