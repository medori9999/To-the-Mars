# Azure 기반 주식 투자 교육 서비스

> **" AI가 만들어내는 가장 현실적인 주식 시장, 그리고 완벽한 워크플로우 최적화"**
> 
> 실제 인간의 투자 심리(행동경제학)를 74% 수준으로 모사하는 수백 명의 생성형 에이전트들이 Azure 클라우드 환경 위에서 활동하는 가상 경제 생태계입니다. 실제 증권사와 동일한 호가 매칭 엔진을 구현하여 생동감 있는 투자 교육 환경을 제공하며,  메타 휴리스틱 알고리즘을 도입해 Azure OpenAI API 운영 비용을 49.5% 절감해 낸 상용화 수준의 대규모 AI 시뮬레이터입니다.

---
<video src="https://github.com/user-attachments/assets/7e1f80eb-9df8-4a1e-b726-30c9ad0d1710" autoplay loop muted playsinline width="100%"></video>

##  주요 기능 (Core Features)

### 1. 수백명의 생성형 에이전트 사회 (Agent Society)
단순한 룰(Rule) 기반 봇이 아닌, 고유의 페르소나와 심리 상태를 가진 AI 생태계입니다.
- **다중 페르소나 및 자산 분리:** 고래(Whale)와 개미(Citizen)로 자본 규모를 나누고, 가치투자/역발상/모멘텀 등의 투자 성향을 부여합니다.
- **인간 심리 완벽 모사:** 탐욕, 공포, 군중 심리 파라미터를 통해 실제 인간의 불완전한 4대 투자 심리(손실 회피, 군집 행동 등)를 백테스팅 기준 **74%의 유사도**로 구현했습니다.

> ![Image](https://github.com/user-attachments/assets/1e068f55-b897-4442-8ac2-1be1b2eb328f)

### 2. 실시간 연속 복수 호가 매칭 엔진 (CDA Market Engine)
![Image](https://github.com/user-attachments/assets/0b2083b9-58dd-4623-9479-693ef28fc259)

현실의 증권 거래소와 완벽히 동일한 비동기 매칭 시스템을 백엔드에 구축했습니다.

- **Time-Warp 동기화:** 현실의 2초를 가상 시장의 1분으로 매핑하여 비동기(Asyncio) 기반의 초고속 시뮬레이션을 진행합니다.
- **Human-in-the-Loop:** 500명의 AI 사이에서 실제 유저(인간)가 개입하여 실시간 거래가 가능하며, 유저의 행동이 시장 가격과 에이전트 여론에 즉각적인 영향을 미칩니다.

### 3. AI 멘토 대시보드 및 인터랙티브 챗봇 (AI Mentor & Chatbot)

![Image](https://github.com/user-attachments/assets/ec3e4bae-8aab-4e6d-9933-a204e8ed3a99)

유저의 투자 여정을 돕고 실시간으로 소통할 수 있는 개인화된 AI 조언자 시스템입니다.

4인 4색 맞춤형 피드백: 가치투자, 퀀트, 역발상 등 각기 다른 투자 철학을 가진 4명의 AI 멘토가 유저의 실시간 포트폴리오와 매매 기록(Trade History)을 분석하여 날카로운 맞춤형 피드백을 제공합니다.
양방향 챗봇 인터페이스: 단순한 일방향 조언을 넘어, 유저가 현재 시장 상황이나 특정 종목의 전망에 대해 멘토에게 직접 질문하고 실시간으로 답변을 받을 수 있는 대화형 챗봇 기능을 지원하여 몰입감을 극대화합니다.


---

##  기술적 챌린지 및 해결 (Technical Deep Dive)

###  [Core] LLM API 비용 폭발 이슈 ➔ 메타 휴리스틱(AFLOW) 기반 워크플로우 최적화

<img width="1500" height="507" alt="Image" src="https://github.com/user-attachments/assets/784321c6-bea9-491f-b6c1-40d67827a88a" />

- **문제:** 수백명의 에이전트가 매 틱마다 뉴스를 읽고 판단(앙상블 기법 적용)하면서 Azure OpenAI 토큰 비용이 기하급수적으로 폭발하여 상용화가 불가능한 수준의 유지비가 발생했습니다.
- **해결:** 최신 논문(ICLR 2025 AFLOW)의 트리 탐색 아이디어에서 착안하여, **유전 알고리즘(GA)과 시뮬레이티드 어닐링(SA)이라는 메타 휴리스틱 기법을 백엔드에 직접 도입**했습니다.
    - 시스템 스스로 **1) 프롬프트 압축률, 2) 자가 검증 노드 배치, 3) 동적 라우팅(급등락장 룰 기반 스킵)** 이라는 3가지 레고 블록을 조합하도록 설계.
    - KKT 조건을 만족할 수 없는 블랙박스(Black-box) 및 이산(Discrete) 환경에서 단 15세대 만에 탐색 공간의 전역 최적해를 도달.
- **결과:** 에이전트 지능(93.4점)을 완벽하게 방어함과 동시에, **API 호출 비용을 49.5% 절감**하는 파레토 최적점(Pareto Optimum) 달성에 성공했습니다.

###  Human-in-the-Loop 환경의 병목 ➔ 마켓 메이커 동적 유동성 공급
- **문제:** 수만 건의 AI 주문 대기열 속에서 실제 유저가 개입하여 주문을 넣었을 때 체결이 지연되며 사용자 경험(UX)이 극도로 저하되는 현상 발생.
- **해결:** 유저가 정상 호가 내에서 주문 시, **Market Maker(시장 조성자) 알고리즘**이 개입하여 즉각적으로 유동성을 공급하는 하이패스 로직을 구현했습니다.
- **결과:** 복잡한 백엔드 시뮬레이션 로직을 훼손하지 않으면서, 유저의 주문을 1초 이내(Sub-second)에 무지연 체결시켜 압도적인 몰입감을 제공합니다.

###  데이터 팽창으로 인한 DB 과부하 ➔ 쿼리 최적화 및 인덱싱
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
## 파이프라인

<img width="1521" height="712" alt="Image" src="https://github.com/user-attachments/assets/9d8ace48-c33b-444e-b526-f52f8c27fd31" />

##  프로젝트 구조 (Directory Structure)

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