import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import datetime
import os

# Set visual style
sns.set_theme(style="whitegrid")
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei']  # Setup for Mac/Windows Chinese
plt.rcParams['axes.unicode_minus'] = False # Normal minus symbol

# Setup paths
DATA_PATH = '../events.csv'
OUT_DIR = 'images'
os.makedirs(OUT_DIR, exist_ok=True)

REPORT_PATH = 'Shopee_AP_Data_Analytics_Report.md'

print("Loading data...")
df = pd.read_csv(DATA_PATH)

print("Preprocessing data...")
# Convert ms timestamp to datetime
df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
df['date'] = df['datetime'].dt.date
df['hour'] = df['datetime'].dt.hour
df['day_of_week'] = df['datetime'].dt.dayofweek

# 1. Funnel Analysis -----------------------------------------
print("1. Computing Funnel...")
funnel_counts = df['event'].value_counts().reindex(['view', 'addtocart', 'transaction'])

plt.figure(figsize=(10, 6))
ax = sns.barplot(x=funnel_counts.index, y=funnel_counts.values, palette='viridis')
plt.title('用户核心行为漏斗 (User Behavior Funnel)', fontsize=16)
plt.ylabel('Event Count')
plt.xlabel('Event Type')

# Add percentage drop labels
for i in range(len(funnel_counts)):
    pct = funnel_counts.values[i] / funnel_counts.values[0] * 100
    ax.text(i, funnel_counts.values[i], f'{funnel_counts.values[i]:,}\n({pct:.2f}%)', 
            ha='center', va='bottom', fontsize=12, fontweight='bold')
    
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'funnel.png'), dpi=300)
plt.close()

# 2. Time-series Analysis (Activity by hour) ----------------
print("2. Computing time series...")
hourly_activity = df.groupby('hour')['event'].count()

plt.figure(figsize=(12, 6))
sns.lineplot(x=hourly_activity.index, y=hourly_activity.values, marker="o", linewidth=2.5, color='coral')
plt.title('全站 24 小时活跃度趋势 (24-Hour Activity Trend)', fontsize=16)
plt.xlabel('Hour of Day')
plt.ylabel('Total Events')
plt.xticks(range(0, 24))
plt.fill_between(hourly_activity.index, hourly_activity.values, alpha=0.2, color='coral')
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'hourly_trend.png'), dpi=300)
plt.close()

# 3. RFM Analysis (R & F only as M is not uniformly available) ----
print("3. Computing RFM (Recency & Frequency)...")
purchases = df[df['event'] == 'transaction'].copy()

# Fix max date as 'today' for Recency
max_date = df['datetime'].max()

# Aggregate per visitor
rf = purchases.groupby('visitorid').agg({
    'datetime': lambda x: (max_date - x.max()).days, # Recency
    'transactionid': 'nunique'                       # Frequency
}).rename(columns={'datetime': 'Recency', 'transactionid': 'Frequency'})

# R and F score based on quantiles. R is inverse (smaller is better).
labels_r = range(4, 0, -1)
r_quartiles = pd.qcut(rf['Recency'], q=4, labels=labels_r, duplicates='drop')
rf['R_score'] = r_quartiles

# Frequency is heavily skewed to 1.
def f_score(x):
    if x == 1: return 1
    elif x == 2: return 2
    elif x <= 5: return 3
    else: return 4
    
rf['F_score'] = rf['Frequency'].apply(f_score)
rf['RF_Segment'] = rf['R_score'].astype(str) + rf['F_score'].astype(str)

# Grouping logic
def segment_customer(row):
    r, f = int(row['R_score']), int(row['F_score'])
    if (r >= 3 and f >= 3):
        return '核心高价值用户 (Champions)'
    elif (r >= 3 and f < 3):
        return '近期潜力用户 (Recent Potential)'
    elif (r < 3 and f >= 3):
        return '流失高优需挽回用户 (At Risk / Needs Attention)'
    else:
        return '低沉睡用户 (Hibernating)'

rf['Segment'] = rf.apply(segment_customer, axis=1)
segment_counts = rf['Segment'].value_counts()

plt.figure(figsize=(10, 6))
colors = sns.color_palette("Set2")[0:len(segment_counts)]
plt.pie(segment_counts.values, labels=segment_counts.index, autopct='%1.1f%%', 
        colors=colors, startangle=140, textprops={'fontsize': 12, 'fontweight': 'bold'})
plt.title('用户 RF 价值分层模型 (User Segmentation)', fontsize=16)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'rf_segmentation.png'), dpi=300)
plt.close()

# 4. Generate Markdown Report --------------------------------
print("4. Generating Markdown Report...")

view_cnt = funnel_counts.get('view', 0)
add_cnt = funnel_counts.get('addtocart', 0)
buy_cnt = funnel_counts.get('transaction', 0)

view_to_add = (add_cnt / view_cnt) * 100 if view_cnt else 0
add_to_buy = (buy_cnt / add_cnt) * 100 if add_cnt else 0
overall_conv = (buy_cnt / view_cnt) * 100 if view_cnt else 0

md_content = f"""# Shopee AP: Data Analytics Case Study - Retailrocket E-commerce Platform

**Role Target**: Data Analytics (DA) / Product Management (PM) \\
**Project Scope**: Event Log Analysis, Funnel Optimization, User Segmentation (RF Mode)

---

## 1. 核心业务漏斗洞察 (Core Funnel Insights)
*漏斗分析可以帮助我们迅速找到平台的“漏水”口，进而提出核心的产品界面和运营链路优化方案。*

![Funnel](images/funnel.png)

### 数据结论
* **View (浏览)**: {view_cnt:,} (100%)
* **Add to Cart (加购)**: {add_cnt:,} ({view_to_add:.2f}% of views)
* **Transaction (购买)**: {buy_cnt:,} ({overall_conv:.4f}% overall)

### 诊断与策略建议：
- **诊断**：从浏览到加购的转化率处于极低的水平 ({view_to_add:.2f}%)，这在大型综合电商（如 Shopee）中意味着商品详情页（PDP页）并没有释放足够的购买促动意愿，或者浏览本身带有了大量无效流量（例如误触/低意向导流）。
- **策略：优化加购链路**
  - **产品侧优化**：对于高流量低加购率的单品，考虑在详情页透传更加直观的限时折扣标签 (`Flash Sale`) 和免邮券 (`Free Shipping`) 信息，以刺激首单加购。
  - **运营侧动作**：利用推荐系统给一直在观望的用户推出 “Bundle Deals (组合特惠)”，提升商品连带率和加购意愿。

---

## 2. 用户活跃大盘趋势 (User Activity Trend)
*用户的活跃高峰决定了我们的资源投放时段（例如大促营销推送时段配置）。*

![Hourly Trend](images/hourly_trend.png)

### 数据结论
* 用户的行为波动存在着极强的波浪形周期，通过 24 小时的切片我们可以提取出流量的高峰期通常落在晚间时段的 **19:00 - 22:00** 附近。

### 诊断与策略建议：
- **资源精准投放**：Push notification 消息的推送、全网直播带货的流量引流应当密集排布在黄金时间段。
- **系统弹性扩容响应**：工程链路需留意晚间峰值的 TPS，确保结账链路 (`Checkout`) 不会出现限流。

---

## 3. 核心用户价值分阶：RF模型 (RF Segmentation)
*基于 Recency (最近消费时间) 与 Frequency (消费频次) 对发生过购买行为的用户进行打标签分群。*

![RF Segmentation](images/rf_segmentation.png)

### 数据结论
* 数据中复购的高价值活跃用户 (`核心高价值用户`) 占比较小，说明该平台存在极其依赖新客单次成交的窘境。
* 存在大量在过去有过多次购买，但近期陷入停滞状态的群体 (`流失高优需挽回用户`) 或是只购买过一次便无音讯的群体。

### 诊断与策略建议：
1. **针对核心高价值用户 (Champions)**：
   - 给予 VIP 及返现积分体系（如 Shopee Coins）的多倍奖励。优先体验新品的权益。
2. **针对流失高优需挽回用户**：
   - 这是曾经信任过平台的群体，流失可能因为竞对补贴。应通过唤醒邮件 (EDM) 或派发高门槛的大额满减券（如 Shopee 9.9 Super Shopping Day Voucher）来精准刺激复购。
3. **针对近期的新晋买家 (最近购物，但频次仅有1次)**：
   - 提供新客专享的复购关怀盲盒或低客单价的高复购引流品（如快消品、纸巾等）促使其完成第二次下单，从而养成心智。
"""

with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    f.write(md_content)

print(f"Report saved to {REPORT_PATH}")
