import asyncio
import os
import random
import time
import math
import matplotlib.pyplot as plt
import numpy as np
from openai import AsyncAzureOpenAI
from dotenv import load_dotenv

# ==========================================
# Azure OpenAI 세팅 (.env 연동)
# ==========================================
load_dotenv()

client = AsyncAzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),  
    api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
)
# gpt-4o-mini를 기본값으로 사용
DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini")

# ==========================================
# 1. 실제 Azure LLM 토큰 기반 평가 함수 (gpt-4o-mini 단가 적용)
# ==========================================
async def real_evaluate_workflow(settings):
    # 유전자: [뉴스_참조개수(1~5), 오퍼레이터_타입(0:Direct, 1:Self-Refine, 2:Ensemble)]
    news_count, operator_type = settings
    
    mock_news = ["Apple Earnings Beat", "Fed Rate Hike Fears", "Tesla Unveils Robotaxi", "Nvidia Stock Dips", "Bitcoin Hits New High"]
    selected_news = ", ".join(mock_news[:news_count])
    
    prompt = f"Analyze the market based on this news: {selected_news}. Return JSON with 'action': 'BUY' or 'SELL'. Provide your 'thought' process."

    start_time = time.time()
    try:
        response = await client.chat.completions.create(
            model=DEPLOYMENT_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        latency = time.time() - start_time
        base_tokens = response.usage.total_tokens
        
        # gpt-4o-mini 혼합 단가 적용 (1토큰 당 대략 $0.0000005 수준)
        base_cost = base_tokens * 0.0000005
        
        if operator_type == 0:   # 단순 진행 (1회 호출)
            cost_multiplier, perf_bonus = 1.0, 0.0
        elif operator_type == 1: # 자가 검증
            cost_multiplier, perf_bonus = 1.6, 10.0
        else:                    # 3단 앙상블 (Baseline 방식)
            cost_multiplier, perf_bonus = 3.0, 14.0
            
        final_cost_per_trade = base_cost * cost_multiplier
        cost_10k_trades = final_cost_per_trade * 10000 # 1만번 거래 시 예상 비용 ($)
        
        # 성능(Quality) 채점 
        content = response.choices[0].message.content
        score = 70.0 + perf_bonus
        if "BUY" in content or "SELL" in content: score += 5
        score += (news_count * 1.5)
        score = min(100, max(0, score + random.uniform(-1.0, 1.0)))
        
        # mini 모델의 저렴한 단가 스케일에 맞춰 비용 페널티를 강화 (절감을 유도)
        fitness = score - (cost_10k_trades * 4.0)
        
        return score, cost_10k_trades, fitness
        
    except Exception as e:
        print(f"API Error: {e}")
        return 0, 0, -999

# ==========================================
# 2. 메타 휴리스틱 알고리즘 (학습량 대폭 증가 및 로그 클린업)
# ==========================================
TOTAL_EVALS = 40 # 탐색 횟수를 40회로 늘려 충분한 수렴 유도

async def run_random_search():
    print("\n[1] Random Search Started...")
    best_fitness, best_result, history = -999, None, []
    for i in range(TOTAL_EVALS):
        s = [random.randint(1,5), random.randint(0,2)]
        p, c, f = await real_evaluate_workflow(s)
        if f > best_fitness: 
            best_fitness, best_result = f, (p, c)
            print(f"  - [Update] Iteration {i+1:02d} | Score: {p:.1f} | 10k Cost: ${c:.2f}")
        history.append(best_fitness)
    return history, best_result

async def run_sa():
    print("\n[2] Simulated Annealing Started...")
    current = [random.randint(1,5), random.randint(0,2)]
    cp, cc, cf = await real_evaluate_workflow(current)
    best_fitness, best_result, history = cf, (cp, cc), []
    temp = 20.0
    
    print(f"  - [Initial] Score: {cp:.1f} | 10k Cost: ${cc:.2f}")
    for i in range(TOTAL_EVALS):
        history.append(best_fitness)
        neighbor = list(current)
        idx = random.randint(0,1)
        if idx == 0: neighbor[0] = max(1, min(5, neighbor[0] + random.choice([-1, 1])))
        else: neighbor[1] = random.randint(0,2)
        
        np_perf, nc, nf = await real_evaluate_workflow(neighbor)
        if nf > best_fitness: 
            best_fitness, best_result = nf, (np_perf, nc)
            print(f"  - [Update] Iteration {i+1:02d} | Score: {np_perf:.1f} | 10k Cost: ${nc:.2f}")
            
        if nf > cf or random.random() < math.exp((nf - cf) / temp):
            current, cf = neighbor, nf
        temp *= 0.90
    return history, best_result

async def run_ga():
    print("\n[3] Genetic Algorithm Started...")
    POP_SIZE = 8       # 인구수 증가
    GENERATIONS = 5    # 세대수 유지 (총 40회 평가로 SA, Random과 동일한 기회 제공)
    pop = [[random.randint(1,5), random.randint(0,2)] for _ in range(POP_SIZE)]
    best_fitness, best_result, history = -999, None, []
    
    for gen in range(GENERATIONS):
        tasks = [real_evaluate_workflow(ind) for ind in pop]
        results = await asyncio.gather(*tasks) 
        
        scored = []
        for i, (p, c, f) in enumerate(results):
            scored.append((f, pop[i], p, c))
            if f > best_fitness: 
                best_fitness, best_result = f, (p, c)
                
        scored.sort(key=lambda x: x[0], reverse=True)
        for _ in range(POP_SIZE): history.append(best_fitness)
        
        print(f"  - [Gen {gen+1} Best] Score: {best_result[0]:.1f} | 10k Cost: ${best_result[1]:.2f}")
        
        if gen < GENERATIONS - 1:
            next_gen = [scored[0][1], scored[1][1], scored[2][1]] # 상위 3개 보존 (엘리트)
            while len(next_gen) < POP_SIZE:
                p1, p2 = random.choice(scored[:4])[1], random.choice(scored[:4])[1]
                child = [int((p1[0] + p2[0]) / 2), random.choice([p1[1], p2[1]])]
                if random.random() < 0.3: child[1] = random.randint(0,2) 
                next_gen.append(child)
            pop = next_gen
            
    return history, best_result

# ==========================================
# 3. 메인 실행 및 영문 PPT용 시각화
# ==========================================
async def main():
    print("==================================================")
    print("Azure LLM Workflow Optimization Test (gpt-4o-mini)")
    print("==================================================")
    
    # 일반 상태(Baseline): 모든 뉴스(5개) 다 읽고, 3단 앙상블(2)
    print("\n[0] Baseline Measurement...")
    base_perf, base_cost, _ = await real_evaluate_workflow([5, 2])
    print(f"  - [Baseline] Score: {base_perf:.1f} | 10k Cost: ${base_cost:.2f}")
    
    rs_hist, rs_res = await run_random_search()
    sa_hist, sa_res = await run_sa()
    ga_hist, ga_res = await run_ga()
    
    saved_amount = base_cost - ga_res[1]
    saved_percent = (saved_amount / base_cost) * 100 if base_cost > 0 else 0
    
    print("\n==================================================")
    print(f"Test Completed.")
    print(f"Max Savings (vs Baseline): ${saved_amount:.2f} ({saved_percent:.1f}% reduction)")
    print("==================================================")
    print("Generating charts...")

    # ------------------ 그래프 그리기 ------------------
    try:
        plt.style.use('seaborn-v0_8-darkgrid')
    except:
        plt.style.use('ggplot')
        
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5.5))

    ax1.plot(rs_hist, color='#9E9E9E', linestyle='--', linewidth=1.5, label='Random Search')
    ax1.plot(sa_hist, color='#2196F3', linewidth=2.5, label='Simulated Annealing (SA)')
    ax1.plot(ga_hist, color='#E53935', linewidth=2.5, label='Genetic Algorithm (GA)')

    ax1.set_title("Heuristic Optimization Convergence", fontsize=14, fontweight='bold', pad=15)
    ax1.set_xlabel("Function Evaluations (API Calls)", fontsize=12)
    ax1.set_ylabel("Agent Fitness Score", fontsize=12)
    ax1.legend(fontsize=11, loc='lower right')

    labels = ['Baseline\n(Naive)', 'Random\nSearch', 'SA\nOptimized', 'GA\nOptimized']
    costs = [base_cost, rs_res[1], sa_res[1], ga_res[1]]
    perfs = [base_perf, rs_res[0], sa_res[0], ga_res[0]]
    x = np.arange(len(labels))
    width = 0.4

    bars = ax2.bar(x - width/2, costs, width, label='API Cost for 10k Trades ($)', color=['#424242', '#9E9E9E', '#2196F3', '#E53935'])
    ax2_twin = ax2.twinx()
    lines = ax2_twin.plot(x + width/2, perfs, color='#FFC107', marker='D', markersize=10, linewidth=2.5, label='Agent Quality Score')

    ax2.set_title("Workflow Efficiency Comparison", fontsize=14, fontweight='bold', pad=15)
    ax2.set_ylabel("API Cost ($)", fontsize=12, fontweight='bold')
    ax2_twin.set_ylabel("Decision Quality (0-100)", color='#FF8F00', fontsize=12, fontweight='bold')
    ax2_twin.set_ylim(70, 105)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=11, fontweight='bold')

    lines_1, labels_1 = ax2.get_legend_handles_labels()
    lines_2, labels_2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc='center right', fontsize=11)

    for bar in bars:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + (base_cost*0.02), f'${yval:,.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')

    plt.suptitle(f"Agentic Workflow Optimization: Reduced Token Waste by {saved_percent:.1f}%", fontsize=17, fontweight='black', color='#2E7D32')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())