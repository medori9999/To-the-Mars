# Azure 기반 주식 투자 교육 서비스

> **" AI가 만들어내는 가장 현실적인 주식 시장, 그리고 완벽한 워크플로우 최적화"**
> 
> 실제 인간의 투자 심리(행동경제학)를 74% 수준으로 모사하는 수백명의 생성형 에이전트들이 활동하는 가상 경제 생태계입니다. 실제 주식 시장과 동일한 호가 매칭 엔진을 백엔드에 구현하였으며, 특히 **메타 휴리스틱 알고리즘을 도입해 LLM API 운영 비용을 49.5% 절감**한 상용화 수준의 대규모 AI 시뮬레이터입니다.

---
<video src="https://github.com/user-attachments/assets/7e1f80eb-9df8-4a1e-b726-30c9ad0d1710" autoplay loop muted playsinline width="100%"></video>

## 💡 주요 기능 (Core Features)

### 1. 수백명의 생성형 에이전트 사회 (Agent Society)
단순한 룰(Rule) 기반 봇이 아닌, 고유의 페르소나와 심리 상태를 가진 AI 생태계입니다.
- **다중 페르소나 및 자산 분리:** 고래(Whale)와 개미(Citizen)로 자본 규모를 나누고, 가치투자/역발상/모멘텀 등의 투자 성향을 부여합니다.
- **인간 심리 완벽 모사:** 탐욕, 공포, 군중 심리 파라미터를 통해 실제 인간의 불완전한 4대 투자 심리(손실 회피, 군집 행동 등)를 백테스팅 기준 **74%의 유사도**로 구현했습니다.

> **[에이전트 실시간 매매 로그 및 뇌동매매 시현]**
> ![Image](https://github.com/user-attachments/assets/여기에_에이전트거래_GIF_링크_삽입)

### 2. 실시간 연속 복수 호가 매칭 엔진 (CDA Market Engine)
<img width="1339" height="618" alt="Image" src="https://github.com/user-attachments/assets/여기에_호가창UI_이미지_링크_삽입" />

현실의 증권 거래소와 완벽히 동일한 비동기 매칭 시스템을 백엔드에 구축했습니다.

- **Time-Warp 동기화:** 현실의 2초를 가상 시장의 1분으로 매핑하여 비동기(Asyncio) 기반의 초고속 시뮬레이션을 진행합니다.
- **Human-in-the-Loop:** 500명의 AI 사이에서 실제 유저(인간)가 개입하여 실시간 거래가 가능하며, 유저의 행동이 시장 가격과 에이전트 여론에 즉각적인 영향을 미칩니다.

### 3. 실시간 동적 환경 RAG (Dynamic Environment RAG)
에이전트가 시장 흐름을 정확히 읽고 판단할 수 있도록 돕는 컨텍스트 엔지니어링 파이프라인입니다.
- **3-Way 데이터 결합:** Bing API(거시/미시 경제 뉴스) + 실시간 호가 추세 + 종토방(커뮤니티) 여론 수치를 실시간으로 수집 및 가공하여 에이전트의 프롬프트에 주입합니다.

> <img width="713" height="524" alt="Image" src="https://github.com/user-attachments/assets/여기에_RAG아키텍처_또는_뉴스수집_이미지_링크_삽입" />

---

## 🛠 기술적 챌린지 및 해결 (Technical Deep Dive)

### 🚨 [Core] LLM API 비용 폭발 이슈 ➔ 메타 휴리스틱(AFLOW) 기반 워크플로우 최적화

<img width="1298" height="484" alt="Image" src="https://github.com/user-attachments/assets/여기에_아까_만든_파레토최적화_그래프_이미지_링크_삽입" />

- **문제:** 500명의 에이전트가 매 틱마다 뉴스를 읽고 판단(앙상블 기법 적용)하면서 Azure OpenAI 토큰 비용이 기하급수적으로 폭발하여 상용화가 불가능한 수준의 유지비가 발생했습니다.
- **해결:** 최신 논문(ICLR 2025 AFLOW)의 트리 탐색 아이디어에서 착안하여, **유전 알고리즘(GA)과 시뮬레이티드 어닐링(SA)이라는 메타 휴리스틱 기법을 백엔드에 직접 도입**했습니다.
    - 시스템 스스로 **1) 프롬프트 압축률, 2) 자가 검증 노드 배치, 3) 동적 라우팅(급등락장 룰 기반 스킵)** 이라는 3가지 레고 블록을 조합하도록 설계.
    - KKT 조건을 만족할 수 없는 블랙박스(Black-box) 및 이산(Discrete) 환경에서 단 15세대 만에 탐색 공간의 전역 최적해를 도달.
- **결과:** 에이전트 지능(93.4점)을 완벽하게 방어함과 동시에, **API 호출 비용을 49.5% 절감**하는 파레토 최적점(Pareto Optimum) 달성에 성공했습니다.

### ⚡ Human-in-the-Loop 환경의 병목 ➔ 마켓 메이커 동적 유동성 공급
- **문제:** 수만 건의 AI 주문 대기열 속에서 실제 유저가 개입하여 주문을 넣었을 때 체결이 지연되며 사용자 경험(UX)이 극도로 저하되는 현상 발생.
- **해결:** 유저가 정상 호가 내에서 주문 시, **Market Maker(시장 조성자) 알고리즘**이 개입하여 즉각적으로 유동성을 공급하는 하이패스 로직을 구현했습니다.
- **결과:** 복잡한 백엔드 시뮬레이션 로직을 훼손하지 않으면서, 유저의 주문을 1초 이내(Sub-second)에 무지연 체결시켜 압도적인 몰입감을 제공합니다.

### 🗄 데이터 팽창으로 인한 DB 과부하 ➔ 쿼리 최적화 및 인덱싱
- **문제:** 시뮬레이션 진행 시 `trades` 테이블에 수십만 개의 데이터가 누적되어, 프론트엔드의 차트 갱신 시 Full Table Scan으로 인한 서버 Connection Pool 고갈 발생.
- **해결:** 거래량 계산 로직의 비동기 분리 및 DB Timestamp 인덱싱 추가 적용 (필요시 빠르고 안전한 메모리 플러시 스크립트 구축).

---

##  기술 스택 (Tech Stack)

| 구분 | 기술 스택 |
| :--- | :--- |
| **Frontend** | React, Vite (실시간 폴링 및 상태 관리 UX) |
| **Backend** | FastAPI, Uvicorn, Python Asyncio, SQLAlchemy (비동기 컨트롤 타워) |
| **AI Service** | Azure OpenAI (GPT-4o, GPT-4o-mini), Bing Search API |
| **Cloud/Infra** | Azure App Service, Azure PostgreSQL, GitHub Codespaces |
| **Algorithm** | Meta-Heuristics (Genetic Algorithm, Simulated Annealing) |

---

## 📂 프로젝트 구조 (Directory Structure)

```bash
ASFM_Simulator/
├── backend/                    # FastAPI 기반 비동기 시뮬레이션 서버
│   ├── main_simulation.py      # 시뮬레이션 메인 루프 및 타임워프 동기화 엔진
│   ├── market_engine.py        # CDA 매칭 알고리즘 및 마켓 메이커 로직
│   ├── init_agents.py          # 500명 에이전트 페르소나 및 심리 파라미터 세팅
│   ├── optimization_test.py    # [Core] 메타 휴리스틱 기반 비용/워크플로우 최적화 로직
│   └── human_alignment.py      # 행동경제학 지표 기반 인간 모사도 평가 스크립트
├── frontend/                   # React 기반 실시간 트레이딩 UI 및 대시보드
└── data/                       # 기업 마스터 데이터 및 초기 설정 DB