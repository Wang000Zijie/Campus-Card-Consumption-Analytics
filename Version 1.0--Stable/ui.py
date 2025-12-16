import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import List, Callable, Optional
from datetime import datetime

# 尝试加载 matplotlib
try:
    import matplotlib
    # 尝试设置 backend，如果失败则捕获异常但不中断程序
    try:
        matplotlib.use("TkAgg")
    except Exception:
        pass
        
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    
    # 配置字体以支持中文显示
    # 优先尝试 Windows 常见中文字体
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']
    plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示为方块的问题
    
    HAS_MPL = True
except ImportError as e:
    print(f"Warning: Matplotlib import failed (ImportError): {e}")
    HAS_MPL = False
except Exception as e:
    print(f"Warning: Matplotlib import failed (Exception): {e}")
    import traceback
    traceback.print_exc()
    HAS_MPL = False

from models import ConsumptionRecord
import database
from analyzer import DataAnalyzer
from utils import DATE_FMT, parse_datetime


class ControlPanel(ttk.LabelFrame):
    """顶部控制面板：包含过滤条件和操作按钮"""
    def __init__(self, parent, on_load, on_filter, on_analyze, on_export_report, on_export_clean, on_poverty_check, on_suspicious_check, on_add, on_edit, on_delete):
        super().__init__(parent, text="过滤与阈值")
        self.on_load = on_load
        self.on_filter = on_filter
        self.on_analyze = on_analyze
        self.on_export_report = on_export_report
        self.on_export_clean = on_export_clean
        self.on_poverty_check = on_poverty_check
        self.on_suspicious_check = on_suspicious_check
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete

        # 变量绑定
        self.single_threshold = tk.DoubleVar(value=200.0)
        self.freq_window = tk.IntVar(value=10)
        self.freq_count = tk.IntVar(value=3)
        self.sort_var = tk.StringVar(value="时间倒序")
        
        self._init_widgets()

    def _init_widgets(self):
        # 恢复紧凑的横向布局
        
        # 第一行：筛选条件
        row1 = ttk.Frame(self)
        row1.pack(fill="x", padx=5, pady=2)
        
        ttk.Label(row1, text="学号:").pack(side="left", padx=2)
        self.ent_sid = ttk.Entry(row1, width=10)
        self.ent_sid.pack(side="left", padx=2)

        ttk.Label(row1, text="姓名:").pack(side="left", padx=2)
        self.ent_name = ttk.Entry(row1, width=8)
        self.ent_name.pack(side="left", padx=2)

        ttk.Label(row1, text="专业:").pack(side="left", padx=2)
        self.ent_major = ttk.Entry(row1, width=10)
        self.ent_major.pack(side="left", padx=2)

        ttk.Label(row1, text="年级:").pack(side="left", padx=2)
        self.ent_grade = ttk.Entry(row1, width=6)
        self.ent_grade.pack(side="left", padx=2)
        
        ttk.Label(row1, text="时间:").pack(side="left", padx=2)
        self.ent_start = ttk.Entry(row1, width=10)
        self.ent_start.pack(side="left", padx=1)
        ttk.Label(row1, text="-").pack(side="left")
        self.ent_end = ttk.Entry(row1, width=10)
        self.ent_end.pack(side="left", padx=1)
        
        ttk.Label(row1, text="排序:").pack(side="left", padx=5)
        ttk.Combobox(row1, textvariable=self.sort_var, values=["时间倒序", "时间正序"], width=8, state="readonly").pack(side="left", padx=2)

        ttk.Button(row1, text="查询", command=self.on_filter).pack(side="left", padx=10)

        # 第二行：分析参数 + 功能按钮
        row2 = ttk.Frame(self)
        row2.pack(fill="x", padx=5, pady=5)
        
        # 左侧：分析参数
        param_frame = ttk.LabelFrame(row2, text="分析参数")
        param_frame.pack(side="left", padx=5)
        
        ttk.Label(param_frame, text="大额阈值:").pack(side="left", padx=2)
        ttk.Entry(param_frame, textvariable=self.single_threshold, width=5).pack(side="left", padx=2)
        
        ttk.Label(param_frame, text="高频(分):").pack(side="left", padx=2)
        ttk.Entry(param_frame, textvariable=self.freq_window, width=4).pack(side="left", padx=2)
        
        ttk.Label(param_frame, text="次数:").pack(side="left", padx=2)
        ttk.Entry(param_frame, textvariable=self.freq_count, width=4).pack(side="left", padx=2)
        
        ttk.Button(param_frame, text="开始分析", command=self.on_analyze).pack(side="left", padx=5)
        ttk.Button(param_frame, text="贫困筛查", command=self.on_poverty_check).pack(side="left", padx=2)
        ttk.Button(param_frame, text="异常检测", command=self.on_suspicious_check).pack(side="left", padx=2)

        # 右侧：操作按钮
        op_frame = ttk.Frame(row2)
        op_frame.pack(side="right", padx=5)
        
        ttk.Button(op_frame, text="新增", command=self.on_add, width=6).pack(side="left", padx=2)
        ttk.Button(op_frame, text="修改", command=self.on_edit, width=6).pack(side="left", padx=2)
        ttk.Button(op_frame, text="删除", command=self.on_delete, width=6).pack(side="left", padx=2)
        ttk.Separator(op_frame, orient="vertical").pack(side="left", fill="y", padx=5)
        ttk.Button(op_frame, text="导出报告", command=self.on_export_report).pack(side="left", padx=2)
        ttk.Button(op_frame, text="导入CSV", command=self.on_load).pack(side="left", padx=2)
        ttk.Button(op_frame, text="导出CSV", command=self.on_export_clean).pack(side="left", padx=2)


    def get_filter_params(self):
        """获取当前的过滤参数"""
        start_str = self.ent_start.get().strip()
        end_str = self.ent_end.get().strip()
        
        return {
            "sid": self.ent_sid.get().strip(),
            "name": self.ent_name.get().strip(),
            "major": self.ent_major.get().strip(),
            "grade": self.ent_grade.get().strip(),
            "start": parse_datetime(start_str + " 00:00:00") if start_str else None,
            "end": parse_datetime(end_str + " 23:59:59") if end_str else None,
            "time_asc": self.sort_var.get() == "时间正序"
        }

    def get_analysis_params(self):
        """获取分析参数"""
        return {
            "single_threshold": self.single_threshold.get(),
            "freq_window": self.freq_window.get(),
            "freq_count": self.freq_count.get()
        }


class DataTableView(ttk.Frame):
    """数据表格视图"""
    def __init__(self, parent):
        super().__init__(parent)
        self._init_table()

    def _init_table(self):
        cols = [
            "student_id", "name", "major", "grade", "balance",
            "timestamp", "amount", "merchant_type", "location", "tx_type"
        ]
        # 定义列名映射
        col_names = {
            "student_id": "学号", "name": "姓名", "major": "专业", "grade": "年级",
            "balance": "余额(元)", "timestamp": "时间", "amount": "金额(元)",
            "merchant_type": "商户类型", "location": "地点", "tx_type": "交易类型"
        }
        
        # 定义列宽配置 (列名: 宽度)
        col_widths = {
            "student_id": 100, "name": 80, "major": 100, "grade": 60,
            "balance": 80, "timestamp": 140, "amount": 80,
            "merchant_type": 100, "location": 120, "tx_type": 80
        }
        
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=10)
        
        for c in cols:
            self.tree.heading(c, text=col_names.get(c, c))
            self.tree.column(c, width=col_widths.get(c, 90), anchor="center")
            
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def update_data(self, rows: List[ConsumptionRecord]):
        # 清空旧数据
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # 插入新数据
        for r in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    r.student_id,
                    r.name,
                    r.major,
                    r.grade,
                    f"{r.balance:.2f}",
                    r.timestamp.strftime(DATE_FMT),
                    f"{r.amount:.2f}",
                    r.merchant_type,
                    r.location,
                    r.tx_type,
                ),
            )


class ResultPanel(ttk.LabelFrame):
    """结果摘要面板"""
    def __init__(self, parent):
        super().__init__(parent, text="结果摘要")
        # 使用等宽字体 (Consolas 或 Courier New) 以确保对齐
        self.txt = tk.Text(self, height=8, font=("Consolas", 10))
        self.txt.pack(fill="both", expand=True, padx=5, pady=5)

    def show_text(self, text: str):
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, text)


class ChartPanel(ttk.LabelFrame):
    """图表可视化面板"""
    def __init__(self, parent):
        super().__init__(parent, text="可视化")
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.canvas = None
        self._init_chart()

    def _init_chart(self):
        if not HAS_MPL:
            ttk.Label(self, text="未安装 matplotlib，无法绘图").pack(padx=20, pady=20)
            return

        # 改为 1 行 2 列的布局
        self.fig, (self.ax1, self.ax2) = plt.subplots(1, 2, figsize=(10, 3.5))
        # 调整布局以适应小窗口
        self.fig.tight_layout()
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    def update_charts(self, daily_data: dict, merchant_data: dict):
        if not HAS_MPL:
            return
        
        try:
            # 图表1: 日消费趋势
            self.ax1.clear()
            if not daily_data:
                self.ax1.set_title("无数据")
            else:
                # 将日期字符串转换为 datetime 对象，消除 matplotlib 的警告
                xs = [datetime.strptime(k, '%Y-%m-%d') for k in daily_data.keys()]
                ys = list(daily_data.values())
                
                # 使用 plot_date 或者直接 plot datetime 对象
                self.ax1.plot(xs, ys, marker="o", linestyle='-', markersize=4)
                self.ax1.set_title("日消费趋势")
                self.ax1.set_xlabel("日期")
                self.ax1.set_ylabel("金额")
                
                # 优化 X 轴标签显示
                import matplotlib.dates as mdates
                self.ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
                self.ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
                self.ax1.tick_params(axis="x", rotation=30)
                self.ax1.grid(True, linestyle='--', alpha=0.7)
                
            # 图表2: 商户分布饼图
            self.ax2.clear()
            if not merchant_data:
                self.ax2.set_title("无数据")
            else:
                labels = list(merchant_data.keys())
                sizes = [v['total'] for v in merchant_data.values()]
                # 简单的饼图
                self.ax2.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 9})
                self.ax2.set_title("商户消费占比")

            self.fig.tight_layout()
            self.canvas.draw()
        except Exception as e:
            print(f"Chart update error: {e}")
            import traceback
            traceback.print_exc()


class App:
    """主应用程序控制器"""
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("校园卡消费分析系统")
        self.root.geometry("1200x800")
        
        # 初始化数据库
        database.init_db()
        
        # 数据状态
        self.filtered: List[ConsumptionRecord] = []
        
        self._setup_ui()
        self.apply_filter() # 初始加载

    def _setup_ui(self):
        # 1. 顶部控制面板
        self.control_panel = ControlPanel(
            self.root,
            on_load=self.load_file,
            on_filter=self.apply_filter,
            on_analyze=self.analyze,
            on_export_report=self.export_report,
            on_export_clean=self.export_clean,
            on_poverty_check=self.check_poverty,
            on_suspicious_check=self.check_suspicious,
            on_add=self.add_record,
            on_edit=self.edit_record,
            on_delete=self.delete_record
        )
        self.control_panel.pack(fill="x", padx=10, pady=5)

        # 2. 中间数据表格
        self.table_view = DataTableView(self.root)
        self.table_view.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 右键菜单绑定
        self.table_view.tree.bind("<Button-3>", self.show_context_menu)

        # 3. 底部区域（左右分栏：左边结果，右边图表）
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="both", expand=False, padx=10, pady=5)

        self.result_panel = ResultPanel(bottom_frame)
        self.result_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))

        self.chart_panel = ChartPanel(bottom_frame)
        self.chart_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))

    def show_context_menu(self, event):
        item = self.table_view.tree.identify_row(event.y)
        if not item:
            return
            
        self.table_view.tree.selection_set(item)
        idx = self.table_view.tree.index(item)
        if idx >= len(self.filtered):
            return
            
        record = self.filtered[idx]
        
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=f"分析该学生 ({record.name})", command=lambda: self.analyze_subset("student_id", record.student_id, f"学生分析: {record.name}"))
        menu.add_command(label=f"分析该专业 ({record.major})", command=lambda: self.analyze_subset("major", record.major, f"专业分析: {record.major}"))
        menu.add_command(label=f"分析该年级 ({record.grade})", command=lambda: self.analyze_subset("grade", record.grade, f"年级分析: {record.grade}"))
        
        menu.post(event.x_root, event.y_root)

    def analyze_subset(self, field, value, title):
        # 从数据库获取完整数据进行分析
        kwargs = {field: value}
        records = database.fetch_records(**kwargs)
        
        if not records:
            messagebox.showinfo("提示", "无相关数据")
            return
            
        params = self.control_panel.get_analysis_params()
        AnalysisWindow(self.root, title, records, params)

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        
        count, errs = database.import_from_csv(Path(path))
        msg = f"成功导入 {count} 条记录"
        if errs:
            msg += f"\n\n出现 {len(errs)} 个错误:\n" + "\n".join(errs[:5])
            if len(errs) > 5:
                msg += "\n..."
        messagebox.showinfo("导入结果", msg)
        self.apply_filter()

    def apply_filter(self):
        params = self.control_panel.get_filter_params()
        
        self.filtered = database.fetch_records(
            student_id=params["sid"],
            name=params["name"],
            major=params["major"],
            grade=params["grade"],
            start_date=params["start"],
            end_date=params["end"],
            time_asc=params.get("time_asc", False)
        )
        
        self.table_view.update_data(self.filtered)
        self.result_panel.show_text(f"查询结果：{len(self.filtered)} 条记录")

    def add_record(self):
        RecordDialog(self.root, "新增记录", on_save=self._on_record_saved)

    def edit_record(self):
        selected = self.table_view.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择一条记录")
            return
        
        # 获取选中记录的索引
        idx = self.table_view.tree.index(selected[0])
        if idx < len(self.filtered):
            record = self.filtered[idx]
            RecordDialog(self.root, "修改记录", record=record, on_save=self._on_record_saved)

    def delete_record(self):
        selected = self.table_view.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选择至少一条记录")
            return
            
        if not messagebox.askyesno("确认", f"确定要删除选中的 {len(selected)} 条记录吗？"):
            return
            
        deleted_count = 0
        for item_id in selected:
            idx = self.table_view.tree.index(item_id)
            if idx < len(self.filtered):
                record = self.filtered[idx]
                if record.id:
                    database.delete_record(record.id)
                    deleted_count += 1
        
        if deleted_count > 0:
            messagebox.showinfo("成功", f"已删除 {deleted_count} 条记录")
            self.apply_filter()

    def _on_record_saved(self, record):
        if record.id:
            database.update_record(record)
        else:
            database.add_record(record)
        self.apply_filter()

    def check_poverty(self):
        if not self.filtered:
            messagebox.showinfo("提示", "当前无数据")
            return
            
        analyzer = DataAnalyzer(self.filtered)
        # 默认阈值140
        poverty_students = analyzer.detect_poverty_students(threshold=140)
        
        if not poverty_students:
            messagebox.showinfo("结果", "未发现周均消费低于140元的学生")
            return
            
        # 弹窗显示结果
        top = tk.Toplevel(self.root)
        top.title("贫困生疑似名单 (周均消费 < 140元)")
        top.geometry("800x400")
        
        # 使用 Treeview 替代 Text，显示更清晰
        columns = ("sid", "name", "major", "avg", "total", "balance", "weeks")
        headers = ("学号", "姓名", "专业", "周均消费", "总消费", "当前余额", "统计周数")
        
        tree = ttk.Treeview(top, columns=columns, show="headings")
        
        # 设置表头和列宽
        col_widths = [100, 80, 100, 80, 80, 80, 60]
        for col, hdr, width in zip(columns, headers, col_widths):
            tree.heading(col, text=hdr)
            tree.column(col, width=width, anchor="center")
            
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 插入数据
        for s in poverty_students:
            tree.insert("", "end", values=(
                s['student_id'],
                s['name'],
                s['major'],
                f"{s['weekly_avg']:.2f}",
                f"{s['total_amount']:.2f}",
                f"{s.get('current_balance', 0):.2f}",
                s['weeks_count']
            ))

    def check_suspicious(self):
        if not self.filtered:
            messagebox.showinfo("提示", "当前无数据")
            return
            
        params = self.control_panel.get_analysis_params()
        analyzer = DataAnalyzer(self.filtered)
        
        suspicious = analyzer.get_suspicious_records(
            params["single_threshold"],
            params["freq_window"],
            params["freq_count"]
        )
        
        if not suspicious:
            messagebox.showinfo("结果", "未发现异常交易")
            return
            
        # 弹窗显示结果
        top = tk.Toplevel(self.root)
        top.title(f"异常交易检测 (大额 > {params['single_threshold']} 或 高频)")
        top.geometry("1000x500")
        
        columns = ("type", "sid", "name", "major", "time", "amount", "tx_type", "location", "desc")
        headers = ("异常类型", "学号", "姓名", "专业", "时间", "金额", "交易类型", "地点", "说明")
        
        tree = ttk.Treeview(top, columns=columns, show="headings")
        
        col_widths = [80, 100, 80, 100, 140, 80, 80, 120, 150]
        for col, hdr, width in zip(columns, headers, col_widths):
            tree.heading(col, text=hdr)
            tree.column(col, width=width, anchor="center")
            
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(top, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        for s in suspicious:
            tree.insert("", "end", values=(
                s['type'],
                s['student_id'],
                s['name'],
                s['major'],
                s['timestamp'].strftime(DATE_FMT),
                f"{s['amount']:.2f}",
                s['tx_type'],
                s['location'],
                s['desc']
            ))

    def analyze(self):
        if not self.filtered:
            messagebox.showinfo("提示", "请先筛选数据")
            return
            
        params = self.control_panel.get_analysis_params()
        analyzer = DataAnalyzer(self.filtered)
        
        report = analyzer.generate_report(
            params["single_threshold"],
            params["freq_window"],
            params["freq_count"]
        )
        
        # 获取深度分析
        deep_insights = analyzer.get_deep_insights()
        
        # 生成文本报告
        text_report = format_report_text(report, deep_insights, params)
        self.result_panel.show_text(text_report)
        
        # 更新图表
        self.chart_panel.update_charts(report["summary"]["daily"], report["habits"]["merchant_breakdown"])

    def export_report(self):
        if not self.filtered:
            messagebox.showinfo("提示", "请先筛选数据并统计")
            return
            
        params = self.control_panel.get_analysis_params()
        analyzer = DataAnalyzer(self.filtered)
        report = analyzer.generate_report(
            params["single_threshold"],
            params["freq_window"],
            params["freq_count"]
        )
        deep_insights = analyzer.get_deep_insights()
        
        save_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if not save_path:
            return
            
        text_report = format_report_text(report, deep_insights, params)
        
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(text_report)
        messagebox.showinfo("成功", f"报告已导出到 {save_path}")

    def export_clean(self):
        if not self.filtered:
            messagebox.showinfo("提示", "无数据")
            return
            
        # 检查是否有选中记录
        selected = self.table_view.tree.selection()
        records_to_export = []
        
        if selected:
            if messagebox.askyesno("导出选项", f"检测到选中了 {len(selected)} 条记录。\n是否仅导出选中的记录？\n(选择'否'将导出当前列表所有 {len(self.filtered)} 条记录)"):
                # 导出选中
                for item_id in selected:
                    idx = self.table_view.tree.index(item_id)
                    if idx < len(self.filtered):
                        records_to_export.append(self.filtered[idx])
            else:
                # 导出所有
                records_to_export = self.filtered
        else:
            # 默认导出所有
            records_to_export = self.filtered

        save_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not save_path:
            return
            
        try:
            import csv
            with open(save_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                # 写入表头
                headers = ["student_id", "name", "major", "grade", "balance", "timestamp", "amount", "merchant_type", "location", "tx_type"]
                writer.writerow(headers)
                
                # 写入数据
                for r in records_to_export:
                    writer.writerow([
                        r.student_id,
                        r.name,
                        r.major,
                        r.grade,
                        f"{r.balance:.2f}",
                        r.timestamp.strftime(DATE_FMT),
                        f"{r.amount:.2f}",
                        r.merchant_type,
                        r.location,
                        r.tx_type
                    ])
            messagebox.showinfo("成功", f"已导出 {len(records_to_export)} 条记录到 {save_path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"错误信息: {e}")




def format_report_text(report, deep_insights, params):
    lines = []
    lines.append("=== 基础统计 ===")
    lines.append(f"统计天数：{len(report['summary']['daily'])} 天")
    lines.append(f"统计周数：{len(report['summary']['weekly'])} 周")
    lines.append(f"涉及学生：{deep_insights.get('student_count', 0)} 人")
    
    lines.append("\n=== 消费习惯深度分析 ===")
    h = report["habits"]
    lines.append(f"总消费额: {h['total']:.2f} 元")
    lines.append(f"交易笔数: {h['count']} 笔")
    lines.append(f"笔均消费: {h['avg']:.2f} 元")
    lines.append(f"单笔最高: {h['max']:.2f} 元")
    
    peak = deep_insights.get('peak_hour', 0)
    lines.append(f"\n高峰时段: {peak}:00 - {peak+1}:00")
    
    weekend_avg = deep_insights.get('weekend_avg', 0.0)
    weekday_avg = deep_insights.get('weekday_avg', 0.0)
    
    lines.append(f"周末日均: {weekend_avg:.2f} 元")
    lines.append(f"工作日日均: {weekday_avg:.2f} 元")
    
    if weekend_avg > weekday_avg:
        lines.append("  -> 周末消费更高")
    else:
        lines.append("  -> 工作日消费更高")

    # Meal Stats
    ms = deep_insights.get('meal_stats', {})
    lines.append("\n=== 三餐规律 ===")
    lines.append(f"早餐 (06-09): {ms.get('breakfast', 0)} 次")
    lines.append(f"午餐 (11-13): {ms.get('lunch', 0)} 次")
    lines.append(f"晚餐 (17-19): {ms.get('dinner', 0)} 次")
    lines.append(f"其他时段: {ms.get('other', 0)} 次")

    lines.append("\n=== 热门消费地点 (Top 5) ===")
    top_locs = deep_insights.get('top_locations', {})
    for loc, count in top_locs.items():
        lines.append(f"  {loc}: {count} 次")
        
    lines.append("\n=== 异常检测 ===")
    lines.append(f"大额交易 (> {params['single_threshold']}元): {report['anomalies']['large_count']} 笔")
    lines.append(f"高频交易 ({params['freq_window']}min内 > {params['freq_count']}次): {report['anomalies']['freq_count']} 笔")
    
    return "\n".join(lines)


class AnalysisWindow(tk.Toplevel):
    """独立分析窗口"""
    def __init__(self, parent, title, records, params):
        super().__init__(parent)
        self.title(title)
        self.geometry("1000x700")
        self.records = records
        self.params = params
        
        self._init_ui()
        self._run_analysis()
        
    def _init_ui(self):
        # 左右分栏
        self.result_panel = ResultPanel(self)
        self.result_panel.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        self.chart_panel = ChartPanel(self)
        self.chart_panel.pack(side="right", fill="both", expand=True, padx=5, pady=5)
        
    def _run_analysis(self):
        if not self.records:
            self.result_panel.show_text("无数据")
            return
            
        analyzer = DataAnalyzer(self.records)
        report = analyzer.generate_report(
            self.params["single_threshold"],
            self.params["freq_window"],
            self.params["freq_count"]
        )
        deep_insights = analyzer.get_deep_insights()
        
        text = format_report_text(report, deep_insights, self.params)
        self.result_panel.show_text(text)
        self.chart_panel.update_charts(report["summary"]["daily"], report["habits"]["merchant_breakdown"])


class RecordDialog(tk.Toplevel):
    """新增/修改记录对话框"""
    def __init__(self, parent, title, record: Optional[ConsumptionRecord] = None, on_save: Callable = None):
        super().__init__(parent)
        self.title(title)
        self.record = record
        self.on_save = on_save
        
        self._init_ui()
        if record:
            self._load_record()
            
    def _init_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="both", expand=True)
        
        self.entries = {}
        fields = [
            ("学号", "student_id"), ("姓名", "name"), ("专业", "major"), ("年级", "grade"),
            ("余额", "balance"), ("时间", "timestamp"), ("金额", "amount"), 
            ("商户", "merchant_type"), ("地点", "location"), ("类型", "tx_type")
        ]
        
        for i, (label, key) in enumerate(fields):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=5)
            ent = ttk.Entry(frame, width=30)
            ent.grid(row=i, column=1, sticky="w", padx=5, pady=5)
            self.entries[key] = ent
            
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=len(fields), column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="保存", command=self._save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side="left", padx=5)
        
    def _load_record(self):
        r = self.record
        self.entries["student_id"].insert(0, r.student_id)
        self.entries["name"].insert(0, r.name)
        self.entries["major"].insert(0, r.major)
        self.entries["grade"].insert(0, r.grade)
        self.entries["balance"].insert(0, str(r.balance))
        self.entries["timestamp"].insert(0, r.timestamp.strftime(DATE_FMT))
        self.entries["amount"].insert(0, str(r.amount))
        self.entries["merchant_type"].insert(0, r.merchant_type)
        self.entries["location"].insert(0, r.location)
        self.entries["tx_type"].insert(0, r.tx_type)
        
    def _save(self):
        try:
            data = {k: v.get().strip() for k, v in self.entries.items()}
            
            # 简单校验
            if not data["student_id"] or not data["amount"]:
                messagebox.showwarning("提示", "学号和金额必填")
                return
                
            record = ConsumptionRecord(
                id=self.record.id if self.record else None,
                student_id=data["student_id"],
                name=data["name"],
                major=data["major"],
                grade=data["grade"],
                balance=float(data["balance"] or 0.0),
                timestamp=parse_datetime(data["timestamp"]),
                amount=float(data["amount"]),
                merchant_type=data["merchant_type"],
                location=data["location"],
                tx_type=data["tx_type"]
            )
            
            if self.on_save:
                self.on_save(record)
            self.destroy()
        except Exception as e:
            messagebox.showerror("错误", f"保存失败: {e}")


def launch():
    root = tk.Tk()
    # 设置默认字体大小，让界面看起来不那么拥挤
    style = ttk.Style()
    style.configure('.', font=('Microsoft YaHei', 9))
    style.configure('Treeview', rowheight=25)
    
    App(root)
    root.mainloop()
