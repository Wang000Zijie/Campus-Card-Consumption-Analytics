import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime
from models import ConsumptionRecord
from utils import DATE_FMT

DB_PATH = Path("data/campus.db")

def get_connection():
    """获取数据库连接"""
    if not DB_PATH.parent.exists():
        DB_PATH.parent.mkdir(parents=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS consumption (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            name TEXT NOT NULL,
            major TEXT NOT NULL,
            grade TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL,
            amount REAL NOT NULL,
            merchant_type TEXT NOT NULL,
            location TEXT NOT NULL,
            tx_type TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def record_to_obj(row: sqlite3.Row) -> ConsumptionRecord:
    """将数据库行转换为对象"""
    return ConsumptionRecord(
        id=row['id'],
        student_id=row['student_id'],
        name=row['name'],
        major=row['major'],
        grade=row['grade'],
        balance=row['balance'] if 'balance' in row.keys() else 0.0,
        timestamp=datetime.strptime(row['timestamp'], DATE_FMT),
        amount=row['amount'],
        merchant_type=row['merchant_type'],
        location=row['location'],
        tx_type=row['tx_type']
    )

def fetch_records(
    student_id: str = "",
    name: str = "",
    major: str = "",
    grade: str = "",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    time_asc: bool = False
) -> List[ConsumptionRecord]:
    """查询记录"""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM consumption WHERE 1=1"
    params = []
    
    if student_id:
        query += " AND student_id LIKE ?"
        params.append(f"%{student_id}%")
    if name:
        query += " AND name LIKE ?"
        params.append(f"%{name}%")
    if major:
        query += " AND major LIKE ?"
        params.append(f"%{major}%")
    if grade:
        query += " AND grade LIKE ?"
        params.append(f"%{grade}%")
    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date.strftime(DATE_FMT))
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date.strftime(DATE_FMT))
        
    # 排序逻辑：
    # 1. 姓名 (拼音顺序，方便找人)
    # 2. 时间 (根据参数决定正序还是倒序)
    sort_order = "ASC" if time_asc else "DESC"
    query += f" ORDER BY name ASC, timestamp {sort_order}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    return [record_to_obj(row) for row in rows]

def add_record(record: ConsumptionRecord) -> int:
    """添加记录"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 检查是否需要添加 balance 列 (简单的迁移逻辑)
    try:
        cursor.execute("SELECT balance FROM consumption LIMIT 1")
    except sqlite3.OperationalError:
        # 列不存在，添加它
        cursor.execute("ALTER TABLE consumption ADD COLUMN balance REAL DEFAULT 0.0")
        conn.commit()

    cursor.execute("""
        INSERT INTO consumption (student_id, name, major, grade, balance, timestamp, amount, merchant_type, location, tx_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.student_id,
        record.name,
        record.major,
        record.grade,
        record.balance,
        record.timestamp.strftime(DATE_FMT),
        record.amount,
        record.merchant_type,
        record.location,
        record.tx_type
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # 重新计算该学生的余额
    recalculate_balance(record.student_id)
    
    return new_id

def recalculate_balance(student_id: str):
    """重新计算指定学生的所有余额"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 获取该学生所有记录，按时间正序排列
    cursor.execute("""
        SELECT id, amount, tx_type FROM consumption 
        WHERE student_id = ? 
        ORDER BY timestamp ASC, id ASC
    """, (student_id,))
    
    rows = cursor.fetchall()
    
    current_balance = 500.0 # 默认初始余额
    
    # 2. 遍历计算
    for row in rows:
        rid = row['id']
        amt = row['amount']
        ttype = row['tx_type']
        
        if ttype in ["充值", "退款"]:
            current_balance += amt
        else:
            current_balance -= amt
            
        # 3. 更新当前记录的 balance
        cursor.execute("UPDATE consumption SET balance = ? WHERE id = ?", (round(current_balance, 2), rid))
        
    conn.commit()
    conn.close()

def update_record(record: ConsumptionRecord):
    """更新记录"""
    if record.id is None:
        raise ValueError("Record ID cannot be None for update")
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE consumption 
        SET student_id=?, name=?, major=?, grade=?, balance=?, timestamp=?, amount=?, merchant_type=?, location=?, tx_type=?
        WHERE id=?
    """, (
        record.student_id,
        record.name,
        record.major,
        record.grade,
        record.balance,
        record.timestamp.strftime(DATE_FMT),
        record.amount,
        record.merchant_type,
        record.location,
        record.tx_type,
        record.id
    ))
    conn.commit()
    conn.close()
    
    # 重新计算余额
    recalculate_balance(record.student_id)

def delete_record(record_id: int):
    """删除记录"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 先获取 student_id 以便重算
    cursor.execute("SELECT student_id FROM consumption WHERE id=?", (record_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
        
    student_id = row['student_id']
    
    cursor.execute("DELETE FROM consumption WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    
    # 重新计算余额
    recalculate_balance(student_id)

def import_from_csv(csv_path: Path) -> Tuple[int, List[str]]:
    """从CSV导入数据"""
    import csv
    
    conn = get_connection()
    cursor = conn.cursor()
    
    count = 0
    errors = []
    
    try:
        # 使用 utf-8-sig 以处理可能的 BOM
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            # 移除表头可能的空白字符
            if reader.fieldnames:
                reader.fieldnames = [name.strip() for name in reader.fieldnames]
            
            for row in reader:
                try:
                    # 处理 balance 字段，如果 CSV 中没有则默认为 0.0
                    balance_val = float(row.get('balance', 0.0))
                    
                    cursor.execute("""
                        INSERT INTO consumption (student_id, name, major, grade, balance, timestamp, amount, merchant_type, location, tx_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['student_id'],
                        row['name'],
                        row['major'],
                        row['grade'],
                        balance_val,
                        row['timestamp'],
                        float(row['amount']),
                        row['merchant_type'],
                        row['location'],
                        row['tx_type']
                    ))
                    count += 1
                except Exception as e:
                    errors.append(f"Line error: {e}")
        
        conn.commit()
    except Exception as e:
        errors.append(f"File error: {e}")
    finally:
        conn.close()
        
    return count, errors
