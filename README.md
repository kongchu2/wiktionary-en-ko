# Wiktionary-en-ko — Yomitan용 영한사전

한국어 · [English](README.en.md)

[Yomitan](https://github.com/yomidevs/yomitan)에서 쓰는 **영어→한국어** 사전입니다.
[영어 위키낱말사전](https://en.wiktionary.org/)의 표제어, 품사, 뜻 구분을 그대로 쓰고([kaikki.org](https://kaikki.org/) 추출본), 각 뜻을 LLM으로 한국어로 번역합니다.

> 107,824개 항목(뜻 219,495개)을 Claude Haiku로 번역했습니다.

## 수록 범위

| 범위 | 표제어 | 항목 | 뜻 |
|---|---|---|---|
| 단일 단어: [wordfreq](https://github.com/rspeer/wordfreq) 빈도 상위 50,000, 하이픈으로 이은 말(`long-term`) 포함 | 47,096 | 69,760 | 165,748 |
| 구동사: 위 동사 + 불변화사 (`give up`, `look forward to`) | — | 4,523 | 10,040 |
| 그 밖의 여러 단어 표제어 (`of course`, `fall in love`, `ice cream`) | — | 33,541 | 43,707 |
| 합계 | | 107,824 | 219,495 |

- 활용형(`went`, `children`, `years`)과 다른 철자(`favorite` → favourite)는 따로 번역하지 않고 원형 항목으로 연결합니다(`source/forms.jsonl`, 59,321개. `fell in love` → fall in love도 포함). Yomitan이 스스로 풀 수 있는 규칙 활용형(`plans`)은 여기에 넣지 않습니다.
- 활용형만 상위 50,000 안에 있는 단어(`relegated` → relegate, `microorganisms` → microorganism)는 원형을 넣었습니다.
- 약어·축약형(`it's`, `Mr`, `CIA`)은 일반 뜻이 없는 항목만, 풀이 2개까지 넣었습니다.
- 문자·기호·접사 항목, 한 글자 표제어(관사 `a`와 대명사 `I`만 남김)와, 폐어·고어·희귀·방언·옛말투·비표준·오철자 표시가 붙은 뜻은 뺐습니다.
- 고유명사(`London`, `March`, `English`)는 포함하되, 표제어마다 성씨 1개, 이름 1개, 지명 2개까지만 남기고 "여러 곳의 지명" 아래에 나열된 동명 지명은 뺐습니다.
- 소문자 단어와 철자가 겹치는 대문자 변형(`She` 민족 이름, `TO` 동사, `Grew` 성씨)은 `source/deferred.jsonl`에 따로 빼 두었습니다(8,783개 항목). 번역도 빌드도 하지 않습니다. `I`, `US`, `IT`, `AM`, `ID`와, 고유한 뜻이 있는 고유명사(`March`, `Turkey`)는 남깁니다.
- 여러 단어 표제어와 하이픈으로 이은 말은 2~4단어이고 모든 단어가 상위 50,000 안인 것입니다. 명사와 고유명사는 너무 많아서 위키낱말사전에 3개 언어 이상 번역이 달린 것만 넣었습니다. 아주 흔한 단어로만 된 것(`to the`, `for you`)도 같은 기준을 적용했고, 빈자리가 있는 것(`pull someone's leg`)은 뺐습니다.
- 선정 결과는 `source/entries.jsonl`에 들어 있고, 빌드는 이 파일만 봅니다.

## 설치

1. [Releases](../../releases/latest)에서 `wiktionary-en-ko.zip`을 받습니다.
2. Yomitan → 설정 → 일반에서 언어를 English로 바꿉니다.
3. Yomitan → 설정 → 사전(Dictionaries) → 가져오기(Import)에서 zip을 불러옵니다.

활용형과 구동사도 검색됩니다(`running` → run, `pick it up` → pick up).

Yomitan → 설정 → Lookup resolution을 Word로 바꾸는 것을 권합니다. 기본값(Letter)에서는 `went` 밑에 `wen`, `we` 같은 앞부분 일치 항목이 함께 나옵니다.

## 번역 품질

- 한국어 뜻은 LLM(Claude Haiku) 자동 번역이라 오역이 있습니다. 항목마다 영어 원문(Wiktionary)을 접어 두었으니 확인용으로 쓰세요.
- 위키낱말사전은 뜻을 역사 순서로 나열해서 첫 뜻이 옛 뜻인 경우가 많습니다(`with` → "~에 맞서", `team` → "역축 한 조"). 그래서 빈도 상위 5,000개 철자(3,672개)는 Claude Sonnet이 품사와 뜻을 현대 영어에서 흔한 순서로 다시 배열했습니다(`translations/order.jsonl`, 손으로 고칠 수 있음). 활용형으로 읽히는 게 보통인 철자의 사소한 항목(`years` "한참", `goals` "닮고 싶은")은 숨겨서 원형(year, goal)이 먼저 나오게 했습니다.
- 모델이 확신하지 못한 항목에는 `※ 자동 번역 신뢰도 낮음` 표시가 붙습니다. 7,261개 항목(6.7%)입니다.
- 지금까지 한 품질 확인은 300개 항목(뜻 883개)의 블라인드 테스트 하나이고, 채점도 Claude가 했습니다. 뜻의 약 2%에 문제가 있었는데, 대부분은 부정확한 표현이고 일부는 뜻이 틀렸습니다. 모델이 모델을 채점했으므로 실제 비율은 더 높을 수 있습니다. 뜻이 12개를 넘는 항목은 테스트에 없었습니다.
- 오역 수정은 `translations/terms.jsonl`에서 해당 항목 줄의 `s`(뜻별 한국어 목록)를 고치면 됩니다.

## 직접 빌드하기

Python 3.9 이상, 그리고 번역할 때는 [Claude Code](https://claude.com/claude-code) CLI(`claude`)가 필요합니다.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python -m enko fetch                         # Yomitan 스키마 다운로드
.venv/bin/python -m enko translate tags                # 품사·용법 태그 한국어 라벨
.venv/bin/python -m enko translate terms --limit 1000  # 빈도순으로 미번역 항목 번역 (재실행하면 이어서)
.venv/bin/python -m enko translate order --model sonnet  # 상위 5,000 철자의 품사·뜻 순서 정리
.venv/bin/python -m enko build                         # dist/wiktionary-en-ko.zip
.venv/bin/python -m enko validate                      # Yomitan 스키마 검증 + 활용 규칙 확인
.venv/bin/python -m enko review -n 200                 # review/sample.md 에 검수용 샘플
.venv/bin/python -m enko status                        # 진행 상황
node tools/lookup.mjs went "fell in love"                # Yomitan의 조회 코드로 zip을 찾아보기
node tools/lookup.mjs --text article.txt --word         # 글을 단어마다 찍어 보고 안 나오는 말 모으기
```

- `tools/`의 두 스크립트는 [Yomitan](https://github.com/yomidevs/yomitan) 소스를 `data/yomitan`에 받아 두어야 돌아갑니다(`git clone --depth 1`, npm 설치는 필요 없음). `select`도 이것으로 Yomitan이 스스로 푸는 활용형을 가려냅니다. 없으면 연결 행을 전부 남깁니다.

- `build --include-untranslated`를 붙이면 미번역 항목도 영어 뜻으로 포함합니다.
- 번역 대상을 다시 뽑으려면 `python -m enko select`를 실행합니다. kaikki 영어 덤프(약 530MB)가 없으면 `data/raw/`에 받습니다. 뜻이 바뀐 항목은 다음 `translate` 때 다시 번역되고, 그 전까지 빌드에서 빠집니다.
- GitHub Actions(`.github/workflows/release.yml`)가 `translations/`, `source/`, `enko/`가 바뀔 때 다시 빌드하고, 내용이 바뀐 경우에만 릴리스를 만듭니다. 번역은 로컬에서 돌리고 `translations/`를 커밋하세요.

## 라이선스

- 코드(`enko/`, `.github/`): [MIT](LICENSE).
- 사전 데이터(`source/`, `translations/`, 빌드된 zip): [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  영어 위키낱말사전의 파생물이며, 기계 판독용 데이터는 [Wiktextract](https://kaikki.org/)에서 가져왔습니다.
- 번역 대상을 고를 때 쓰는 빈도 데이터: [wordfreq](https://github.com/rspeer/wordfreq) (CC BY-SA 4.0). 빌드 결과물에는 포함되지 않습니다.
