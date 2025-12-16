import os

# 抑制 NumExpr 的警告
os.environ['NUMEXPR_MAX_THREADS'] = '16'

from ui import launch

if __name__ == "__main__":
    launch()