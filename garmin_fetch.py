"""
garmin_fetch.py
---------------
從 Garmin Connect 抓取最近的跑步數據，並用 Claude 分析最新一筆紀錄
安裝依賴：pip3 install garminconnect anthropic python-dotenv
執行方式：python3 garmin_fetch.py
"""

import os
import json
import subprocess
from datetime import date, timedelta
from garminconnect import Garmin
from anthropic import Anthropic
from dotenv import load_dotenv

# ── 設定 ──────────────────────────────────────────
EMAIL = "banc9999@hotmail.com"   # 換成你的 Garmin Connect Email
PASSWORD = "0204tksM"          # 換成你的密碼
DAYS_BACK = 30                      # 抓取最近幾天的數據
REPO_DIR = "/Users/tingchen/Desktop/running-dashboard"
# ──────────────────────────────────────────────────

load_dotenv(os.path.join(REPO_DIR, ".env"))


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

    pace_sec_per_km = (duration_sec / distance_km) if distance_km > 0 else 0
    pace_min = int(pace_sec_per_km // 60)
    pace_sec = int(pace_sec_per_km % 60)

    return {
        "activity_id": activity.get("activityId"),
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


def load_existing_analysis():
    """讀取現有的分析紀錄"""
    path = os.path.join(REPO_DIR, "analysis.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"analyses": []}


def already_analyzed(analysis_data, activity_id):
    """檢查這筆活動是否已經分析過"""
    return any(a.get("activity_id") == activity_id for a in analysis_data["analyses"])


def analyze_run_with_ai(run, recent_runs):
    """用 Claude 分析單次跑步紀錄"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ 找不到 ANTHROPIC_API_KEY，跳過 AI 分析")
        return None

    client = Anthropic(api_key=api_key)

    prompt = f"""你是一位專業跑步教練。請分析這次跑步紀錄，並參考最近的歷史數據作為對比基準。

【這次跑步】
日期：{run['date']}
路線：{run['name']}
距離：{run['distance_km']} km
時間：{run['duration_min']} 分鐘
配速：{run['pace']}
平均心率：{run['avg_hr']} bpm
最高心率：{run['max_hr']} bpm
平均步頻：{run['avg_cadence']} spm
平均步幅：{run['avg_stride_length_m']} cm
爬升：{run['elevation_gain_m']} m

【最近 5 次歷史數據（供對比）】
{json.dumps(recent_runs[:5], ensure_ascii=False, indent=2)}

請用繁體中文，以 JSON 格式回覆，包含以下欄位：
{{
  "overall_rating": "一句話總評（例如：今天表現穩定，配速與心率控制良好）",
  "cadence_analysis": "步頻分析，與理想範圍（170-185 spm）對比",
  "efficiency_analysis": "跑步效率分析（配速、心率、步幅之間的關係）",
  "comparison": "與最近紀錄相比的趨勢（進步/退步/持平，具體數字）",
  "suggestions": ["建議1", "建議2", "建議3"]
}}

只回 JSON，不要其他文字。"""

    print("🤖 呼叫 Claude 分析中...")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        result = json.loads(text)
        print("✅ AI 分析完成")
        return result
    except json.JSONDecodeError:
        print("⚠️ AI 回覆格式錯誤，保留原始文字")
        return {"raw_text": text}


def git_push(repo_dir, files, message):
    """將指定檔案 commit 並推上 GitHub"""
    subprocess.run(["git", "add"] + files, cwd=repo_dir)
    result = subprocess.run(["git", "commit", "-m", message], cwd=repo_dir, capture_output=True, text=True)
    if "nothing to commit" in result.stdout:
        print("ℹ️ 沒有新的變動，跳過 push")
        return
    subprocess.run(["git", "push"], cwd=repo_dir)
    print(f"🚀 已推上 GitHub：{message}")


def main():
    client = connect_garmin()
    raw_activities = fetch_running_activities(client, days=DAYS_BACK)

    if not raw_activities:
        print("⚠️ 沒有找到跑步紀錄")
        return

    runs = [parse_activity(a) for a in raw_activities]
    stats = summarize(runs)

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

    # 儲存跑步數據
    data_path = os.path.join(REPO_DIR, "running_data.json")
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump({"summary": stats, "runs": runs}, f, ensure_ascii=False, indent=2)
    print(f"\n💾 數據已儲存到 running_data.json")

    # ── AI 分析最新一筆紀錄 ─────────────────────────
    analysis_data = load_existing_analysis()
    latest_run = runs[0]  # 最新的一筆（已按時間排序）

    if already_analyzed(analysis_data, latest_run["activity_id"]):
        print("ℹ️ 最新紀錄已分析過，跳過")
    else:
        analysis_result = analyze_run_with_ai(latest_run, runs[1:6])
        if analysis_result:
            analysis_data["analyses"].insert(0, {
                "activity_id": latest_run["activity_id"],
                "date": latest_run["date"],
                "run": latest_run,
                "analysis": analysis_result,
            })
            analysis_data["analyses"] = analysis_data["analyses"][:20]

            analysis_path = os.path.join(REPO_DIR, "analysis.json")
            with open(analysis_path, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            print("💾 分析結果已儲存到 analysis.json")

    # ── 推上 GitHub ─────────────────────────────────
    git_push(REPO_DIR, ["running_data.json", "analysis.json"], "自動更新跑步數據與分析")


if __name__ == "__main__":
    main()
