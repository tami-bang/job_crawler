# crawler/utils.py
import pandas as pd
import os

def save_jobs(jobs, filename="data/jobs.csv"):
    """크롤링 데이터 CSV 저장"""
    if not os.path.exists("data"):
        os.makedirs("data")
    df = pd.DataFrame(jobs)
    df.to_csv(filename, index=False, encoding="utf-8-sig")
    print(f"[INFO] {len(jobs)}개의 공고 저장 완료: {filename}")
