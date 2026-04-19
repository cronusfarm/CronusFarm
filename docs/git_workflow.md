# Git 협업·백업 (Thalia PC / 맥)

## 백업은 어디서 하나?

- **코드의 “정본”**: Git 원격 저장소(GitHub 등). 푸시된 커밋이 팀/기기 간 공유 기준이다.
- **각 PC의 백업**: 맞다. **Thalia·맥 각자**에서 Time Machine / File History / 수동 복사 등 **로컬 백업**을 추가하면, 원격이 일시적으로 안 될 때·실수로 강제 푸시했을 때 대비에 유리하다. Git이 대체하지 않는 것은 “내 PC 전체 디스크” 백업이다.

## Thalia(Windows) — 최초 1회

PowerShell에서 저장소 루트로 이동한 뒤:

```powershell
git init
git branch -M main
git add .
git status   # secrets.h 가 **없어야** 정상(.gitignore 적용)
git commit -m "chore: Git 초기화 및 협업 문서"
```

GitHub에서 **빈 저장소**를 만든 뒤(README 만들지 않는 것이 충돌 적음):

```powershell
git remote add origin https://github.com/<계정>/<저장소>.git
git push -u origin main
```

`git status` 에 `secrets.h` 가 보이면 **커밋하지 말고** `.gitignore` 와 파일 경로를 확인한다.

일부 드라이브(소유권 정보가 없는 볼륨 등)에서는 `fatal: detected dubious ownership` 이 나올 수 있다. Git이 제시하는 대로 한 번만 허용한다:

```powershell
git config --global --add safe.directory "D:/WorkSpace/Study/MyCode/Cursor/CronusFarm"
```

(실제 경로에 맞게 바꾼다.)

## 맥 — 나중에 (다른 Cursor 계정에서)

1. [Git](https://git-scm.com/) 설치, 터미널에서 `git --version` 확인.
2. 원격 저장소를 클론:  
   `git clone https://github.com/<계정>/<저장소>.git`  
   (SSH 키를 쓰면 `git@github.com:...` 형식.)
3. Cursor에서 **클론한 폴더**를 연다(File → Open Folder).
4. `arduino/CronusFarm/secrets.h.example` 을 복사해 `secrets.h` 생성 후 로컬 값만 채운다.
5. 작업 루틴: `git pull` → 수정 → `git commit` → `git push`.

## Cursor가 `AGENTS.md` / `.cursor/rules` / `docs` 를 읽는 방식

- 이 파일들은 **원격이 아니라 “클론된 로컬 폴더”** 안에 있다. **Git으로 받아지므로**, 맥에서 `git pull` 하면 최신 내용이 폴더에 반영되고, Cursor는 **현재 연 워크스페이스 루트** 기준으로 규칙·문서를 참고한다.
- 별도 “클라우드에서 규칙만 불러오기” 설정은 필요 없다. **저장소에 포함해 두고 Git으로 동기화**하면 된다.

## 채팅 기록

Cursor 채팅/에이전트 세션은 **계정·기기별**이라 맥에서 자동 이어쓰기는 기대하지 않는다. 이어야 할 맥락은 **`AGENTS.md` + `docs/` + 커밋 메시지**에 남기는 방식이 안정적이다.
