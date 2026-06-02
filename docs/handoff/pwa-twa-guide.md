# 매듭 PWA → TWA(안드로이드 앱) 가이드

웹앱(`/m` 모바일 뷰)을 **PWA로 설치 가능**하게 만들고, **TWA로 안드로이드 앱**으로 패키징하는 절차.
기능은 그대로 — 추가된 건 설치/오프라인/앱 셸 레이어뿐.

## 1. PWA (구현 완료)
| 요소 | 위치 |
|---|---|
| 매니페스트 | `frontend/src/app/manifest.ts` → `/manifest.webmanifest` (start_url `/m`, theme `#4f46e5`, standalone, 아이콘·shortcuts) |
| 서비스워커 | `@ducanh2912/next-pwa` 자동 생성 (`public/sw.js`, build 시) — 정적자산 캐시, API/WS는 NetworkOnly |
| 아이콘 | `frontend/public/icons/` (192·512·maskable·apple-touch·1024). 생성기 `frontend/scripts/gen_icons.py` |
| 메타 | `frontend/src/app/layout.tsx` (manifest·appleWebApp·themeColor·viewport-fit) |
| 앱 셸 | `frontend/src/app/m/layout.tsx` (폰=풀스크린+세이프에어리어, 데스크탑=390 프레임) |
| 설치 배너 | `frontend/src/components/pwa/InstallPrompt.tsx` (beforeinstallprompt 가로채기, iOS 안내) |
| 오프라인 | `frontend/src/app/offline/page.tsx` |

**dev에선 SW 비활성**(`disable: NODE_ENV==='development'`) → production 빌드에서만 동작. 설치/SW 테스트는 `npm run build && npm start` 또는 Docker(prod) 빌드로.

### 설치 가능 조건 체크
- [x] HTTPS (또는 localhost) — **프로덕션은 HTTPS 필수**
- [x] manifest (name, icons 192+512, start_url, display:standalone)
- [x] 서비스워커 등록
- [x] maskable 아이콘
- [x] theme/background color, apple-touch-icon

## 2. TWA (안드로이드 앱) — 배포 후 진행
TWA는 **PWA를 신뢰된 웹뷰로 감싼 네이티브 앱**. 전제: **PWA가 공개 HTTPS 도메인에 배포**돼 있어야 함(localhost 불가).

### 절차
```bash
# 0) PWA를 HTTPS 도메인에 배포 (예: https://maedeup.app)
# 1) Bubblewrap 설치
npm i -g @bubblewrap/cli

# 2) TWA 프로젝트 생성 (manifest URL로 초기화)
bubblewrap init --manifest https://<도메인>/manifest.webmanifest
#   → twa-manifest.json 생성. 본 레포의 twa/twa-manifest.json 값을 참고해 채움
#   (packageId=app.maedeup.twa, startUrl=/m, themeColor=#4f46e5)

# 3) 빌드 (키스토어 생성 — 비밀번호·SHA256 보관!)
bubblewrap build
#   → app-release-signed.apk / .aab 생성

# 4) Digital Asset Links 채우기 (도메인 ↔ 앱 검증)
bubblewrap fingerprint   # 또는 keytool로 SHA256 추출
#   → frontend/public/.well-known/assetlinks.json 의
#     "REPLACE_WITH_ANDROID_APP_SHA256_FINGERPRINT" 를 실제 SHA256으로 교체 후 재배포
#   (검증 실패 시 앱 상단에 URL 바가 보임 = TWA 신뢰 실패)

# 5) Play Console 업로드 (.aab) 또는 .apk 직접 설치 테스트
```

### 체크리스트
- [ ] PWA를 HTTPS 도메인에 배포
- [ ] `bubblewrap init/build` → .aab + 키스토어
- [ ] `assetlinks.json`에 SHA256 채우고 재배포 → `https://<도메인>/.well-known/assetlinks.json` 200 확인
- [ ] 디바이스에서 URL 바 안 보이면 TWA 검증 성공
- [ ] (선택) Play Console 등록

## 3. 주의 / 후속
- **localhost 배포 한계**: TWA·iOS 설치·SW는 HTTPS 도메인에서 완전 동작. 로컬은 PWA 설치 가능성만 부분 확인.
- **폰트 크기**: `globals.css`의 `html{font-size:22px}`·`body{zoom:0.95}`는 시연(프로젝션 가독성)용 — 실제 폰 앱에선 큼. 앱 전환 시 모바일 기준(16px)으로 조정 검토.
- **CSP**: `script-src 'self' … kakao`. SW/매니페스트는 same-origin이라 영향 없음.
- 빌드 산출물(`public/sw.js`, `public/workbox-*.js`, `public/fallback-*.js`)은 `.gitignore` 처리(빌드마다 생성).
