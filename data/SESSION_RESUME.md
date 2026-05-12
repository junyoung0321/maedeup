# 매듭 ML 파이프라인 재개 프롬프트

## 현재 상태 요약

### 데이터 현황
- **장소 수**: 23,684개 (광역시 15,764 + 비광역시 7,920)
- **비광역시**: 아직 places.csv에서 삭제 안 됨 → 파이프라인 전에 삭제 필요
- **리뷰 텍스트 커버리지 (광역시 기준)**
  - 수집 전: ~2,585개 (16.4%)
  - 수집 후: 7,811개 (49.5%)
  - 나머지 ~7,984개는 Naver API 미노출 장소 (재수집 불가)

### 전처리 파이프라인 상태
모든 전처리 스크립트에 `save_versioned()` 추가 완료 (재실행 시 versions/ 백업 자동 생성).

| 단계 | 스크립트 | 상태 |
|------|----------|------|
| 정규화 | preprocessing/normalize.py | 완료 |
| 형태소 분석 | preprocessing/morpheme.py | 완료 |
| 반어법 탐지 | preprocessing/sarcasm.py | 완료 |
| ABSA (4축 감성) | preprocessing/absa.py | 완료 |
| 긍부정 레이블 | preprocessing/sentiment_label.py | 완료 |
| 피쳐 가공 | preprocessing/features.py | **버그 수정 완료, 재실행 필요** |

### features.py 수정 내역 (미적용 — 재실행 필요)
1. `rating_norm`: 단순 `/5.0` → percentile rank (rating>0 장소만 대상)
2. `category_depth1`: `category_group` 컬럼 → `category` 컬럼 파싱으로 변경 (결측 2,955개 커버)

### ML 모델 현황
- LGBMRanker v2, NDCG@10=0.9103, 16 feature
- 피쳐 버그 수정 전 버전 → 재학습 필요

---

## 지금 해야 할 일 (순서)

### 1. 비광역시 제거
```python
# output/places.csv에서 광역시 아닌 행 삭제
METRO_CITIES = {'서울', '부산', '인천', '대구', '대전', '광주', '울산', '세종'}
df = pd.read_csv('output/places.csv', dtype={'naver_place_id': str})
city = df['hub'].str.split('_').str[0]
df_metro = df[city.isin(METRO_CITIES)]
df_metro.to_csv('output/places.csv', index=False, encoding='utf-8-sig')
```

### 2. 전처리 파이프라인 재실행
비광역시 제거 후 raw 파일 기준으로 재실행:
```bash
python run_preprocess.py  # 또는 단계별 실행
```
순서: normalize → morpheme → sarcasm → ABSA → sentiment_labels → **features** (필수 재실행)

### 3. 시뮬레이션 재생성
```bash
python run_simulation.py
```
output/simulation/train_data.csv 재생성 (현재 59,401행 기준 → 광역시 데이터만으로 재생성)

### 4. 모델 재학습
```bash
python run_train.py
```
피쳐 버그 수정 + 새 리뷰 데이터 반영된 LGBMRanker 재학습

---

## 주요 경로
- Raw 데이터: `output/raw/`
- places.csv: `output/places.csv`
- 피쳐: `output/features/place_features.csv`
- 학습 데이터: `output/simulation/train_data.csv`
- 체크포인트: `output/place_ids/add_reviews_checkpoint.json` (14,723개)
- 버전 백업: 각 output 하위 `versions/` 폴더
