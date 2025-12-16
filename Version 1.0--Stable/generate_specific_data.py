import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
OUTPUT_FILE = Path("data/consumption_sample.csv")
INITIAL_BALANCE = 500.0

# Students
STUDENTS = [
    {"id": "2025001", "name": "安欣", "major": "计算机", "grade": "2025"},
    {"id": "2022001", "name": "白江波", "major": "土木工程", "grade": "2022"},
    {"id": "2023001", "name": "高启强", "major": "自动化", "grade": "2023"}, # Poverty
    {"id": "2024001", "name": "高启盛", "major": "电子信息", "grade": "2024"}, # Large Amount
    {"id": "2025002", "name": "安欣", "major": "心理学", "grade": "2025"}, # High Frequency
]

# Locations & Types
LOCATIONS = {
    "canteen": ["一区食堂", "二区食堂", "三区食堂"],
    "store": ["图书馆便利店"],
    "cafe": ["1897咖啡"],
    "center": ["学生活动中心"]
}

def get_random_time(base_date, start_hour=7, end_hour=22):
    hour = random.randint(start_hour, end_hour)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return base_date.replace(hour=hour, minute=minute, second=second)

def generate_records():
    all_records = []
    base_date = datetime(2025, 12, 10)

    for student in STUDENTS:
        balance = INITIAL_BALANCE
        student_records = []
        
        # Determine student profile
        is_poverty = student["name"] == "高启强"
        is_rich = student["name"] == "高启盛"
        is_freq = student["name"] == "安欣" and student["major"] == "心理学"
        
        # 1. Generate Timestamps first
        timestamps = []
        current_date = base_date
        for i in range(10):
            if i % 3 == 0 and i > 0:
                current_date += timedelta(days=1)
            timestamps.append(get_random_time(current_date))
            
        # Sort timestamps to ensure chronological order
        timestamps.sort()
        
        # Special handling for High Frequency (An Xin - Psych)
        # We need a burst. Let's overwrite the middle timestamps to be close together.
        if is_freq:
            burst_start = timestamps[5]
            for k in range(1, 5): # 5, 6, 7, 8, 9 indices involved? Let's do 4 transactions
                if 5 + k < len(timestamps):
                    timestamps[5+k] = burst_start + timedelta(minutes=k*2)
            timestamps.sort() # Re-sort just in case

        # 2. Generate Transactions based on sorted timestamps
        for i, ts in enumerate(timestamps):
            # Default values
            tx_type = "消费"
            merchant_type = "餐饮美食"
            location = random.choice(LOCATIONS["canteen"])
            amount = round(random.uniform(8, 25), 2)
            
            # Logic based on index or profile
            # Note: i is now the chronological index (0 is earliest)
            
            # Recharge logic: Let's say the 2nd or 3rd transaction is a recharge for some
            if i == 2 and not is_poverty:
                tx_type = "充值"
                merchant_type = "充值"
                location = "学生活动中心"
                amount = 100.0
                balance += amount
            
            # Poverty Profile
            elif is_poverty:
                amount = round(random.uniform(3, 8), 2)
                location = random.choice(LOCATIONS["canteen"])
                merchant_type = "餐饮美食"
                balance -= amount
                
            # Large Amount Profile (Gao Qisheng) - Make it happen late
            elif is_rich and i == 8:
                amount = 800.0
                location = "1897咖啡"
                merchant_type = "休闲娱乐"
                balance -= amount
            
            # High Frequency Profile (An Xin - Psych)
            # We set timestamps 5,6,7,8,9 to be close. Let's make them small store purchases.
            elif is_freq and i >= 5:
                amount = round(random.uniform(5, 15), 2)
                location = "图书馆便利店"
                merchant_type = "购物超市"
                balance -= amount
                
            # Normal Consumption
            else:
                if tx_type == "消费":
                    if random.random() < 0.2:
                        location = random.choice(LOCATIONS["store"] + LOCATIONS["cafe"])
                        merchant_type = "购物超市" if "便利店" in location else "休闲娱乐"
                        amount = round(random.uniform(10, 35), 2)
                    else:
                        location = random.choice(LOCATIONS["canteen"])
                        merchant_type = "餐饮美食"
                        amount = round(random.uniform(8, 20), 2)
                    balance -= amount

            record = {
                "student_id": student["id"],
                "name": student["name"],
                "major": student["major"],
                "grade": student["grade"],
                "balance": round(balance, 2),
                "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
                "amount": amount,
                "merchant_type": merchant_type,
                "location": location,
                "tx_type": tx_type
            }
            student_records.append(record)
            
        all_records.extend(student_records)

    # Sort final list by Name then Timestamp
    all_records.sort(key=lambda x: (x["name"], x["timestamp"]))

    return all_records

def save_to_csv(records):
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    
    headers = [
        "student_id", "name", "major", "grade", "balance", 
        "timestamp", "amount", "merchant_type", "location", "tx_type"
    ]
    
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)
    
    print(f"Successfully generated {len(records)} records to {OUTPUT_FILE}")

if __name__ == "__main__":
    data = generate_records()
    save_to_csv(data)
