import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import ConsumptionRecord
from utils import in_range

class DataAnalyzer:
    def __init__(self, records: List[ConsumptionRecord]):
        # 将记录转换为 DataFrame，方便后续分析
        if not records:
            self.df = pd.DataFrame(columns=[
                "student_id", "name", "major", "grade", "balance", 
                "timestamp", "amount", "merchant_type", "location", "tx_type"
            ])
        else:
            data = [
                {
                    "student_id": r.student_id,
                    "name": r.name,
                    "major": r.major,
                    "grade": r.grade,
                    "balance": r.balance,
                    "timestamp": r.timestamp,
                    "amount": r.amount,
                    "merchant_type": r.merchant_type,
                    "location": r.location,
                    "tx_type": r.tx_type,
                    "_obj": r  # 保留原始对象引用，方便返回
                }
                for r in records
            ]
            self.df = pd.DataFrame(data)

    def generate_report(
        self,
        single_threshold: float,
        freq_window_min: int,
        freq_count: int,
    ) -> Dict[str, Any]:
        
        df = self.df

        if df.empty:
            return {
                "summary": {"daily": {}, "weekly": {}, "monthly": {}},
                "habits": {
                    "count": 0, "total": 0.0, "avg": 0.0, "max": 0.0,
                    "merchant_breakdown": {}
                },
                "anomalies": {"large_count": 0, "freq_count": 0}
            }

        # 1. 消费汇总 (Resample)
        df_ts = df.set_index('timestamp')
        daily = df_ts.resample('D')['amount'].sum().fillna(0)
        weekly = df_ts.resample('W')['amount'].sum().fillna(0)
        monthly = df_ts.resample('ME')['amount'].sum().fillna(0) # pandas 2.0+ use 'ME' for Month End

        # 转换 key 为字符串格式
        daily_dict = {k.strftime('%Y-%m-%d'): v for k, v in daily.items() if v > 0}
        weekly_dict = {f"{k.year}-W{k.week:02d}": v for k, v in weekly.items() if v > 0}
        monthly_dict = {k.strftime('%Y-%m'): v for k, v in monthly.items() if v > 0}

        # 2. 习惯分析
        total = df['amount'].sum()
        count = len(df)
        avg = df['amount'].mean()
        max_amt = df['amount'].max()
        
        # 商户分布
        merchant_stats = df.groupby('merchant_type')['amount'].agg(['sum', 'count'])
        merchant_breakdown = {
            k: {"total": v['sum'], "count": v['count']} 
            for k, v in merchant_stats.iterrows()
        }

        # 3. 异常检测
        # 大额
        large_count = len(df[df['amount'] > single_threshold])
        
        # 高频 (Rolling window)
        # 对每个学生分别计算
        freq_count_total = 0
        if not df.empty:
            # 按学生分组，然后对时间排序
            grouped = df.sort_values('timestamp').groupby('student_id')
            
            for _, group in grouped:
                # 使用 rolling window 计算 freq_window_min 内的交易次数
                # 这里的逻辑稍微复杂，pandas rolling 是基于 index 的
                # 我们可以简单地用 timestamp 的 diff 来做，或者用 rolling('10min')
                
                # 设置时间索引
                g_ts = group.set_index('timestamp')
                # 统计过去 freq_window_min 分钟内的交易次数
                counts = g_ts.rolling(f'{freq_window_min}min')['amount'].count()
                # 如果次数 >= freq_count，则标记为异常
                # 注意：rolling 包含当前行，所以 >= freq_count 即可
                freq_count_total += len(counts[counts >= freq_count])

        return {
            "summary": {
                "daily": daily_dict,
                "weekly": weekly_dict,
                "monthly": monthly_dict
            },
            "habits": {
                "count": count,
                "total": total,
                "avg": avg,
                "max": max_amt,
                "merchant_breakdown": merchant_breakdown
            },
            "anomalies": {
                "large_count": large_count,
                "freq_count": freq_count_total
            }
        }

    def detect_poverty_students(self, threshold: float = 140.0) -> List[Dict[str, Any]]:
        """
        贫困生筛查：周平均消费低于阈值的学生
        注意：只统计 '消费' 类型的记录
        """
        if self.df.empty:
            return []
            
        # 1. 筛选消费记录
        df_cons = self.df[self.df['tx_type'] == '消费'].copy()
        
        if df_cons.empty:
            return []

        # 2. 按学生和周分组统计
        df_cons['week'] = df_cons['timestamp'].dt.to_period('W')
        
        # 计算每个学生每周的总消费
        weekly_spend = df_cons.groupby(['student_id', 'name', 'major', 'grade', 'week'])['amount'].sum().reset_index()
        
        # 计算每个学生的周平均消费
        # 注意：这里只计算了有消费记录的周。如果某周完全没消费，可能不会被统计进来，
        # 但对于贫困生筛查来说，只要存在的周平均低即可。
        avg_weekly = weekly_spend.groupby(['student_id', 'name', 'major', 'grade'])['amount'].mean().reset_index()
        avg_weekly.rename(columns={'amount': 'weekly_avg'}, inplace=True)
        
        # 计算总消费和总周数，方便展示
        total_stats = df_cons.groupby(['student_id'])['amount'].agg(['sum', 'count']).reset_index()
        total_stats.rename(columns={'sum': 'total_amount', 'count': 'tx_count'}, inplace=True)
        
        # 统计周数
        weeks_count = df_cons.groupby(['student_id'])['week'].nunique().reset_index(name='weeks_count')
        
        # 获取每个学生的当前余额 (取最后一条记录的余额)
        # 注意：要从 self.df (全量数据) 中取，因为最后一条记录可能是充值
        latest_balance = self.df.sort_values('timestamp', ascending=False).drop_duplicates('student_id')[['student_id', 'balance']]
        latest_balance.rename(columns={'balance': 'current_balance'}, inplace=True)

        # 合并数据
        result = pd.merge(avg_weekly, total_stats, on='student_id')
        result = pd.merge(result, weeks_count, on='student_id')
        result = pd.merge(result, latest_balance, on='student_id', how='left')
        
        # 筛选低于阈值的学生
        poverty_students = result[result['weekly_avg'] < threshold]
        
        # 填充 NaN 余额为 0 (理论上不应该发生，除非数据不一致)
        poverty_students['current_balance'] = poverty_students['current_balance'].fillna(0)
        
        return poverty_students.to_dict('records')

    def get_suspicious_records(self, single_threshold: float, freq_window_min: int, freq_count: int) -> List[Dict[str, Any]]:
        """
        获取异常交易记录：大额消费 或 高频消费
        """
        if self.df.empty:
            return []
            
        suspicious = []
        
        # 1. 大额消费
        # 只统计 '消费' 类型
        large_df = self.df[(self.df['amount'] > single_threshold) & (self.df['tx_type'] == '消费')].copy()
        for _, row in large_df.iterrows():
            suspicious.append({
                "type": "大额消费",
                "student_id": row['student_id'],
                "name": row['name'],
                "major": row['major'],
                "timestamp": row['timestamp'],
                "amount": row['amount'],
                "tx_type": row['tx_type'],
                "location": row['location'],
                "desc": f"单笔 > {single_threshold}"
            })
            
        # 2. 高频消费
        if not self.df.empty:
            # 确保按时间排序，且只看消费记录
            df_sorted = self.df[self.df['tx_type'] == '消费'].sort_values('timestamp')
            grouped = df_sorted.groupby('student_id')
            
            for _, group in grouped:
                if group.empty: continue
                
                # 设置时间索引
                g_ts = group.set_index('timestamp')
                
                # 统计窗口内的交易次数
                # min_periods=1 确保有数据就计算
                counts = g_ts.rolling(f'{freq_window_min}min')['amount'].count()
                
                # 找到异常的时间点
                anomalies = counts[counts >= freq_count]
                
                for ts, count in anomalies.items():
                    # 找到触发阈值的这条记录
                    matches = group[group['timestamp'] == ts]
                    if not matches.empty:
                        record = matches.iloc[0]
                        
                        suspicious.append({
                            "type": "高频消费",
                            "student_id": record['student_id'],
                            "name": record['name'],
                            "major": record['major'],
                            "timestamp": record['timestamp'],
                            "amount": record['amount'],
                            "tx_type": record['tx_type'],
                            "location": record['location'],
                            "desc": f"{freq_window_min}分内 {int(count)} 次"
                        })
        
        # 按时间倒序
        suspicious.sort(key=lambda x: x['timestamp'], reverse=True)
        return suspicious

    def get_deep_insights(self) -> Dict[str, Any]:
        """
        深度数据挖掘：时间段偏好、工作日/周末差异、三餐规律等
        """
        defaults = {
            'peak_hours': [],
            'peak_hour': 0,
            'weekend_avg': 0.0,
            'weekday_avg': 0.0,
            'top_locations': {},
            'meal_stats': {'breakfast': 0, 'lunch': 0, 'dinner': 0, 'other': 0},
            'avg_meal_cost': 0.0,
            'most_expensive_meal': 0.0,
            'student_count': 0
        }
        
        if self.df.empty:
            return defaults
            
        insights = defaults.copy()
        # 过滤出消费记录进行分析 (排除充值)
        df = self.df[self.df['tx_type'] == '消费'].copy()
        
        if df.empty:
            return defaults

        try:
            insights['student_count'] = df['student_id'].nunique()

            # 1. 消费高峰时段分析
            if 'timestamp' in df.columns:
                df['hour'] = df['timestamp'].dt.hour
                hour_counts = df['hour'].value_counts().sort_index()
                # 找到 Top 3 活跃小时
                top_hours = hour_counts.nlargest(3).index.tolist()
                insights['peak_hours'] = top_hours
                insights['peak_hour'] = top_hours[0] if top_hours else 0
                
                # 三餐规律分析
                def get_meal_type(h):
                    if 6 <= h <= 9: return 'breakfast'
                    elif 11 <= h <= 13: return 'lunch'
                    elif 17 <= h <= 19: return 'dinner'
                    else: return 'other'
                
                df['meal_type'] = df['hour'].apply(get_meal_type)
                meal_counts = df['meal_type'].value_counts()
                insights['meal_stats'] = {
                    'breakfast': int(meal_counts.get('breakfast', 0)),
                    'lunch': int(meal_counts.get('lunch', 0)),
                    'dinner': int(meal_counts.get('dinner', 0)),
                    'other': int(meal_counts.get('other', 0))
                }
            
            # 2. 工作日 vs 周末 消费对比
            if 'timestamp' in df.columns and 'amount' in df.columns:
                df['is_weekend'] = df['timestamp'].dt.dayofweek >= 5
                weekend_avg = df[df['is_weekend']]['amount'].mean()
                weekday_avg = df[~df['is_weekend']]['amount'].mean()
                insights['weekend_avg'] = float(weekend_avg) if not pd.isna(weekend_avg) else 0.0
                insights['weekday_avg'] = float(weekday_avg) if not pd.isna(weekday_avg) else 0.0
                
                insights['avg_meal_cost'] = float(df['amount'].mean())
                insights['most_expensive_meal'] = float(df['amount'].max())
            
            # 3. 最受欢迎的地点 (Top 5)
            if 'location' in df.columns:
                top_locations = df['location'].value_counts().nlargest(5)
                insights['top_locations'] = top_locations.to_dict()
                
        except Exception as e:
            print(f"Analysis error: {e}")
            # Return whatever we have so far (initialized with defaults)
            
        return insights
