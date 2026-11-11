# Wiktionary-en-ko — Yomitan용 영한사전

[Yomitan](https://github.com/yomidevs/yomitan)에서 쓰는 **영어→한국어** 사전입니다.
[영어 위키낱말사전](https://en.wiktionary.org/)의 표제어, 품사, 뜻 구분을 그대로 쓰고([kaikki.org](https://kaikki.org/) 추출본), 각 뜻을 LLM으로 한국어로 번역합니다.

> 아직 번역 전입니다. 번역 대상 선정과 빌드 도구만 들어 있습니다.

## 번역 대상

| 범위 | 표제어 | 항목 | 뜻 |
|---|---|---|---|
| 단일 단어: [wordfreq](https://github.com/rspeer/wordfreq) 빈도 상위 20,000 | 13,886 | 24,851 | 85,832 |
| 구동사: 위 동사 + 불변화사 (`give up`, `look forward to`) | — | 4,103 | 9,426 |
| 합계 | | 28,954 | 95,258 |

- 활용형 항목(`went`, `years`)은 뺐습니다. Yomitan이 원형으로 찾아 줍니다.
- 고유명사·문자·기호 항목과, 폐어·고어·희귀·방언·옛말투·비표준·오철자 표시가 붙은 뜻은 뺐습니다.
- 선정 결과는 `source/entries.jsonl`에 들어 있고, 빌드는 이 파일만 봅니다.

## 설치

1. [Releases](../../releases/latest)에서 `wiktionary-en-ko.zip`을 받습니다.
2. Yomitan → 설정 → 일반에서 언어를 English로 바꿉니다.
3. Yomitan → 설정 → 사전(Dictionaries) → 가져오기(Import)에서 zip을 불러옵니다.

활용형과 구동사도 검색됩니다(`running` → run, `pick it up` → pick up).

## 번역 품질

- 한국어 뜻은 LLM(Claude) 자동 번역이라 오역이 있을 수 있습니다. 항목마다 영어 원문(Wiktionary)을 접어 두었으니 확인용으로 쓰세요.
- 모델이 확신하지 못한 항목에는 `※ 자동 번역 신뢰도 낮음` 표시가 붙습니다.
- 오역 수정은 `translations/terms.jsonl`에서 해당 항목 줄의 `s`(뜻별 한국어 목록)를 고치면 됩니다.

## 직접 빌드하기

Python 3.9 이상, 그리고 번역할 때는 [Claude Code](https://claude.com/claude-code) CLI(`claude`)가 필요합니다.

```sh
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

.venv/bin/python -m enko fetch                         # Yomitan 스키마 다운로드
.venv/bin/python -m enko translate tags                # 품사·용법 태그 한국어 라벨
.venv/bin/python -m enko translate terms --limit 1000  # 빈도순으로 미번역 항목 번역 (재실행하면 이어서)
.venv/bin/python -m enko build                         # dist/wiktionary-en-ko.zip
.venv/bin/python -m enko validate                      # Yomitan 스키마 검증 + 활용 규칙 확인
.venv/bin/python -m enko review -n 200                 # review/sample.md 에 검수용 샘플
.venv/bin/python -m enko status                        # 진행 상황
```

- `build --include-untranslated`를 붙이면 미번역 항목도 영어 뜻으로 포함합니다.
- 번역 대상을 다시 뽑으려면 `python -m enko select`를 실행합니다. kaikki 영어 덤프(약 530MB)가 없으면 `data/raw/`에 받습니다. 뜻이 바뀐 항목은 다음 `translate` 때 다시 번역되고, 그 전까지 빌드에서 빠집니다.
- GitHub Actions(`.github/workflows/release.yml`)가 `translations/`, `source/`, `enko/`가 바뀔 때 다시 빌드하고, 내용이 바뀐 경우에만 릴리스를 만듭니다. 번역은 로컬에서 돌리고 `translations/`를 커밋하세요.

## 라이선스

- 코드(`enko/`, `.github/`): [MIT](LICENSE).
- 사전 데이터(`source/`, `translations/`, 빌드된 zip): [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
  영어 위키낱말사전의 파생물이며, 기계 판독용 데이터는 [Wiktextract](https://kaikki.org/)에서 가져왔습니다.
- 번역 대상을 고를 때 쓰는 빈도 데이터: [wordfreq](https://github.com/rspeer/wordfreq) (CC BY-SA 4.0). 빌드 결과물에는 포함되지 않습니다.
